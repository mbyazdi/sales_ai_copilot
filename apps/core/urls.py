from django.urls import path

from .views import role_home


urlpatterns = [
    path(
        "",
        role_home,
        name="role-home",
    ),
]