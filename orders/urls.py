from django.urls import path

from . import views

urlpatterns = [
    path(
        "product/<int:product_id>/sold/",
        views.product_mark_sold_view,
        name="product_mark_sold",
    ),
]
