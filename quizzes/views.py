
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from drf_spectacular.utils import extend_schema, extend_schema_view

from quizzes.models import Quiz, Question, Option, StudentQuizAttempt, StudentQuizAnswer
from quizzes.serializers import (
    QuizSerializer, QuizCreateSerializer, QuizUpdateSerializer,
    QuestionSerializer, QuestionCreateSerializer,
    OptionSerializer, OptionCreateSerializer,
    StudentQuizAttemptSerializer, StudentQuizAttemptCreateSerializer,
    StudentQuizAnswerSerializer, StudentQuizAnswerUpdateSerializer,
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
    list=extend_schema(summary='List questions in a quiz'),
    create=extend_schema(summary='Create a question'),
    partial_update=extend_schema(summary='Update a question'),
)
class QuestionViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return QuestionCreateSerializer
        return QuestionSerializer

    def get_permissions(self):
        if self.action in ['create', 'partial_update']:
            return [permissions.IsAuthenticated(), IsAdminOrApprovedCreator()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if 'quiz_pk' in self.kwargs:
            return Question.objects.filter(quiz_id=self.kwargs['quiz_pk'])
        return Question.objects.all()

    def _get_quiz(self):
        quiz_pk = self.kwargs.get('quiz_pk')
        try:
            return Quiz.objects.select_related('lesson__module__course').get(pk=quiz_pk)
        except Quiz.DoesNotExist:
            raise NotFound('Quiz not found.')

    def list(self, request, *args, **kwargs):
        quiz = self._get_quiz()
        user = request.user
        course = quiz.lesson.module.course

        if user.role == 'ADMIN':
            pass
        elif user.role == 'CREATOR' and user.is_creator_approved and course.creator_id == user.id:
            pass
        elif user.role == 'STUDENT' and course.status in [Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED]:
            pass
        else:
            raise PermissionDenied()

        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        question = self.get_object()
        user = request.user
        course = question.quiz.lesson.module.course

        if user.role == 'ADMIN':
            pass
        elif user.role == 'CREATOR' and user.is_creator_approved and course.creator_id == user.id:
            pass
        elif user.role == 'STUDENT' and course.status in [Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED]:
            pass
        else:
            raise PermissionDenied()

        return Response(self.get_serializer(question).data)

    def perform_create(self, serializer):
        quiz = self._get_quiz()
        course = quiz.lesson.module.course
        user = self.request.user

        if course.status not in [Course.STATUS_DRAFT, Course.STATUS_PUBLISHED]:
            raise ValidationError(f'Cannot add questions to {course.status} course.')
        if user.role == 'CREATOR' and (not user.is_creator_approved or course.creator_id != user.id):
            raise PermissionDenied()
        if user.role == 'STUDENT':
            raise PermissionDenied()

        next_order = Question.objects.filter(quiz=quiz).count() + 1
        serializer.save(quiz=quiz, order=next_order)


@extend_schema_view(
    list=extend_schema(summary='List options for a question'),
    create=extend_schema(summary='Create an option'),
    partial_update=extend_schema(summary='Update an option'),
)
class OptionViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return OptionCreateSerializer
        return OptionSerializer

    def get_permissions(self):
        if self.action in ['create', 'partial_update']:
            return [permissions.IsAuthenticated(), IsAdminOrApprovedCreator()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if 'question_pk' in self.kwargs:
            return Option.objects.filter(question_id=self.kwargs['question_pk'])
        return Option.objects.all()

    def _get_question(self):
        question_pk = self.kwargs.get('question_pk')
        try:
            return Question.objects.select_related('quiz__lesson__module__course').get(pk=question_pk)
        except Question.DoesNotExist:
            raise NotFound('Question not found.')

    def list(self, request, *args, **kwargs):
        question = self._get_question()
        user = request.user
        course = question.quiz.lesson.module.course

        if user.role == 'ADMIN':
            pass
        elif user.role == 'CREATOR' and user.is_creator_approved and course.creator_id == user.id:
            pass
        elif user.role == 'STUDENT' and course.status in [Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED]:
            pass
        else:
            raise PermissionDenied()

        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        option = self.get_object()
        user = request.user
        course = option.question.quiz.lesson.module.course

        if user.role == 'ADMIN':
            pass
        elif user.role == 'CREATOR' and user.is_creator_approved and course.creator_id == user.id:
            pass
        elif user.role == 'STUDENT' and course.status in [Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED]:
            pass
        else:
            raise PermissionDenied()

        return Response(self.get_serializer(option).data)

    def perform_create(self, serializer):
        question = self._get_question()
        course = question.quiz.lesson.module.course
        user = self.request.user

        if course.status not in [Course.STATUS_DRAFT, Course.STATUS_PUBLISHED]:
            raise ValidationError(f'Cannot add options to {course.status} course.')
        if user.role == 'CREATOR' and (not user.is_creator_approved or course.creator_id != user.id):
            raise PermissionDenied()
        if user.role == 'STUDENT':
            raise PermissionDenied()

        serializer.save(question=question)


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
        if self.action == 'update_answers':
            return StudentQuizAnswerUpdateSerializer
        return StudentQuizAttemptSerializer

    def get_permissions(self):
        if self.action in ['create', 'update_answers', 'submit', 'list', 'retrieve']:
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

        # Check enrollment? Maybe we should add that later.
        last_attempt = StudentQuizAttempt.objects.filter(student=user, quiz=quiz).order_by('-attempt_number').first()
        attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1

        attempt = StudentQuizAttempt.objects.create(
            student=user,
            quiz=quiz,
            attempt_number=attempt_number,
            total_questions=quiz.questions.count(),
        )
        return Response(
            StudentQuizAttemptSerializer(attempt).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary='Update answers',
        description='Add or modify answers for an ongoing attempt.'
    )
    @action(detail=True, methods=['patch'], url_path='answers')
    def update_answers(self, request, pk=None):
        attempt = self.get_object()
        if attempt.submitted_at:
            raise ValidationError('Cannot modify a submitted attempt.')

        # Accept a list of answers? For simplicity, let's accept single answer for now.
        # Or maybe a list of {question, option}.
        question_id = request.data.get('question')
        option_id = request.data.get('option')

        try:
            question = Question.objects.get(pk=question_id, quiz=attempt.quiz)
        except Question.DoesNotExist:
            raise ValidationError('Invalid question for this quiz.')

        try:
            option = Option.objects.get(pk=option_id, question=question)
        except Option.DoesNotExist:
            raise ValidationError('Invalid option for this question.')

        with transaction.atomic():
            # Delete any existing answer for this question in this attempt
            StudentQuizAnswer.objects.filter(attempt=attempt, question=question).delete()
            # Create new answer
            answer = StudentQuizAnswer.objects.create(
                attempt=attempt,
                question=question,
                option=option,
                is_correct=option.is_correct,
            )
        return Response(StudentQuizAnswerSerializer(answer).data)

    @extend_schema(
        summary='Submit the attempt',
        description='Finalize the quiz attempt and calculate the score.'
    )
    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        attempt = self.get_object()
        if attempt.submitted_at:
            raise ValidationError('This attempt has already been submitted.')

        with transaction.atomic():
            # Calculate the score
            score = StudentQuizAnswer.objects.filter(attempt=attempt, is_correct=True).count()
            attempt.score = score
            attempt.submitted_at = transaction.now()
            attempt.save()

        return Response(StudentQuizAttemptSerializer(attempt).data)
