from django.urls import path

from . import views

urlpatterns = [
    path("", views.my_ratings_view, name="my_ratings"),
    path("sale/<int:sale_id>/", views.rate_sale_view, name="rate_sale"),
    path("<int:rating_id>/reply/", views.rating_reply_view, name="rating_reply"),
    path("<int:rating_id>/report/", views.rating_report_view, name="rating_report"),
]
