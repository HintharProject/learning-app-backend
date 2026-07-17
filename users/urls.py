from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import UserViewSet, clerk_webhook

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('clerk/webhook/', clerk_webhook, name='clerk-webhook'),
    path('', include(router.urls)),
]
