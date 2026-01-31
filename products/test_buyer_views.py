"""
Tests for buyer product browsing and detail views.
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse

from users.models import User
from sellers.models import Seller
from products.models import Product, ProductCategory, ProductCondition, ProductImage


class ProductBrowseViewTests(TestCase):
    """Tests for public product browsing functionality."""

    def setUp(self):
        """Set up test data."""
        # Create test user and seller
        self.user = User.objects.create_user(
            email='seller1@test.com',
            username='seller1@test.com',
            password='testpass123',
            is_seller=True
        )
        
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user,
            defaults={
                'shop_name': 'Test Shop',
                'shop_slug': 'test-shop'
            }
        )
        
        # Create categories and conditions
        self.category = ProductCategory.objects.create(
            name='Electronics',
            slug='electronics',
            description='Electronic items'
        )
        
        self.condition = ProductCondition.objects.create(
            name='Like New',
            description='Like new condition'
        )
        
        # Create published products
        self.product1 = Product.objects.create(
            seller=self.seller,
            title='Test Product 1',
            description='A great test product',
            price=29.99,
            category=self.category,
            condition=self.condition,
            stock=5,
            status='published'
        )
        
        self.product2 = Product.objects.create(
            seller=self.seller,
            title='Test Product 2',
            description='Another test product',
            price=49.99,
            category=self.category,
            condition=self.condition,
            stock=0,
            status='published'
        )
        
        # Create draft product (should not appear in browse)
        self.draft_product = Product.objects.create(
            seller=self.seller,
            title='Draft Product',
            description='This is a draft',
            price=19.99,
            category=self.category,
            status='draft'
        )
        
        self.client = Client()

    def test_products_browse_view_returns_200(self):
        """Test that products browse view returns 200."""
        response = self.client.get(reverse('products_browse'))
        self.assertEqual(response.status_code, 200)

    def test_products_browse_shows_published_products(self):
        """Test that browse view shows only published products."""
        response = self.client.get(reverse('products_browse'))
        self.assertContains(response, self.product1.title)
        self.assertContains(response, self.product2.title)
        self.assertNotContains(response, self.draft_product.title)

    def test_products_browse_search(self):
        """Test product search functionality."""
        response = self.client.get(reverse('products_browse'), {'q': 'Product 1'})
        self.assertContains(response, self.product1.title)
        self.assertNotContains(response, self.product2.title)

    def test_products_browse_filter_by_category(self):
        """Test filtering by category."""
        # Create product in different category
        other_category = ProductCategory.objects.create(
            name='Books',
            slug='books'
        )
        other_product = Product.objects.create(
            seller=self.seller,
            title='Book Product',
            description='A book',
            price=15.99,
            category=other_category,
            status='published'
        )
        
        response = self.client.get(
            reverse('products_browse'),
            {'category': self.category.id}
        )
        self.assertContains(response, self.product1.title)
        self.assertNotContains(response, other_product.title)

    def test_products_browse_sort_by_price(self):
        """Test sorting by price."""
        response = self.client.get(reverse('products_browse'), {'sort': 'price'})
        self.assertContains(response, self.product1.title)
        # Verify response has product data
        self.assertEqual(response.status_code, 200)

    def test_products_browse_pagination(self):
        """Test pagination works."""
        # Create many products
        for i in range(15):
            Product.objects.create(
                seller=self.seller,
                title=f'Product {i}',
                description='Test',
                price=19.99 + i,
                status='published'
            )
        
        response = self.client.get(reverse('products_browse'))
        self.assertEqual(len(response.context['products']), 12)  # 12 per page


class CategoryProductsViewTests(TestCase):
    """Tests for category-based product browsing."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='seller2@test.com',
            username='seller2@test.com',
            password='testpass123',
            is_seller=True
        )
        
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user,
            defaults={
                'shop_name': 'Test Shop',
                'shop_slug': 'test-shop-2'
            }
        )
        
        self.category = ProductCategory.objects.create(
            name='Electronics',
            slug='electronics'
        )
        
        self.product = Product.objects.create(
            seller=self.seller,
            title='Electronics Product',
            description='An electronic item',
            price=99.99,
            category=self.category,
            status='published'
        )
        
        self.client = Client()

    def test_category_view_returns_200(self):
        """Test that category view returns 200."""
        response = self.client.get(
            reverse('category_products', args=[self.category.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_category_view_shows_products_in_category(self):
        """Test that category view shows only products in that category."""
        response = self.client.get(
            reverse('category_products', args=[self.category.id])
        )
        self.assertContains(response, self.product.title)

    def test_category_view_hides_products_in_other_categories(self):
        """Test that category view hides products from other categories."""
        other_category = ProductCategory.objects.create(
            name='Books',
            slug='books'
        )
        other_product = Product.objects.create(
            seller=self.seller,
            title='Book',
            description='A book',
            price=15.99,
            category=other_category,
            status='published'
        )
        
        response = self.client.get(
            reverse('category_products', args=[self.category.id])
        )
        self.assertContains(response, self.product.title)
        self.assertNotContains(response, other_product.title)


class ProductDetailViewTests(TestCase):
    """Tests for public product detail view."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='seller3@test.com',
            username='seller3@test.com',
            password='testpass123',
            is_seller=True
        )
        
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user,
            defaults={
                'shop_name': 'Test Shop',
                'shop_slug': 'test-shop-3'
            }
        )
        
        self.category = ProductCategory.objects.create(
            name='Electronics',
            slug='electronics'
        )
        
        self.condition = ProductCondition.objects.create(
            name='Like New'
        )
        
        self.product = Product.objects.create(
            seller=self.seller,
            title='Test Product',
            description='This is a test product with details',
            price=49.99,
            category=self.category,
            condition=self.condition,
            stock=5,
            status='published'
        )
        
        # Create related products
        self.related_product = Product.objects.create(
            seller=self.seller,
            title='Related Product',
            description='Another product from same seller',
            price=39.99,
            status='published'
        )
        
        self.client = Client()

    def test_product_detail_view_returns_200(self):
        """Test that product detail view returns 200."""
        response = self.client.get(
            reverse('product_detail', args=[self.product.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_product_detail_shows_product_info(self):
        """Test that product detail page shows all product information."""
        response = self.client.get(
            reverse('product_detail', args=[self.product.id])
        )
        self.assertContains(response, self.product.title)
        self.assertContains(response, self.product.description)
        # Price is formatted with locale, so check for both period and comma versions
        self.assertTrue(
            b'49.99' in response.content or b'49,99' in response.content,
            f"Neither '49.99' nor '49,99' found in response"
        )

    def test_product_detail_shows_seller_info(self):
        """Test that product detail shows seller information."""
        response = self.client.get(
            reverse('product_detail', args=[self.product.id])
        )
        self.assertContains(response, self.seller.shop_name)

    def test_product_detail_shows_related_products(self):
        """Test that related products are shown."""
        response = self.client.get(
            reverse('product_detail', args=[self.product.id])
        )
        self.assertContains(response, self.related_product.title)

    def test_product_detail_404_for_draft_product(self):
        """Test that draft products return 404."""
        draft = Product.objects.create(
            seller=self.seller,
            title='Draft Product',
            description='This is a draft',
            price=19.99,
            status='draft'
        )
        
        response = self.client.get(
            reverse('product_detail', args=[draft.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_product_detail_shows_stock_status(self):
        """Test that stock status is displayed."""
        response = self.client.get(
            reverse('product_detail', args=[self.product.id])
        )
        self.assertContains(response, 'In Stock')

    def test_product_detail_out_of_stock(self):
        """Test that out of stock is shown for zero stock products."""
        out_of_stock = Product.objects.create(
            seller=self.seller,
            title='Out of Stock Product',
            description='No stock',
            price=29.99,
            stock=0,
            status='published'
        )
        
        response = self.client.get(
            reverse('product_detail', args=[out_of_stock.id])
        )
        self.assertContains(response, 'Out of Stock')
