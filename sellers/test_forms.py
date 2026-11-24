"""
Tests for seller forms.
"""

from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from users.models import User

from .forms import SellerAccountSettingsForm
from .models import TRADER_STATEMENT, Seller


class SellerAccountSettingsFormTests(TestCase):
    """Tests for SellerAccountSettingsForm."""

    def setUp(self):
        """Set up test user and seller."""
        self.user = User.objects.create_user(
            email="test@example.com",
            username="test@example.com",
            password="testpass123",
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user,
            defaults={
                "shop_name": "Test Shop",
                "shop_slug": "test-shop",
                "shop_description": "Test description",
                "location": "Test location",
            },
        )

    def test_form_accepts_user_as_keyword_argument(self):
        """Test that form can be instantiated with user as keyword argument."""
        # This is how the view calls it
        form = SellerAccountSettingsForm(
            data={
                "shop_name": "Updated Shop",
                "shop_description": "Updated description",
                "location": "Updated location",
            },
            instance=self.seller,
            user=self.user,
        )

        self.assertTrue(form.is_valid(), str(form.errors))

    def test_form_has_no_email_field(self):
        """The account email is changed through allauth (/auth/email/), #77."""
        form = SellerAccountSettingsForm(instance=self.seller, user=self.user)
        self.assertNotIn("email", form.fields)

    def test_form_with_files_and_user(self):
        """Test that form accepts files and user as keyword argument."""
        image = SimpleUploadedFile(
            "test.jpg", b"fake image content", content_type="image/jpeg"
        )

        files = MultiValueDict({"shop_image": [image]})
        form = SellerAccountSettingsForm(
            data={
                "shop_name": "Updated Shop",
                "shop_description": "Updated description",
                "location": "Updated location",
                "email": "updated@example.com",
            },
            files=files,
            instance=self.seller,
            user=self.user,
        )

        # Form should process without TypeError
        try:
            is_valid = form.is_valid()
        except TypeError as e:
            self.fail(f"Form raised TypeError: {e}")

    def test_form_no_typeerror_with_post_and_user_kwarg(self):
        """
        Regression test: Ensure form doesn't raise TypeError when user is passed
        as keyword argument alongside POST/FILES data.

        This tests the bug fix where __init__(user, *args, **kwargs) was changed to
        __init__(*args, user=None, **kwargs) to allow user to be a keyword argument.

        Bug: TypeError at /en/seller/settings/
        SellerAccountSettingsForm.__init__() got multiple values for argument 'user'
        """
        # This should NOT raise TypeError
        try:
            form = SellerAccountSettingsForm(
                data={
                    "shop_name": "Updated Shop",
                    "shop_description": "Updated description",
                    "location": "Updated location",
                    "email": "newemail@example.com",
                },
                instance=self.seller,
                user=self.user,
            )
            # If we got here, no TypeError was raised
            self.assertTrue(True)
        except TypeError as e:
            if "multiple values for argument 'user'" in str(e):
                self.fail(
                    "Form raised TypeError about multiple values for 'user'. "
                    "This means the bug has regressed. Ensure __init__ signature is "
                    "__init__(*args, user=None, **kwargs)"
                )
            else:
                raise


class SellerAccountSettingsFormCommitTests(TestCase):
    """The settings form only writes to the database when committing."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="commit@example.com",
            username="commit@example.com",
            password="testpass123",
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user,
            defaults={
                "shop_name": "Commit Shop",
                "shop_slug": "commit-shop",
                # The shop name is a store field (paid tiers)
                "tier": "odrzivo",
            },
        )
        self.original_name = self.seller.shop_name

    def _form(self):
        form = SellerAccountSettingsForm(
            data={"shop_name": "Renamed Shop"},
            instance=self.seller,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def test_commit_false_writes_nothing(self):
        self._form().save(commit=False)
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.shop_name, self.original_name)

    def test_save_m2m_after_commit_false_saves_the_seller(self):
        form = self._form()
        seller = form.save(commit=False)
        seller.save()
        form.save_m2m()
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.shop_name, "Renamed Shop")


class SellerTraderConfirmationFormTests(TestCase):
    """Tests for the trader confirmation checkbox on the settings form."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="trader@example.com",
            username="trader@example.com",
            password="testpass123",
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user,
            defaults={"shop_name": "Trader Shop", "shop_slug": "trader-shop"},
        )

    def _save(self, is_trader):
        data = {
            "shop_name": "Trader Shop",
            "email": self.user.email,
        }
        if is_trader:
            data["is_trader"] = "on"
        form = SellerAccountSettingsForm(
            data=data, instance=self.seller, user=self.user
        )
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def test_checking_sets_confirmation_time(self):
        seller = self._save(is_trader=True)
        seller.refresh_from_db()
        self.assertIsNotNone(seller.trader_confirmed_at)
        self.assertEqual(seller.trader_statement, TRADER_STATEMENT)
        self.assertTrue(seller.is_trader)

    def test_resaving_keeps_original_confirmation_time(self):
        confirmed_at = timezone.now() - timedelta(days=10)
        self.seller.trader_confirmed_at = confirmed_at
        self.seller.trader_statement = TRADER_STATEMENT
        self.seller.save()
        seller = self._save(is_trader=True)
        seller.refresh_from_db()
        self.assertEqual(seller.trader_confirmed_at, confirmed_at)

    def test_unchecking_clears_confirmation(self):
        self.seller.confirm_trader()
        self.seller.save()
        seller = self._save(is_trader=False)
        seller.refresh_from_db()
        self.assertIsNone(seller.trader_confirmed_at)
        self.assertEqual(seller.trader_statement, "")
        self.assertFalse(seller.is_trader)

    def test_initial_reflects_confirmation(self):
        form = SellerAccountSettingsForm(instance=self.seller, user=self.user)
        self.assertFalse(form.fields["is_trader"].initial)
        self.seller.confirm_trader()
        self.seller.save()
        form = SellerAccountSettingsForm(instance=self.seller, user=self.user)
        self.assertTrue(form.fields["is_trader"].initial)

    def _confirm_old_wording(self):
        old_time = timezone.now() - timedelta(days=10)
        self.seller.trader_confirmed_at = old_time
        self.seller.trader_statement = "Old wording"
        self.seller.save()
        return old_time

    def test_outdated_confirmation_starts_unticked(self):
        self._confirm_old_wording()
        self.assertTrue(self.seller.trader_statement_outdated)
        form = SellerAccountSettingsForm(instance=self.seller, user=self.user)
        self.assertFalse(form.fields["is_trader"].initial)

    def test_reconfirming_records_new_statement_and_time(self):
        old_time = self._confirm_old_wording()
        seller = self._save(is_trader=True)
        seller.refresh_from_db()
        self.assertEqual(seller.trader_statement, TRADER_STATEMENT)
        self.assertGreater(seller.trader_confirmed_at, old_time)
        self.assertFalse(seller.trader_statement_outdated)
