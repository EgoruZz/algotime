from django.contrib.postgres.search import (
    SearchVector, 
    SearchQuery, 
    SearchRank,
    TrigramSimilarity
)
from django.db.models import Q, Count
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.conf import settings
from django.core.cache import cache
from django.db.utils import OperationalError
from django.views.generic.edit import FormMixin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponseForbidden
from django.views.generic import DetailView
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.shortcuts import redirect
from .models import Article, Comment
from .forms import CommentForm, CustomUserCreationForm
from django.db import connection

from .models import Article, Category, Tag, Comment
from .forms import CommentForm


def add_comment(request):
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            
            # Получаем связанный объект (статью)
            content_type = ContentType.objects.get(model='article')
            comment.content_type = content_type
            comment.object_id = request.POST.get('object_id')
            
            # Обработка родительского комментария
            parent_id = request.POST.get('parent_id')
            if parent_id:
                comment.parent = get_object_or_404(Comment, id=parent_id)
            
            comment.save()
            return redirect(comment.content_object.get_absolute_url())
    
    # Если что-то пошло не так, перенаправляем на главную
    return redirect('blog:home')

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('blog:home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

def get_paginated_articles(queryset, request, cache_key=None, timeout=900):
    """
    Утилита для пагинации с кешированием
    """
    per_page = request.GET.get('per_page', settings.ARTICLES_PER_PAGE)
    try:
        per_page = min(int(per_page), 50)  # Максимум 50 на странице
    except ValueError:
        per_page = settings.ARTICLES_PER_PAGE
        
    paginator = Paginator(queryset, per_page)

    if cache_key and (articles := cache.get(cache_key)):
        return articles
    
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)
    
    if cache_key:
        cache.set(cache_key, page, timeout)
    return page

@vary_on_cookie
@cache_page(60 * 15)  # Кеширование на 15 минут
def home(request):
    """
    Главная страница со списком статей
    """
    cache_key = 'home_articles_page_' + str(request.GET.get('page', 1))
    
    articles = Article.objects.filter(
        status='published'
    ).select_related(
        'category', 'author'
    ).prefetch_related(
        'tags'
    ).order_by('-pub_date')
    
    articles = get_paginated_articles(articles, request, cache_key)
    
    # Получаем популярные теги (кешируем на 1 час)
    popular_tags = cache.get_or_set('popular_tags', 
        Tag.objects.annotate(
            num_articles=Count('articles')
        ).filter(
            num_articles__gt=0
        ).order_by('-num_articles')[:10], 
        3600)
    
    return render(request, 'blog/index.html', {
        'articles': articles,
        'popular_tags': popular_tags,
        'categories': cache.get_or_set(
            'all_categories', 
            Category.objects.annotate(
                num_articles=Count('articles')
            ).filter(
                num_articles__gt=0
            ), 
            3600
        )
    })

class ArticleDetailView(FormMixin, DetailView):
    """
    Детальное отображение статьи с комментариями
    """
    model = Article
    form_class = CommentForm
    template_name = 'blog/article_detail.html'
    context_object_name = 'article'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        if self.request.user.is_staff:
            return Article.objects.all()
        return Article.objects.filter(status='published')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Увеличиваем счетчик просмотров только для опубликованных статей
        if self.object.status == 'published':
            self.object.increment_view_count()
            
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_success_url(self):
        return self.object.get_absolute_url()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object
        
        # Кеширование связанных статей на 1 час
        cache_key = f'article_{article.id}_related'
        related_articles = cache.get_or_set(cache_key, 
            Article.objects.filter(
                tags__in=article.tags.all(),
                status='published'
            ).exclude(
                id=article.id
            ).distinct()[:3], 
            3600)
        
        context.update({
            'comments': article.comments,
            'comment_form': CommentForm(),
            'related_articles': related_articles,
            'meta_description': article.get_meta_description(),
            'meta_keywords': article.get_meta_keywords(),
        })
        return context
    
    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
    
    def form_valid(self, form):
        comment = form.save(commit=False)
        comment.user = self.request.user
        comment.content_object = self.object
        comment.save()
        return super().form_valid(form)

@require_http_methods(["POST"])
@login_required
def delete_comment(request, pk):
    """
    Удаление комментария (помечаем как удаленный)
    """
    comment = get_object_or_404(Comment, pk=pk, user=request.user)
    comment.is_deleted = True
    comment.save()
    return JsonResponse({'status': 'ok'})

def search(request):
    """
    Поиск по статьям с поддержкой триграмм и полнотекстового поиска
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return render(request, 'blog/search.html', {
            'results': [], 
            'query': '',
            'suggestion': None
        })

    base_qs = Article.objects.filter(
        status='published'
    ).select_related(
        'category', 'author'
    ).prefetch_related(
        'tags'
    )

    try:
        # Для PostgreSQL с поддержкой триграмм
        if connection.vendor == 'postgresql':
            # Используем полнотекстовый поиск для сложных запросов
            if len(query.split()) > 1:
                search_query = SearchQuery(query)
                results = base_qs.annotate(
                    search=SearchVector('title', weight='A') + 
                        SearchVector('content', weight='B'),
                    rank=SearchRank(
                        SearchVector('title', 'content'), 
                        search_query
                    )
                ).filter(
                    search=search_query
                ).order_by('-rank', '-pub_date')
            else:
                # Для простых запросов используем триграммы с явным приведением типов
                results = base_qs.annotate(
                    similarity=TrigramSimilarity('title', query) +
                            TrigramSimilarity('content', query)
                ).filter(
                    similarity__gt=0.1
                ).order_by('-similarity', '-pub_date')
                
            suggestion = base_qs.annotate(
                similarity=TrigramSimilarity('title', query)
            ).filter(
                similarity__gt=0.3
            ).order_by('-similarity').first()
            
        else:
            # Fallback для других БД
            results = base_qs.filter(
                Q(title__icontains=query) | 
                Q(content__icontains=query))
            suggestion = None

    except OperationalError:
        # Дополнительный fallback
        results = base_qs.filter(
            Q(title__icontains=query) | 
            Q(content__icontains=query))
        suggestion = None

    results = get_paginated_articles(results, request)
    
    return render(request, 'blog/search.html', {
        'results': results, 
        'query': query,
        'suggestion': suggestion.title if suggestion else None
    })

def category_view(request, slug):
    """
    Отображение статей по категориям
    """
    cache_key = f'category_{slug}_page_{request.GET.get("page", 1)}'
    
    category = get_object_or_404(Category, slug=slug)
    articles = Article.objects.filter(
        category=category, 
        status='published'
    ).select_related(
        'author'
    ).prefetch_related(
        'tags'
    ).order_by('-pub_date')
    
    articles = get_paginated_articles(articles, request, cache_key)
    
    return render(request, 'blog/category.html', {
        'category': category,
        'articles': articles,
        'meta_description': f"Статьи по категории {category.name}",
        'meta_keywords': f"{category.name}, алгоритмы, программирование"
    })

def tag_view(request, slug):
    """
    Отображение статей по тегам
    """
    cache_key = f'tag_{slug}_page_{request.GET.get("page", 1)}'
    
    tag = get_object_or_404(Tag, slug=slug)
    articles = Article.objects.filter(
        tags=tag, 
        status='published'
    ).select_related(
        'category', 'author'
    ).prefetch_related(
        'tags'
    ).order_by('-pub_date')
    
    articles = get_paginated_articles(articles, request, cache_key)
    
    return render(request, 'blog/tag.html', {
        'tag': tag,
        'articles': articles,
        'meta_description': f"Статьи по тегу {tag.name}",
        'meta_keywords': f"{tag.name}, алгоритмы, программирование"
    })
