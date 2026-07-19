from django.urls import path, include
from rest_framework.routers import DefaultRouter
from quizzes.views import QuizViewSet, StudentQuizAttemptViewSet


router = DefaultRouter()
router.register(r'quizzes', QuizViewSet, basename='quiz')
router.register(r'attempts', StudentQuizAttemptViewSet, basename='quiz-attempt')


urlpatterns = [
    # Nested URLs under lessons
    path('lessons/<uuid:lesson_pk>/quizzes/', QuizViewSet.as_view({'get': 'list', 'post': 'create'}), name='lesson-quiz-list'),

    # Nested URLs under quizzes
    path('quizzes/<uuid:quiz_pk>/attempts/', StudentQuizAttemptViewSet.as_view({'get': 'list', 'post': 'create'}), name='quiz-attempt-list'),

    # Router-generated flat URLs
    path('', include(router.urls)),
]
