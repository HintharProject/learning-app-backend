
from rest_framework import serializers
from django.db import transaction
from courses.models import Course, Module, Lesson, Resource, LessonProgress


# ── Resource Serializers ──────────────────────────────────────────────────────

class ResourceSerializer(serializers.ModelSerializer):
    """Full read/write serializer for Resources."""

    class Meta:
        model = Resource
        fields = [
            'id',
            'lesson',
            'title',
            'type',
            'url',
            'created_at',
        ]
        read_only_fields = ['id', 'lesson', 'created_at']


class ResourceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a Resource — lesson is set from the URL context."""

    class Meta:
        model = Resource
        fields = ['id', 'title', 'type', 'url', 'created_at']
        read_only_fields = ['id', 'created_at']


# ── Lesson Serializers ────────────────────────────────────────────────────────

class LessonSerializer(serializers.ModelSerializer):
    """Full read serializer for a Lesson (includes nested resources)."""
    resources = ResourceSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id',
            'module',
            'title',
            'content',
            'video_url',
            'duration_minutes',
            'order',
            'resources',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'module', 'order', 'resources', 'created_at', 'updated_at']


class LessonListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for lesson lists (no nested resources)."""

    class Meta:
        model = Lesson
        fields = [
            'id',
            'title',
            'video_url',
            'duration_minutes',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'order', 'created_at', 'updated_at']


class LessonCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for adding a new Lesson to a Module.
    'order' is auto-assigned; 'module' is set from URL context.
    """

    class Meta:
        model = Lesson
        fields = [
            'id',
            'title',
            'content',
            'video_url',
            'duration_minutes',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'order', 'created_at', 'updated_at']


class LessonUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for patching a Lesson.
    When a course is PUBLISHED, title and video_url are locked.
    Validation is enforced in the view by checking lifecycle state.
    """

    class Meta:
        model = Lesson
        fields = [
            'id',
            'title',
            'content',
            'video_url',
            'duration_minutes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'order', 'created_at', 'updated_at']

    def validate(self, attrs):
        """
        Enforce post-publication editing restrictions:
        title and video_url cannot be changed once PUBLISHED.
        """
        lesson = self.instance
        if lesson:
            course = lesson.module.course
            if course.status == Course.STATUS_PUBLISHED:
                locked_fields = {'title', 'video_url'}
                changed = locked_fields & set(attrs.keys())
                if changed:
                    raise serializers.ValidationError(
                        {field: 'This field cannot be modified after a course is published.'
                         for field in changed}
                    )
        return attrs


# ── Module Serializers ────────────────────────────────────────────────────────

class ModuleSerializer(serializers.ModelSerializer):
    """Full read serializer for a Module (includes nested lessons)."""
    lessons = LessonListSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = [
            'id',
            'course',
            'title',
            'description',
            'order',
            'lessons',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'course', 'order', 'lessons', 'created_at', 'updated_at']


class ModuleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for module lists (no nested lessons)."""
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = [
            'id',
            'title',
            'description',
            'order',
            'lesson_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'order', 'created_at', 'updated_at']

    def get_lesson_count(self, obj):
        return obj.lessons.count()


class ModuleCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for adding a new Module to a Course.
    'order' is auto-assigned; 'course' is set from URL context.
    """

    class Meta:
        model = Module
        fields = [
            'id',
            'title',
            'description',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'order', 'created_at', 'updated_at']


class ModuleUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for patching a Module.
    When a course is PUBLISHED, title is locked.
    """

    class Meta:
        model = Module
        fields = [
            'id',
            'title',
            'description',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'order', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Enforce post-publication editing restrictions: title is locked."""
        module = self.instance
        if module:
            course = module.course
            if course.status == Course.STATUS_PUBLISHED:
                if 'title' in attrs:
                    raise serializers.ValidationError(
                        {'title': 'Module title cannot be modified after a course is published.'}
                    )
        return attrs


# ── Reorder Serializers ───────────────────────────────────────────────────────

class ReorderSerializer(serializers.Serializer):
    """
    Generic reorder payload: a list of {id, order} pairs.
    Validates that orders are unique, continuous starting at 1.
    """
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text='Ordered list of UUIDs representing the new sequence (index+1 = new order).',
    )

    def validate_ordered_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Duplicate IDs are not allowed.')
        return value


# ── Course Serializers ────────────────────────────────────────────────────────

class CourseSerializer(serializers.ModelSerializer):
    """Full read serializer for a Course (includes nested modules list)."""
    modules = ModuleListSerializer(many=True, read_only=True)
    creator_email = serializers.EmailField(source='creator.email', read_only=True)
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'slug',
            'description',
            'cover_image',
            'creator',
            'creator_email',
            'creator_name',
            'status',
            'modules',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'slug',
            'creator',
            'creator_email',
            'creator_name',
            'status',
            'modules',
            'created_at',
            'updated_at',
        ]


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for course list views."""
    creator_email = serializers.EmailField(source='creator.email', read_only=True)
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)
    module_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'slug',
            'description',
            'cover_image',
            'creator',
            'creator_email',
            'creator_name',
            'status',
            'module_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_module_count(self, obj):
        return obj.modules.count()


class CourseCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new Course (always starts as DRAFT).
    Creator is injected from the request user in the view.
    """

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'description',
            'cover_image',
            'slug',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'status', 'created_at', 'updated_at']


class CourseUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for patching a Course.
    Post-publication: title and description are locked.
    """

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'description',
            'cover_image',
            'slug',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'status', 'created_at', 'updated_at']

    def validate(self, attrs):
        course = self.instance
        if course and course.status == Course.STATUS_PUBLISHED:
            locked_fields = {'title', 'description'}
            changed = locked_fields & set(attrs.keys())
            if changed:
                raise serializers.ValidationError(
                    {field: 'This field cannot be modified after a course is published.'
                     for field in changed}
                )
        if course and course.status == Course.STATUS_PENDING:
            raise serializers.ValidationError(
                'This course is pending approval and cannot be edited. '
                'Reject the course to return it to Draft.'
            )
        return attrs


# ── LessonProgress Serializers ────────────────────────────────────────────────

class LessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = [
            'id',
            'student',
            'lesson',
            'video_progress',
            'completed',
            'updated_at',
        ]
        read_only_fields = ['id', 'student', 'lesson', 'updated_at']


class LessonProgressUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = ['video_progress']

    def validate_video_progress(self, value):
        if value < 0 or value > 1:
            raise serializers.ValidationError('Video progress must be between 0 and 1.')
        return value
