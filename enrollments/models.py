
import uuid
from django.db import models
from django.conf import settings
from courses.models import Course


class Enrollment(models.Model):
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_DROPPED = 'DROPPED'
    STATUS_COMPLETED = 'COMPLETED'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DROPPED, 'Dropped'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='enrollments'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name='enrollments'
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE
    )

    class Meta:
        db_table = 'enrollments'
        ordering = ['-enrolled_at']
        unique_together = [('student', 'course')]

    def __str__(self):
        return f'{self.student.email} enrolled in {self.course.title} ({self.status})'
