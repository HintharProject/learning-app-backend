
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from enrollments.views import EnrollmentViewSet, AdminEnrollmentViewSet

router = DefaultRouter()
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')

urlpatterns = [
    # Student-facing enrollment routes (via router)
    path('', include(router.urls)),

    # Admin enrollment routes
    path(
        'admin/enrollments/',
        AdminEnrollmentViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='admin-enrollments',
    ),
]
