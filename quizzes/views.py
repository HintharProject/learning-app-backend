
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from drf_spectacular.utils import extend_schema, extend_schema_view

from quizzes.models import Quiz, StudentQuizAttempt
from quizzes.serializers import (
    QuizSerializer, QuizCreateSerializer, QuizUpdateSerializer,
    StudentQuizAttemptSerializer, StudentQuizAttemptCreateSerializer,
)
from courses.permissions import IsAdminOrApprovedCreator, IsCourseOwnerOrAdmin
from users.permissions import IsStudent
from courses.models import Lesson, Course


@extend_schema_view(
    list=extend_schema(
        summary='List quizzes in a lesson',
        description='Get all quizzes for a specific lesson.'
    ),
    create=extend_schema(
        summary='Create a quiz',
        description='Add a quiz to a lesson.'
    ),
    partial_update=extend_schema(
        summary='Update a quiz',
        description='Modify a quiz (only if course is draft or published).'
    ),
)
class QuizViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return QuizCreateSerializer
        if self.action == 'partial_update':
            return QuizUpdateSerializer
        return QuizSerializer

    def get_permissions(self):
        if self.action in ['create', 'partial_update']:
            return [permissions.IsAuthenticated(), IsAdminOrApprovedCreator()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if 'lesson_pk' in self.kwargs:
            return Quiz.objects.filter(lesson_id=self.kwargs['lesson_pk'])
        return Quiz.objects.all()

    def _get_lesson(self):
        lesson_pk = self.kwargs.get('lesson_pk')
        try:
            return Lesson.objects.select_related('module__course').get(pk=lesson_pk)
        except Lesson.DoesNotExist:
            raise NotFound('Lesson not found.')

    def _check_lesson_permission(self, lesson):
        user = self.request.user
        course = lesson.module.course
        if user.role == 'ADMIN':
            return
        if user.role == 'CREATOR' and user.is_creator_approved and course.creator_id == user.id:
            return
        if user.role == 'STUDENT' and course.status in [Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED]:
            return
        raise PermissionDenied('You do not have permission to access this lesson.')

    def list(self, request, *args, **kwargs):
        lesson = self._get_lesson()
        self._check_lesson_permission(lesson)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        quiz = self.get_object()
        self._check_lesson_permission(quiz.lesson)
        return Response(self.get_serializer(quiz).data)

    def perform_create(self, serializer):
        lesson = self._get_lesson()
        course = lesson.module.course
        user = self.request.user

        if course.status not in [Course.STATUS_DRAFT, Course.STATUS_PUBLISHED]:
            raise ValidationError(f'Cannot add quiz to {course.status} course.')
        if user.role == 'CREATOR' and (not user.is_creator_approved or course.creator_id != user.id):
            raise PermissionDenied('You are not allowed to add quizzes to this course.')
        if user.role == 'STUDENT':
            raise PermissionDenied('Students cannot create quizzes.')

        serializer.save(lesson=lesson)


@extend_schema_view(
    list=extend_schema(
        summary='List quiz attempts',
        description='Get all attempts for a quiz (only for the student or admin).'
    ),
    create=extend_schema(
        summary='Start a quiz attempt',
        description='Begin a new attempt for a quiz.'
    ),
    retrieve=extend_schema(
        summary='Get a quiz attempt',
        description='Get details of a specific quiz attempt.'
    ),
)
class StudentQuizAttemptViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return StudentQuizAttemptCreateSerializer
        return StudentQuizAttemptSerializer

    def get_permissions(self):
        if self.action in ['create', 'submit', 'list', 'retrieve']:
            return [permissions.IsAuthenticated(), IsStudent()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if 'quiz_pk' in self.kwargs:
            return StudentQuizAttempt.objects.filter(student=user, quiz_id=self.kwargs['quiz_pk'])
        return StudentQuizAttempt.objects.filter(student=user)

    def _get_quiz(self):
        quiz_pk = self.kwargs.get('quiz_pk')
        try:
            return Quiz.objects.select_related('lesson__module__course').get(pk=quiz_pk)
        except Quiz.DoesNotExist:
            raise NotFound('Quiz not found.')

    def create(self, request, *args, **kwargs):
        quiz = self._get_quiz()
        course = quiz.lesson.module.course
        user = request.user

        if course.status not in [Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED]:
            raise PermissionDenied('Quiz is not available yet.')

        last_attempt = StudentQuizAttempt.objects.filter(student=user, quiz=quiz).order_by('-attempt_number').first()
        attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1

        # total_questions is stored for attempt context
        attempt = StudentQuizAttempt.objects.create(
            student=user,
            quiz=quiz,
            attempt_number=attempt_number,
            total_questions=len(quiz.questions) if isinstance(quiz.questions, list) else 0,
        )
        return Response(
            StudentQuizAttemptSerializer(attempt).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary='Submit the attempt',
        description='Finalize the quiz attempt with answers and calculate the score.'
    )
    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        attempt = self.get_object()
        if attempt.submitted_at:
            raise ValidationError('This attempt has already been submitted.')

        answers_submitted = request.data.get('answers', {})
        if not isinstance(answers_submitted, dict):
            raise ValidationError('Answers must be a dictionary of question_id: option_id.')

        quiz_questions = attempt.quiz.questions
        score = 0
        total_questions = len(quiz_questions) if isinstance(quiz_questions, list) else 0

        if isinstance(quiz_questions, list):
            for q in quiz_questions:
                q_id = str(q.get('id'))
                submitted_option_id = str(answers_submitted.get(q_id))
                
                correct_option = next((opt for opt in q.get('options', []) if opt.get('is_correct')), None)
                if correct_option and str(correct_option.get('id')) == submitted_option_id:
                    score += 1

        passed = False
        if total_questions > 0:
            percentage = (score / total_questions) * 100
            passed = percentage >= attempt.quiz.passing_percentage
        else:
            passed = True

        with transaction.atomic():
            attempt.score = score
            attempt.total_questions = total_questions
            attempt.passed = passed
            attempt.answers_submitted = answers_submitted
            attempt.submitted_at = timezone.now()
            attempt.save()

        return Response(StudentQuizAttemptSerializer(attempt).data)
