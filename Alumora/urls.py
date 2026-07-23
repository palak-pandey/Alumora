"""
URL configuration for Alumora project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve as static_serve

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # accounts app URLs
    path('', include('accounts.urls')),
]

# Media routes for Render production.
# NOTE: Django's `static()` helper from django.conf.urls.static is a no-op
# whenever settings.DEBUG is False, so on Render (DEBUG=False) it was adding
# NO url pattern at all for /media/, which is why every profile pic /
# cover photo / degree certificate was 404ing (shown as broken images).
# We serve media explicitly here regardless of DEBUG.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', static_serve, {'document_root': settings.MEDIA_ROOT}),
]
# Static files are already served in production by WhiteNoise middleware,
# so no extra route is needed for STATIC_URL here.