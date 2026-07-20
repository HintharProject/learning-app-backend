
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

        # Prevent duplicate entries within the same study plan
        existing = StudyPlanItem.objects.filter(study_plan=self.study_plan)
        if self.pk:
            existing = existing.exclude(pk=self.pk)

        if self.course:
            if existing.filter(course=self.course).exists():
                raise ValidationError('This course is already in the study plan.')
            # Hierarchy check: a Course and its child Modules/Lessons cannot coexist
            child_modules = Module.objects.filter(course=self.course).values_list('id', flat=True)
            child_lessons = Lesson.objects.filter(module__course=self.course).values_list('id', flat=True)
            if existing.filter(module_id__in=child_modules).exists():
                raise ValidationError(
                    'This course cannot be added because one of its modules is already in the study plan.'
                )
            if existing.filter(lesson_id__in=child_lessons).exists():
                raise ValidationError(
                    'This course cannot be added because one of its lessons is already in the study plan.'
                )

        elif self.module:
            if existing.filter(module=self.module).exists():
                raise ValidationError('This module is already in the study plan.')
            # Hierarchy check: a Module and its parent Course or child Lessons cannot coexist
            if existing.filter(course=self.module.course).exists():
                raise ValidationError(
                    'This module cannot be added because its parent course is already in the study plan.'
                )
            child_lessons = Lesson.objects.filter(module=self.module).values_list('id', flat=True)
            if existing.filter(lesson_id__in=child_lessons).exists():
                raise ValidationError(
                    'This module cannot be added because one of its lessons is already in the study plan.'
                )

        elif self.lesson:
            if existing.filter(lesson=self.lesson).exists():
                raise ValidationError('This lesson is already in the study plan.')
            # Hierarchy check: a Lesson and its parent Course or Module cannot coexist
            parent_module = self.lesson.module
            if existing.filter(module=parent_module).exists():
                raise ValidationError(
                    'This lesson cannot be added because its parent module is already in the study plan.'
                )
            parent_course = parent_module.course
            if existing.filter(course=parent_course).exists():
                raise ValidationError(
                    'This lesson cannot be added because its parent course is already in the study plan.'
                )

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
