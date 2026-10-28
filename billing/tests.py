"""
Tests for billing models.
"""

from datetime import date, datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from users.models import User

from .models import Invoice


class TestInvoiceNumber(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="billing@example.com",
            username="billing@example.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller = user.seller_profile

    def _make_invoice(self):
        return Invoice.objects.create(
            seller=self.seller,
            amount=100,
            due_date=date(2026, 1, 9),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        )

    def test_numbers_are_sequential_within_year(self):
        year = timezone.localdate().year
        first = self._make_invoice()
        second = self._make_invoice()
        self.assertEqual(first.invoice_number, f"{year}-0001")
        self.assertEqual(second.invoice_number, f"{year}-0002")

    def test_numbering_restarts_each_year(self):
        new_year = timezone.make_aware(datetime(2030, 1, 1, 12))
        self._make_invoice()
        with mock.patch("django.utils.timezone.now", return_value=new_year):
            invoice = self._make_invoice()
        self.assertEqual(invoice.invoice_number, "2030-0001")
