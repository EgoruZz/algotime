from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, mark_safe
from django.db.models import Count, Q, OuterRef, Subquery, IntegerField
from django.shortcuts import redirect
from django.contrib.contenttypes.models import ContentType
from .models import Category, Tag, Article, Comment
from django.db.models.functions import Coalesce
from django.db import models

class CommentCountFilter(admin.SimpleListFilter):
    title = 'Количество комментариев'
    parameter_name = 'comment_count'
    
    def lookups(self, request, model_admin):
        return (
            ('0', 'Нет комментариев'),
            ('1-5', '1-5 комментариев'),
            ('5-20', '5-20 комментариев'),
            ('20+', '20+ комментариев'),
        )
    
    def queryset(self, request, queryset):
        content_type = ContentType.objects.get_for_model(Article)
        comment_subquery = Comment.objects.filter(
            content_type=content_type,
            object_id=OuterRef('pk')
        ).values('object_id').annotate(
            cnt=Count('*')
        ).values('cnt')[:1]
        
        queryset = queryset.annotate(
            comment_count=Coalesce(
                Subquery(comment_subquery),
                0,
                output_field=IntegerField()
            )
        )
        
        if self.value() == '0':
            return queryset.filter(comment_count=0)
        if self.value() == '1-5':
            return queryset.filter(comment_count__range=(1,5))
        if self.value() == '5-20':
            return queryset.filter(comment_count__range=(5,20))
        if self.value() == '20+':
            return queryset.filter(comment_count__gt=20)

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'preview_text', 'content_object_link', 
                   'created_at', 'is_deleted', 'has_replies')
    list_filter = ('is_deleted', 'created_at', 'content_type')
    search_fields = ('text', 'user__username')
    list_select_related = ('user', 'content_type')
    readonly_fields = ('created_at', 'updated_at','content_object_link', 'preview_text', 'parent_link')
    actions = ['mark_as_deleted', 'restore_comments']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('user', 'content_object_link', 'parent_link')
        }),
        ('Содержание', {
            'fields': ('preview_text', 'text')
        }),
        ('Статус', {
            'fields': ('is_deleted',)
        }),
    )

    def preview_text(self, obj):
        return obj.text[:100] + '...' if obj.text else ''
    preview_text.short_description = 'Текст'

    def content_object_link(self, obj):
        if obj.content_object:
            url = reverse(f'admin:{obj.content_object._meta.app_label}_{obj.content_object._meta.model_name}_change', 
                         args=[obj.content_object.id])
            return format_html('<a href="{}">{}</a>', url, str(obj.content_object))
        return "-"
    content_object_link.short_description = "Связанный объект"
    content_object_link.admin_order_field = "object_id"

    def parent_link(self, obj):
        if obj.parent:
            return mark_safe(
                f'<a href="{reverse("admin:blog_comment_change", args=[obj.parent.id])}">'
                f'Комментарий #{obj.parent.id}</a>'
            )
        return '-'
    parent_link.short_description = 'Родительский комментарий'

    def has_replies(self, obj):
        return obj.replies.exists()
    has_replies.boolean = True
    has_replies.short_description = 'Есть ответы'

    def mark_as_deleted(self, request, queryset):
        updated = queryset.update(is_deleted=True)
        self.message_user(request, f'{updated} комментариев помечено как удаленные')
    mark_as_deleted.short_description = "Пометить как удаленные"

    def restore_comments(self, request, queryset):
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f'{updated} комментариев восстановлено')
    restore_comments.short_description = "Восстановить комментарии"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'article_count', 'order')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('order',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _article_count=Count('articles')
        )
    
    def article_count(self, obj):
        return obj._article_count
    article_count.admin_order_field = '_article_count'
    article_count.short_description = 'Кол-во статей'

class ArticleTagInline(admin.TabularInline):
    model = Article.tags.through
    extra = 1
    verbose_name = "Тег"
    verbose_name_plural = "Теги статьи"
    autocomplete_fields = ['tag']

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'article_count')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ArticleTagInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _article_count=Count('articles')
        )
    
    def article_count(self, obj):
        return obj._article_count
    article_count.admin_order_field = '_article_count'
    article_count.short_description = 'Кол-во статей'

    def view_articles(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Выберите ровно один тег", level='error')
            return
        
        tag = queryset.first()
        url = f"{reverse('admin:blog_article_changelist')}?tags__id__exact={tag.id}"
        return redirect(url)
    view_articles.short_description = "Просмотреть статьи с этим тегом"
    actions = [view_articles]

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'pub_date', 
                   'view_count', 'comment_count', 'reading_time')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        content_type = ContentType.objects.get_for_model(Article)
        
        comment_subquery = Comment.objects.filter(
            content_type=content_type,
            object_id=OuterRef('pk')
        ).values('object_id').annotate(
            cnt=Count('*')
        ).values('cnt')[:1]
        
        return queryset.annotate(
            _comment_count=Coalesce(
                Subquery(comment_subquery),
                0,
                output_field=IntegerField()
            )
        )
    
    def comment_count(self, obj):
        return obj._comment_count
    comment_count.admin_order_field = '_comment_count'
    comment_count.short_description = 'Комментарии'
    
    def preview_content(self, obj):
        return obj.content[:200] + '...' if obj.content else ''
    preview_content.short_description = 'Превью'
    
    def reading_time(self, obj):
        if not obj.content:
            return '0 мин.'
        words = len(obj.content.split())
        minutes = max(1, words // 200)
        return f'{minutes} мин.'
    reading_time.short_description = 'Время чтения'
    
    def admin_thumbnail(self, obj):
        if obj.featured_image:
            return mark_safe(
                f'<img src="{obj.featured_image.url}" style="max-height: 200px;"/>'
            )
        return '-'
    admin_thumbnail.short_description = 'Превью изображения'
    
    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)
