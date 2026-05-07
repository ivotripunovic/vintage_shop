"""
Crawl all internal links reachable from the home page and assert none return errors.
Runs as both anonymous and authenticated (seller) user.
"""

import pytest
from html.parser import HTMLParser
from django.test import TestCase
from django.urls import reverse

from users.models import User
from sellers.models import Seller
from products.models import Product, ProductCategory, ProductCondition


class LinkExtractor(HTMLParser):
    """Extract href values from <a> tags."""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr, value in attrs:
                if attr == "href" and value:
                    self.links.append(value)


def extract_links(html):
    parser = LinkExtractor()
    parser.feed(html)
    return parser.links


def is_internal(href):
    """Keep only local paths, skip anchors, mailto, external URLs."""
    if not href or href.startswith(("#", "mailto:", "tel:")):
        return False
    if href.startswith("http://") or href.startswith("https://"):
        return False
    return True


def crawl(client, seed_url, expected_ok=(200,), follow_redirects=False):
    """
    BFS crawl from seed_url using client.
    Returns a dict of {url: status_code} for every URL visited.
    """
    visited = {}
    queue = [seed_url]

    while queue:
        url = queue.pop(0)
        if url in visited:
            continue

        response = client.get(url)
        visited[url] = response.status_code

        # Only follow links on pages that rendered successfully
        if response.status_code == 200:
            for href in extract_links(response.content.decode("utf-8", errors="ignore")):
                if is_internal(href) and href not in visited and href not in queue:
                    queue.append(href)

    return visited


class AnonymousLinkCrawlTest(TestCase):
    """Crawl all pages reachable by an anonymous visitor."""

    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user(
            email="seller@linktest.com",
            username="seller@linktest.com",
            password="testpass123",
            is_seller=True,
            is_buyer=True,
            email_verified=True,
        )
        seller, _ = Seller.objects.get_or_create(
            user=user,
            defaults={"shop_name": "Link Test Shop", "shop_slug": "link-test-shop"},
        )
        Seller.objects.filter(pk=seller.pk).update(
            shop_name="Link Test Shop",
            shop_slug="link-test-shop",
            status="active",
        )
        category = ProductCategory.objects.create(
            name="Test Category", slug="test-category-links"
        )
        condition = ProductCondition.objects.create(name="Dobro", order=1)
        cls.product = Product.objects.create(
            seller=seller,
            title="Link Test Product",
            description="Used for link testing.",
            price="100.00",
            category=category,
            condition=condition,
            stock=1,
            status="published",
        )

    def test_no_broken_links_as_anonymous(self):
        visited = crawl(self.client, reverse("home"))

        broken = {
            url: code
            for url, code in visited.items()
            if code >= 400
        }
        self.assertEqual(
            broken, {},
            msg=f"Broken links found (anonymous): {broken}",
        )

    def test_pages_reachable(self):
        """Key public pages must be in the crawl results."""
        visited = crawl(self.client, reverse("home"))
        expected = [
            reverse("home"),
            reverse("products_browse"),
            reverse("shops_browse"),
            reverse("register"),
            reverse("login"),
        ]
        for url in expected:
            self.assertIn(url, visited, msg=f"Page not reached by crawler: {url}")
            self.assertEqual(visited[url], 200, msg=f"{url} returned {visited[url]}")


class AuthenticatedLinkCrawlTest(TestCase):
    """Crawl all pages reachable by a logged-in seller."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="seller2@linktest.com",
            username="seller2@linktest.com",
            password="testpass123",
            is_seller=True,
            is_buyer=True,
            email_verified=True,
        )
        seller, _ = Seller.objects.get_or_create(
            user=cls.user,
            defaults={"shop_name": "Auth Link Shop", "shop_slug": "auth-link-shop"},
        )
        Seller.objects.filter(pk=seller.pk).update(
            shop_name="Auth Link Shop",
            shop_slug="auth-link-shop",
            status="active",
        )
        category = ProductCategory.objects.create(
            name="Auth Category", slug="auth-category-links"
        )
        condition = ProductCondition.objects.create(name="Novo", order=0)
        cls.product = Product.objects.create(
            seller=seller,
            title="Auth Link Product",
            description="Used for authenticated link testing.",
            price="200.00",
            category=category,
            condition=condition,
            stock=2,
            status="published",
        )

    def setUp(self):
        self.client.login(username="seller2@linktest.com", password="testpass123")

    def test_no_broken_links_as_seller(self):
        visited = crawl(self.client, reverse("home"))

        broken = {
            url: code
            for url, code in visited.items()
            if code >= 400
        }
        self.assertEqual(
            broken, {},
            msg=f"Broken links found (seller): {broken}",
        )

    def test_seller_pages_reachable(self):
        """Seller-specific pages must be reachable when logged in."""
        visited = crawl(self.client, reverse("home"))
        expected = [
            reverse("seller_dashboard"),
            reverse("seller_products_list"),
            reverse("product_create"),
        ]
        for url in expected:
            self.assertIn(url, visited, msg=f"Page not reached by crawler: {url}")
            self.assertEqual(visited[url], 200, msg=f"{url} returned {visited[url]}")
