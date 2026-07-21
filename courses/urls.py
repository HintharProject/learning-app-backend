from django.urls import path, include
from rest_framework.routers import DefaultRouter
from courses.views import (
    CourseViewSet,
    ModuleViewSet,
    ModuleDetailViewSet,
    LessonViewSet,
    ResourceViewSet,
    LessonProgressViewSet,
    TagViewSet,
)

router = DefaultRouter()

# /api/v1/courses/
router.register(r'courses', CourseViewSet, basename='course')

# /api/v1/tags/
router.register(r'tags', TagViewSet, basename='tag')

# /api/v1/modules/{id}/ — standalone PATCH only
router.register(r'modules', ModuleDetailViewSet, basename='module-detail')

# /api/v1/lessons/{id}/ — retrieve + PATCH
router.register(r'lessons', LessonViewSet, basename='lesson')

# /api/v1/resources/{id}/ — PATCH only
router.register(r'resources', ResourceViewSet, basename='resource')

urlpatterns = [
    # ── Nested routes ──────────────────────────────────────────────────────
    # GET  /api/v1/courses/{course_pk}/modules/
    # POST /api/v1/courses/{course_pk}/modules/
    # POST /api/v1/courses/{course_pk}/modules/reorder/
    path(
        'courses/<uuid:course_pk>/modules/',
        ModuleViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='course-modules-list',
    ),
    path(
        'courses/<uuid:course_pk>/modules/reorder/',
        ModuleViewSet.as_view({'post': 'reorder'}),
        name='course-modules-reorder',
    ),

    # GET  /api/v1/modules/{module_pk}/lessons/
    # POST /api/v1/modules/{module_pk}/lessons/
    # POST /api/v1/modules/{module_pk}/lessons/reorder/
    path(
        'modules/<uuid:module_pk>/lessons/',
        LessonViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='module-lessons-list',
    ),
    path(
        'modules/<uuid:module_pk>/lessons/reorder/',
        LessonViewSet.as_view({'post': 'reorder'}),
        name='module-lessons-reorder',
    ),

    # GET  /api/v1/lessons/{lesson_pk}/resources/
    # POST /api/v1/lessons/{lesson_pk}/resources/
    path(
        'lessons/<uuid:lesson_pk>/resources/',
        ResourceViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='lesson-resources-list',
    ),

    # GET   /api/v1/lessons/{lesson_pk}/progress/
    # PATCH /api/v1/lessons/{lesson_pk}/progress/
    path(
        'lessons/<uuid:lesson_pk>/progress/',
        LessonProgressViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update'}),
        name='lesson-progress',
    ),
    # POST  /api/v1/lessons/{lesson_pk}/progress/reset/
    path(
        'lessons/<uuid:lesson_pk>/progress/reset/',
        LessonProgressViewSet.as_view({'post': 'reset'}),
        name='lesson-progress-reset',
    ),

    # ── Router-generated flat routes ──────────────────────────────────────
    path('', include(router.urls)),
]
