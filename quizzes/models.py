
import uuid
from django.db import models
from django.conf import settings
from courses.models import Lesson


class Quiz(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.PROTECT,
        related_name='quizzes'
    )
    description = models.TextField(blank=True, default='')
    passing_percentage = models.PositiveIntegerField(default=80)
    questions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quizzes'
        ordering = ['-created_at']

    def __str__(self):
        return f'Quiz for Lesson: {self.lesson.title}'


class StudentQuizAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='quiz_attempts'
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.PROTECT,
        related_name='attempts'
    )
    attempt_number = models.PositiveIntegerField()
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    
    score = models.PositiveIntegerField(blank=True, null=True)
    total_questions = models.PositiveIntegerField(blank=True, null=True)
    passed = models.BooleanField(default=False)
    answers_submitted = models.JSONField(default=dict)
    questions_snapshot = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_quiz_attempts'
        ordering = ['-created_at']
        unique_together = [('student', 'quiz', 'attempt_number')]

    @property
    def is_submitted(self):
        return self.submitted_at is not None

    def __str__(self):
        return f'Attempt {self.attempt_number} for {self.student.email} on Quiz {self.quiz_id}'
