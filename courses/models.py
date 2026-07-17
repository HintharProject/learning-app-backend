import uuid
from django.db import models
from django.utils.text import slugify
from django.conf import settings


class Course(models.Model):
    """
    Represents a course created by a Creator.
    Lifecycle: DRAFT → PENDING_APPROVAL → PUBLISHED → ARCHIVED
    """
    STATUS_DRAFT = 'DRAFT'
    STATUS_PENDING = 'PENDING_APPROVAL'
    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_ARCHIVED = 'ARCHIVED'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_ARCHIVED, 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, default='')
    cover_image = models.URLField(max_length=500, blank=True, null=True)
    # PROTECTED: do not cascade-delete courses if a creator user is removed.
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_courses',
        limit_choices_to={'role': 'CREATOR'},
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Auto-generate slug from title on creation only.
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    # ── State-transition helpers ──────────────────────────────────────────
    @property
    def is_editable(self):
        """Fully editable only in DRAFT state."""
        return self.status == self.STATUS_DRAFT

    @property
    def is_published(self):
        return self.status == self.STATUS_PUBLISHED

    def __str__(self):
        return f'{self.title} [{self.status}]'


class Module(models.Model):
    """
    An ordered section within a Course.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECTED: prevents accidental module removal when a course is deleted
    # while enrollments/progress records exist.
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name='modules',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'modules'
        ordering = ['order']
        # Ordering must be unique per course.
        unique_together = [('course', 'order')]

    def __str__(self):
        return f'[{self.order}] {self.title} (Course: {self.course_id})'


class Lesson(models.Model):
    """
    An ordered piece of content within a Module.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECTED: prevents accidental lesson removal when historical progress records exist.
    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        related_name='lessons',
    )
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default='')
    video_url = models.URLField(max_length=500, blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lessons'
        ordering = ['order']
        # Ordering must be unique per module.
        unique_together = [('module', 'order')]

    def __str__(self):
        return f'[{self.order}] {self.title} (Module: {self.module_id})'


class Resource(models.Model):
    """
    A supplementary resource attached to a Lesson (PDF, image, link, etc.).
    """
    TYPE_PDF = 'PDF'
    TYPE_IMAGE = 'IMAGE'
    TYPE_LINK = 'LINK'
    TYPE_ZIP = 'ZIP'
    TYPE_DOCUMENT = 'DOCUMENT'

    TYPE_CHOICES = [
        (TYPE_PDF, 'PDF'),
        (TYPE_IMAGE, 'Image'),
        (TYPE_LINK, 'Link'),
        (TYPE_ZIP, 'ZIP'),
        (TYPE_DOCUMENT, 'Document'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECTED: resources are content-level; do not cascade on lesson removal.
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.PROTECT,
        related_name='resources',
    )
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'resources'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.title} ({self.type}) — Lesson: {self.lesson_id}'


class LessonProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='lesson_progress'
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.PROTECT,
        related_name='progress'
    )
    video_progress = models.FloatField(default=0.0)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lesson_progress'
        ordering = ['-updated_at']
        unique_together = [('student', 'lesson')]

    def __str__(self):
        return f'Progress for {self.student.email} on {self.lesson.title} ({"Completed" if self.completed else "In Progress"})'
