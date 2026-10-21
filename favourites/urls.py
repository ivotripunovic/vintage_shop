from django.urls import path

from . import views

urlpatterns = [
    path(
        "seller/<int:seller_id>/",
        views.favourite_seller_toggle,
        name="favourite_seller_toggle",
    ),
    path("product/<int:product_id>/", views.wishlist_toggle, name="wishlist_toggle"),
]
