from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .feeds import LatestArticlesFeed

app_name = 'blog'  # Namespace для URL

urlpatterns = [
    # Основные URL
    path('', views.home, name='home'),
    path('search/', views.search, name='search'),
    path('signup/', views.signup, name='signup'),
    
    # Комментарии
    path('comments/add/', views.add_comment, name='add_comment'),
    
    # Статьи
    path('articles/<slug:slug>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('articles/<int:pk>/', RedirectView.as_view(pattern_name='blog:article_detail', permanent=True)),
    
    # Категории и теги
    path('category/<slug:slug>/', views.category_view, name='category'),
    path('tag/<slug:slug>/', views.tag_view, name='tag'),
    
    # API для комментариев
    path('api/comment/', include([
        path('delete/<int:pk>/', views.delete_comment, name='delete_comment'),
    ])),
    
    # RSS и sitemap
    path('feed/', LatestArticlesFeed(), name='articles_feed'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
