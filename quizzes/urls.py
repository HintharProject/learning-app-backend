
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from quizzes.views import QuizViewSet, QuestionViewSet, OptionViewSet, StudentQuizAttemptViewSet


router = DefaultRouter()
router.register(r'quizzes', QuizViewSet, basename='quiz')
router.register(r'questions', QuestionViewSet, basename='question')
router.register(r'options', OptionViewSet, basename='option')
router.register(r'attempts', StudentQuizAttemptViewSet, basename='quiz-attempt')


urlpatterns = [
    # Nested URLs under lessons
    path('lessons/<uuid:lesson_pk>/quizzes/', QuizViewSet.as_view({'get': 'list', 'post': 'create'}), name='lesson-quiz-list'),

    # Nested URLs under quizzes
    path('quizzes/<uuid:quiz_pk>/questions/', QuestionViewSet.as_view({'get': 'list', 'post': 'create'}), name='quiz-question-list'),
    path('quizzes/<uuid:quiz_pk>/attempts/', StudentQuizAttemptViewSet.as_view({'get': 'list', 'post': 'create'}), name='quiz-attempt-list'),

    # Nested URLs under questions
    path('questions/<uuid:question_pk>/options/', OptionViewSet.as_view({'get': 'list', 'post': 'create'}), name='question-option-list'),

    # Router-generated flat URLs
    path('', include(router.urls)),
]
