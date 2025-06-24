from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.core.cache import cache
from django.db.models import Count, Q, F
from django.core.validators import MinLengthValidator
from django.utils.translation import gettext_lazy as _
import itertools
import re

User = get_user_model()

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        abstract = True
        ordering = ['-created_at']

class SlugMixin(models.Model):
    slug = models.SlugField(max_length=255, unique=True, blank=True, verbose_name=_('URL'))
    slug_source_field = None

    def generate_unique_slug(self):
        source_text = getattr(self, self.slug_source_field)
        
        # Кастомная функция транслитерации кириллицы
        def transliterate(text):
            text = text.lower()
            # Основные символы
            cyrillic = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
            latin = 'a|b|v|g|d|e|e|zh|z|i|j|k|l|m|n|o|p|r|s|t|u|f|kh|ts|ch|sh|shch||y||e|yu|ya'.split('|')
            trans_dict = dict(zip(cyrillic, latin))
            
            # Замена символов
            result = []
            for char in text:
                result.append(trans_dict.get(char, char))
            return ''.join(result)
        
        # Генерация slug
        transliterated = transliterate(source_text)
        slug = orig_slug = slugify(transliterated)[:self._meta.get_field('slug').max_length].strip('-')

        for i in itertools.count(1):
            if not self.__class__.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                break
            slug = f"{orig_slug}-{i}"[:self._meta.get_field('slug').max_length]
        
        return slug

    def save(self, *args, **kwargs):
        if not self.slug or self._state.adding:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)

    class Meta:
        abstract = True

class Category(SlugMixin, BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Order'))
    slug_source_field = 'name'

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('blog:category', kwargs={'slug': self.slug})

    @property
    def published_articles_count(self):
        return self.articles.filter(status=Article.Status.PUBLISHED).count()

class Tag(SlugMixin, BaseModel):
    name = models.CharField(max_length=50, unique=True, verbose_name=_('Name'))
    slug_source_field = 'name'

    class Meta:
        verbose_name = _('Tag')
        verbose_name_plural = _('Tags')
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('blog:tag', kwargs={'slug': self.slug})

    @property
    def published_articles_count(self):
        return self.articles.filter(status=Article.Status.PUBLISHED).count()

class Article(SlugMixin, BaseModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        PUBLISHED = 'published', _('Published')
        ARCHIVED = 'archived', _('Archived')

    title = models.CharField(max_length=200, verbose_name=_('Title'))
    content = models.TextField(verbose_name=_('Content'))
    excerpt = models.TextField(blank=True, default="", verbose_name=_('Excerpt'))
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_('Status')
    )
    pub_date = models.DateTimeField(default=timezone.now, verbose_name=_('Publication date'))
    view_count = models.PositiveIntegerField(default=0, verbose_name=_('View count'))
    meta_description = models.CharField(max_length=160, blank=True, verbose_name=_('Meta description'))
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name=_('Meta keywords'))
    
    # Relationships
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='articles',
        verbose_name=_('Category')
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='articles',
        verbose_name=_('Author')
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='articles',
        verbose_name=_('Tags')
    )
    featured_image = models.ImageField(
        upload_to='article_images/%Y/%m/',
        blank=True,
        null=True,
        verbose_name=_('Featured image')
    )
    
    slug_source_field = 'title'

    class Meta:
        verbose_name = _('Article')
        verbose_name_plural = _('Articles')
        ordering = ['-pub_date']
        get_latest_by = ['-pub_date', '-updated_at']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['title', 'pub_date']),
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
            models.Index(fields=['pub_date']),
            models.Index(fields=['view_count']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.excerpt:
            self.excerpt = strip_tags(self.content)[:200] + '...'
        
        super().save(*args, **kwargs)
        
        # Clear relevant cache
        cache.delete('home_articles_page_1')
        cache.delete(f'article_{self.id}_related')

    def get_absolute_url(self):
        return reverse('blog:article_detail', kwargs={'slug': self.slug})

    def increment_view_count(self):
        Article.objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)
        self.refresh_from_db()

    def get_meta_description(self):
        return self.meta_description or strip_tags(self.content)[:160]

    def get_meta_keywords(self):
        return self.meta_keywords or ', '.join(tag.name for tag in self.tags.all()[:5])

    @property
    def comments(self):
        content_type = ContentType.objects.get_for_model(self)
        return Comment.objects.filter(
            content_type=content_type,
            object_id=self.id,
            parent__isnull=True,
            is_deleted=False
        ).select_related('user').prefetch_related('replies')

    @property
    def comments_count(self):
        return self.comments.count()

class Comment(BaseModel):
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        verbose_name=_('User'),
        related_name='comments'
    )
    text = models.TextField(
        max_length=2000, 
        verbose_name=_('Text'),
        validators=[MinLengthValidator(10)]
    )
    parent = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE,
        verbose_name=_('Parent comment'),
        related_name='replies'
    )
    is_deleted = models.BooleanField(
        default=False, 
        verbose_name=_('Is deleted')
    )
    
    # Generic relation
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_deleted']),
        ]

    def __str__(self):
        return _('Comment by %(username)s') % {'username': self.user.username}

    def get_absolute_url(self):
        return f"{self.content_object.get_absolute_url()}#comment-{self.id}"

    def get_children(self):
        return self.replies.filter(is_deleted=False).select_related('user')

    def save(self, *args, **kwargs):
        self.text = strip_tags(self.text)
        super().save(*args, **kwargs)
        
        if hasattr(self.content_object, 'id'):
            cache.delete(f'article_{self.content_object.id}_comments')
