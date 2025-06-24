from django.contrib.sitemaps import Sitemap
from .models import Article
from django.urls import reverse

class ArticleSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Article.objects.filter(status='published')

    def lastmod(self, obj):
        return obj.updated_at

class StaticViewSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return ['blog:home', 'blog:search']

    def location(self, item):
        return reverse(item)
