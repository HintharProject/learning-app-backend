
import uuid
from django.db import models
from django.conf import settings
from courses.models import Course, Module, Lesson


class StudyPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='study_plans'
    )
    title = models.CharField(max_length=255)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'study_plans'
        ordering = ['-created_at']

    def __str__(self):
        return f'Study Plan: {self.title} for {self.student.email}'


class StudyPlanItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    study_plan = models.ForeignKey(
        StudyPlan,
        on_delete=models.CASCADE,
        related_name='items'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='+',
        blank=True,
        null=True
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='+',
        blank=True,
        null=True
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='+',
        blank=True,
        null=True
    )
    scheduled_date = models.DateField(blank=True, null=True)
    order = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'study_plan_items'
        ordering = ['order']
        unique_together = [('study_plan', 'order')]

    def clean(self):
        from django.core.exceptions import ValidationError

        # Exactly one of course, module, lesson must be set
        count = sum([
            1 for x in [self.course, self.module, self.lesson] if x is not None
        ])
        if count != 1:
            raise ValidationError('Exactly one of course, module, or lesson must be specified.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.course:
            ref = f'Course: {self.course.title}'
        elif self.module:
            ref = f'Module: {self.module.title}'
        elif self.lesson:
            ref = f'Lesson: {self.lesson.title}'
        else:
            ref = 'No Reference'
        return f'Item {self.order}: {ref} in Study Plan {self.study_plan_id}'
