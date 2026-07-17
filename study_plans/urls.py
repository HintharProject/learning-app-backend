
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from study_plans.views import StudyPlanViewSet, StudyPlanItemViewSet

router = DefaultRouter()
router.register(r'study-plans', StudyPlanViewSet, basename='study-plan')
router.register(r'study-plan-items', StudyPlanItemViewSet, basename='study-plan-item')


urlpatterns = [
    # Nested routes for study plan items
    path(
        'study-plans/<uuid:study_plan_pk>/items/',
        StudyPlanItemViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='study-plan-item-list',
    ),
    path('', include(router.urls)),
]
