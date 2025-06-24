from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils import timezone
from .models import Article

class LatestArticlesFeed(Feed):
    title = "AlgoTime: Новые статьи"
    link = "/feed/"
    description = "Последние статьи об алгоритмах и программировании"
    feed_type = Atom1Feed
    feed_copyright = f"Copyright © {timezone.now().year}, AlgoTime"

    def items(self):
        return Article.objects.filter(
            status='published'
        ).order_by('-pub_date')[:10]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return strip_tags(item.content[:500]) + "..."

    def item_pubdate(self, item):
        return item.pub_date

    def item_updateddate(self, item):
        return item.updated_at

    def item_categories(self, item):
        return [item.category.name]

    def item_author_name(self, item):
        return item.author.username if item.author else "Anonymous"

    def item_link(self, item):
        return reverse('blog:article_detail', kwargs={'slug': item.slug})

    def feed_url(self):
        return reverse('blog:feed')
