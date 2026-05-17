from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/",     admin.site.urls),
    path("accounts/",  include("apps.accounts.urls")),
    path("",           include("apps.camps.urls")),
    path("meals/",     include("apps.meals.urls")),
    path("recipes/",   include("apps.recipes.urls")),
    path("shopping/",  include("apps.shopping.urls")),
    path("feedback/",  include("apps.feedback.urls")),
    path("voting/",    include("apps.voting.urls")),
    path("api/v1/camps/",   include("apps.camps.api_urls")),
    path("api/v1/meals/",   include("apps.meals.api_urls")),
    path("api/v1/recipes/", include("apps.recipes.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
