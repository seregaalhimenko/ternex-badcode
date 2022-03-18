from django.urls import path
from . import views


urlpatterns = [
    path("", views.index),
    path("landing-form/", views.landing_form),
    path("hotels/", views.hotels),
    path("franchise/", views.franchise),
    path("consumers/", views.consumers),
]
