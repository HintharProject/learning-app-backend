from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from courses.models import Course, Module, Lesson, Resource, LessonProgress
from courses.serializers import (
    CourseSerializer,
    CourseListSerializer,
    CourseCreateSerializer,
    CourseUpdateSerializer,
    ModuleSerializer,
    ModuleListSerializer,
    ModuleCreateSerializer,
    ModuleUpdateSerializer,
    LessonSerializer,
    LessonListSerializer,
    LessonCreateSerializer,
    LessonUpdateSerializer,
    ResourceSerializer,
    ResourceCreateSerializer,
    ReorderSerializer,
    LessonProgressSerializer,
    LessonProgressUpdateSerializer,
)
from courses.permissions import (
    IsAdminOrApprovedCreator,
    IsCourseOwnerOrAdmin,
    CanAddContentToCourse,
)
from users.permissions import IsAdmin


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_next_order(queryset):
    """Returns max(order) + 1 for a given queryset, starting at 1."""
    last = queryset.order_by('-order').first()
    return (last.order + 1) if last else 1


def _apply_reorder(model_class, scope_field, scope_id, ordered_ids):
    """
    Atomically reorder items within a scope.
    ordered_ids: list of UUIDs in the desired order (index 0 → order=1).
    Raises ValidationError if any ID is not in the scope.
    """
    qs = model_class.objects.filter(**{scope_field: scope_id})
    existing_ids = set(str(obj.id) for obj in qs)
    incoming_ids = [str(uid) for uid in ordered_ids]

    if set(incoming_ids) != existing_ids:
        raise ValidationError(
            {'ordered_ids': 'The provided IDs must exactly match the existing items in this scope.'}
        )

    with transaction.atomic():
        from django.db.models import F
        model_class.objects.filter(id__in=incoming_ids).update(order=F('order') + 100000)
        for new_order, item_id in enumerate(incoming_ids, start=1):
            model_class.objects.filter(id=item_id).update(order=new_order)


# ── CourseViewSet ─────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary='List courses',
        description=(
            'Students see only PUBLISHED courses. '
            'Creators see their own courses (all statuses). '
            'Admins see all courses.'
        ),
    ),
    retrieve=extend_schema(
        summary='Retrieve course details',
        description='Full course detail with nested modules.',
    ),
    create=extend_schema(
        summary='Create a new draft course',
        description='Creates a course in DRAFT state. Requires approved Creator or Admin.',
    ),
    partial_update=extend_schema(
        summary='Update course info',
        description='Modify course metadata (subject to lifecycle editing restrictions).',
    ),
    update=extend_schema(exclude=True),
    destroy=extend_schema(exclude=True),
)
class CourseViewSet(viewsets.ModelViewSet):
    """
    Course management:
    - GET  /courses/          → list
    - POST /courses/          → create (approved Creator or Admin)
    - GET  /courses/{id}/     → retrieve
    - PATCH /courses/{id}/    → update (owner or Admin)
    - POST /courses/{id}/submit-review/
    - POST /courses/{id}/approve/
    - POST /courses/{id}/reject/
    - POST /courses/{id}/archive/
    """
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Course.objects.none()
        if user.role == 'ADMIN':
            return Course.objects.all().select_related('creator')
        if user.role == 'CREATOR':
            return Course.objects.filter(creator=user).select_related('creator')
        # STUDENT: only published courses
        return Course.objects.filter(status=Course.STATUS_PUBLISHED).select_related('creator')

    def get_permissions(self):
        if self.action == 'list':
            return [permissions.IsAuthenticated()]
        if self.action == 'retrieve':
            return [permissions.IsAuthenticated()]
        if self.action == 'create':
            return [IsAdminOrApprovedCreator()]
        if self.action in ('partial_update', 'submit_review', 'archive'):
            return [permissions.IsAuthenticated(), IsCourseOwnerOrAdmin()]
        if self.action in ('approve', 'reject'):
            return [IsAdmin()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        if self.action == 'create':
            return CourseCreateSerializer
        if self.action == 'partial_update':
            return CourseUpdateSerializer
        return CourseSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user, status=Course.STATUS_DRAFT)

    def retrieve(self, request, *args, **kwargs):
        """
        Students can only retrieve PUBLISHED courses.
        Owners and Admins can view any status.
        """
        course = self.get_object()
        user = request.user
        if user.role == 'STUDENT' and course.status != Course.STATUS_PUBLISHED:
            raise PermissionDenied('This course is not yet published.')
        if user.role == 'CREATOR' and course.creator_id != user.id:
            raise PermissionDenied('You do not have permission to view this course.')
        serializer = self.get_serializer(course)
        return Response(serializer.data)

    # ── Lifecycle actions ─────────────────────────────────────────────────

    @extend_schema(
        summary='Submit course for review',
        description='Transitions a DRAFT course to PENDING_APPROVAL.',
        request=None,
        responses={200: CourseSerializer},
    )
    @action(detail=True, methods=['post'], url_path='submit-review')
    def submit_review(self, request, pk=None):
        course = self.get_object()
        self.check_object_permissions(request, course)
        if course.status != Course.STATUS_DRAFT:
            raise ValidationError('Only DRAFT courses can be submitted for review.')
        course.status = Course.STATUS_PENDING
        course.save(update_fields=['status', 'updated_at'])
        return Response(CourseSerializer(course).data)

    @extend_schema(
        summary='Approve course publication',
        description='Transitions a PENDING_APPROVAL course to PUBLISHED. Admin only.',
        request=None,
        responses={200: CourseSerializer},
    )
    @action(detail=True, methods=['post'], url_path='approve', permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        course = self.get_object()
        if course.status != Course.STATUS_PENDING:
            raise ValidationError('Only PENDING_APPROVAL courses can be approved.')
        course.status = Course.STATUS_PUBLISHED
        course.save(update_fields=['status', 'updated_at'])
        return Response(CourseSerializer(course).data)

    @extend_schema(
        summary='Reject course — return to Draft',
        description='Returns a PENDING_APPROVAL course to DRAFT state. Admin only.',
        request=None,
        responses={200: CourseSerializer},
    )
    @action(detail=True, methods=['post'], url_path='reject', permission_classes=[IsAdmin])
    def reject(self, request, pk=None):
        course = self.get_object()
        if course.status != Course.STATUS_PENDING:
            raise ValidationError('Only PENDING_APPROVAL courses can be rejected.')
        course.status = Course.STATUS_DRAFT
        course.save(update_fields=['status', 'updated_at'])
        return Response(CourseSerializer(course).data)

    @extend_schema(
        summary='Archive course',
        description='Transitions a PUBLISHED course to ARCHIVED. Admin or owner Creator.',
        request=None,
        responses={200: CourseSerializer},
    )
    @action(detail=True, methods=['post'], url_path='archive')
    def archive(self, request, pk=None):
        course = self.get_object()
        self.check_object_permissions(request, course)
        if course.status != Course.STATUS_PUBLISHED:
            raise ValidationError('Only PUBLISHED courses can be archived.')
        course.status = Course.STATUS_ARCHIVED
        course.save(update_fields=['status', 'updated_at'])
        return Response(CourseSerializer(course).data)


# ── ModuleViewSet ─────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary='List modules in a course',
        description='Returns all modules ordered by their position.',
    ),
    create=extend_schema(
        summary='Add a module to a course',
        description='Creates a new module at the end of the existing sequence.',
    ),
    partial_update=extend_schema(
        summary='Update module details',
        description='Modify module info (subject to lifecycle editing restrictions).',
    ),
    update=extend_schema(exclude=True),
    retrieve=extend_schema(exclude=True),
    destroy=extend_schema(exclude=True),
)
class ModuleViewSet(viewsets.ModelViewSet):
    """
    Nested under /courses/{course_pk}/modules/ and /modules/{id}/.
    - GET  /courses/{course_pk}/modules/          → list
    - POST /courses/{course_pk}/modules/          → create
    - PATCH /modules/{id}/                        → partial_update
    - POST /courses/{course_pk}/modules/reorder/  → reorder
    """
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def _get_course(self):
        course_pk = self.kwargs.get('course_pk')
        try:
            return Course.objects.get(pk=course_pk)
        except Course.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Course not found.')

    def get_queryset(self):
        if 'course_pk' in self.kwargs:
            course = self._get_course()
            self._check_course_read_permission(course)
            return Module.objects.filter(course=course).prefetch_related('lessons')
        return Module.objects.all().select_related('course')

    def _check_course_read_permission(self, course):
        user = self.request.user
        if user.role == 'STUDENT' and course.status not in (
            Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED
        ):
            raise PermissionDenied('This course is not accessible.')
        if user.role == 'CREATOR' and course.creator_id != user.id:
            raise PermissionDenied('You do not have permission to view this course.')

    def get_permissions(self):
        if self.action == 'list':
            return [permissions.IsAuthenticated()]
        if self.action == 'create':
            return [IsAdminOrApprovedCreator()]
        if self.action in ('partial_update', 'reorder'):
            return [permissions.IsAuthenticated(), IsCourseOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return ModuleListSerializer
        if self.action == 'create':
            return ModuleCreateSerializer
        if self.action == 'partial_update':
            return ModuleUpdateSerializer
        return ModuleSerializer

    def perform_create(self, serializer):
        course = self._get_course()
        user = self.request.user

        if course.status == Course.STATUS_PENDING:
            raise ValidationError('Modules cannot be added while the course is pending approval.')
        if course.status == Course.STATUS_ARCHIVED:
            raise ValidationError('Modules cannot be added to an archived course.')
        if user.role == 'CREATOR' and course.creator_id != user.id:
            raise PermissionDenied('You are not the owner of this course.')

        next_order = _get_next_order(Module.objects.filter(course=course))
        serializer.save(course=course, order=next_order)

    @extend_schema(
        summary='Reorder modules',
        description=(
            'Provide the full ordered list of module UUIDs for this course. '
            'Orders are reassigned 1 to N in the given sequence.'
        ),
        request=ReorderSerializer,
        responses={200: ModuleListSerializer(many=True)},
    )
    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request, course_pk=None):
        course = self._get_course()
        self.check_object_permissions(request, course)

        user = request.user
        if user.role == 'CREATOR' and course.creator_id != user.id:
            raise PermissionDenied('You are not the owner of this course.')
        if course.status not in (Course.STATUS_DRAFT, Course.STATUS_PUBLISHED):
            raise ValidationError('Modules can only be reordered in DRAFT or PUBLISHED courses.')

        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ordered_ids = serializer.validated_data['ordered_ids']

        _apply_reorder(Module, 'course_id', course.pk, ordered_ids)
        modules = Module.objects.filter(course=course).order_by('order')
        return Response(ModuleListSerializer(modules, many=True).data)


# ── Standalone ModuleDetailViewSet ────────────────────────────────────────────

class ModuleDetailViewSet(viewsets.GenericViewSet):
    """
    Standalone viewset for /modules/{id}/ — PATCH only.
    """
    queryset = Module.objects.all().select_related('course')
    serializer_class = ModuleUpdateSerializer
    http_method_names = ['patch', 'head', 'options']
    permission_classes = [permissions.IsAuthenticated, IsCourseOwnerOrAdmin]

    @extend_schema(
        summary='Update module details',
        description='Modify module metadata (title/description). Title is locked when PUBLISHED.',
        responses={200: ModuleSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        module = self.get_object()
        self.check_object_permissions(request, module)
        serializer = self.get_serializer(module, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ModuleSerializer(module).data)


# ── LessonViewSet ─────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary='List lessons in a module',
        description='Returns all lessons ordered by their position.',
    ),
    create=extend_schema(
        summary='Add a lesson to a module',
        description='Creates a new lesson at the end of the module sequence.',
    ),
    update=extend_schema(exclude=True),
    destroy=extend_schema(exclude=True),
)
class LessonViewSet(viewsets.ModelViewSet):
    """
    Nested under /modules/{module_pk}/lessons/ and /lessons/{id}/.
    - GET  /modules/{module_pk}/lessons/          → list
    - POST /modules/{module_pk}/lessons/          → create
    - GET  /lessons/{id}/                         → retrieve
    - PATCH /lessons/{id}/                        → partial_update
    - POST /modules/{module_pk}/lessons/reorder/  → reorder
    """
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def _get_module(self):
        module_pk = self.kwargs.get('module_pk')
        try:
            return Module.objects.select_related('course').get(pk=module_pk)
        except Module.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Module not found.')

    def get_queryset(self):
        if 'module_pk' in self.kwargs:
            module = self._get_module()
            self._check_course_read_permission(module.course)
            return Lesson.objects.filter(module=module).prefetch_related('resources')
        return Lesson.objects.all().select_related('module__course').prefetch_related('resources')

    def _check_course_read_permission(self, course):
        user = self.request.user
        if user.role == 'STUDENT' and course.status not in (
            Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED
        ):
            raise PermissionDenied('This course is not accessible.')
        if user.role == 'CREATOR' and course.creator_id != user.id:
            raise PermissionDenied('You do not have permission to view this course.')

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.IsAuthenticated()]
        if self.action == 'create':
            return [IsAdminOrApprovedCreator()]
        if self.action in ('partial_update', 'reorder'):
            return [permissions.IsAuthenticated(), IsCourseOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return LessonListSerializer
        if self.action == 'create':
            return LessonCreateSerializer
        if self.action == 'partial_update':
            return LessonUpdateSerializer
        return LessonSerializer

    def retrieve(self, request, *args, **kwargs):
        lesson = self.get_object()
        course = lesson.module.course
        user = request.user
        if user.role == 'STUDENT' and course.status not in (
            Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED
        ):
            raise PermissionDenied('This lesson is not accessible.')
        if user.role == 'CREATOR' and course.creator_id != user.id:
            raise PermissionDenied('You do not have permission to view this lesson.')
        serializer = self.get_serializer(lesson)
        return Response(serializer.data)

    def perform_create(self, serializer):
        module = self._get_module()
        course = module.course
        user = self.request.user

        if course.status == Course.STATUS_PENDING:
            raise ValidationError('Lessons cannot be added while the course is pending approval.')
        if course.status == Course.STATUS_ARCHIVED:
            raise ValidationError('Lessons cannot be added to an archived course.')
        if user.role == 'CREATOR' and course.creator_id != user.id:
            raise PermissionDenied('You are not the owner of this course.')

        next_order = _get_next_order(Lesson.objects.filter(module=module))
        serializer.save(module=module, order=next_order)

    def partial_update(self, request, *args, **kwargs):
        lesson = self.get_object()
        self.check_object_permissions(request, lesson)
        serializer = self.get_serializer(lesson, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(LessonSerializer(lesson).data)

    @extend_schema(
        summary='Reorder lessons',
        description=(
            'Provide the full ordered list of lesson UUIDs for this module. '
            'Orders are reassigned 1 to N in the given sequence.'
        ),
        request=ReorderSerializer,
        responses={200: LessonListSerializer(many=True)},
    )
    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request, module_pk=None):
        module = self._get_module()
        course = module.course
        user = request.user

        if user.role == 'ADMIN':
            pass
        elif user.role == 'CREATOR':
            if not user.is_creator_approved or course.creator_id != user.id:
                raise PermissionDenied('You are not the owner of this course.')
        else:
            raise PermissionDenied('Only Admins or course owners can reorder lessons.')

        if course.status not in (Course.STATUS_DRAFT, Course.STATUS_PUBLISHED):
            raise ValidationError('Lessons can only be reordered in DRAFT or PUBLISHED courses.')

        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ordered_ids = serializer.validated_data['ordered_ids']

        _apply_reorder(Lesson, 'module_id', module.pk, ordered_ids)
        lessons = Lesson.objects.filter(module=module).order_by('order')
        return Response(LessonListSerializer(lessons, many=True).data)


# ── ResourceViewSet ───────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary='List resources for a lesson',
        description='Returns all resources attached to this lesson.',
    ),
    create=extend_schema(
        summary='Add a resource to a lesson',
        description='Attaches a new resource (PDF, link, etc.) to the lesson.',
    ),
    partial_update=extend_schema(
        summary='Update resource metadata',
        description='Modify resource title, type, or URL.',
    ),
    update=extend_schema(exclude=True),
    retrieve=extend_schema(exclude=True),
    destroy=extend_schema(exclude=True),
)
class ResourceViewSet(viewsets.ModelViewSet):
    """
    Nested under /lessons/{lesson_pk}/resources/ and /resources/{id}/.
    - GET  /lessons/{lesson_pk}/resources/  → list
    - POST /lessons/{lesson_pk}/resources/  → create
    - PATCH /resources/{id}/               → partial_update
    """
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def _get_lesson(self):
        lesson_pk = self.kwargs.get('lesson_pk')
        try:
            return Lesson.objects.select_related('module__course').get(pk=lesson_pk)
        except Lesson.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Lesson not found.')

    def get_queryset(self):
        if 'lesson_pk' in self.kwargs:
            lesson = self._get_lesson()
            self._check_course_read_permission(lesson.module.course)
            return Resource.objects.filter(lesson=lesson)
        return Resource.objects.all().select_related('lesson__module__course')

    def _check_course_read_permission(self, course):
        user = self.request.user
        if user.role == 'STUDENT' and course.status not in (
            Course.STATUS_PUBLISHED, Course.STATUS_ARCHIVED
        ):
            raise PermissionDenied('This course is not accessible.')
        if user.role == 'CREATOR' and course.creator_id != user.id:
            raise PermissionDenied('You do not have permission to view this course.')

    def get_permissions(self):
        if self.action == 'list':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsCourseOwnerOrAdmin()]

    def get_serializer_class(self):
        if self.action == 'create':
            return ResourceCreateSerializer
        return ResourceSerializer

    def perform_create(self, serializer):
        lesson = self._get_lesson()
        course = lesson.module.course
        user = self.request.user

        if user.role == 'STUDENT':
            raise PermissionDenied('Students cannot add resources.')
        elif user.role == 'CREATOR':
            if not user.is_creator_approved:
                raise PermissionDenied('Your creator account has not been approved.')
            if course.creator_id != user.id:
                raise PermissionDenied('You are not the owner of this course.')
        if course.status in (Course.STATUS_PENDING, Course.STATUS_ARCHIVED):
            raise ValidationError(
                'Resources cannot be added to a {} course.'.format(course.status.lower())
            )
        serializer.save(lesson=lesson)

    def partial_update(self, request, *args, **kwargs):
        resource = self.get_object()
        self.check_object_permissions(request, resource)
        serializer = self.get_serializer(resource, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ResourceSerializer(resource).data)


# ── LessonProgressViewSet ───────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary='List lesson progress for a student',
        description='Returns all lesson progress records for the authenticated student.',
    ),
    retrieve=extend_schema(
        summary='Retrieve lesson progress',
        description='Get detailed progress for a specific lesson.',
    ),
    create=extend_schema(
        summary='Start a lesson',
        description='Marks a lesson as started by the student.',
    ),
    partial_update=extend_schema(
        summary='Update lesson progress',
        description='Mark a lesson as completed, update last accessed time.',
    ),
    update=extend_schema(exclude=True),
    destroy=extend_schema(exclude=True),
)
class LessonProgressViewSet(viewsets.ModelViewSet):
    """
    Lesson progress tracking:
    - GET  /lesson-progress/          → list (student's own progress)
    - GET  /lesson-progress/{id}/     → retrieve
    - POST /lesson-progress/          → create (start lesson)
    - PATCH /lesson-progress/{id}/    → partial_update (mark completed, etc.)
    """
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return LessonProgress.objects.none()
        if user.role == 'ADMIN':
            return LessonProgress.objects.all().select_related('student', 'lesson__module__course')
        # Only students can have progress
        return LessonProgress.objects.filter(student=user).select_related('student', 'lesson__module__course')

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'create', 'partial_update'):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'partial_update':
            return LessonProgressUpdateSerializer
        return LessonProgressSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != 'STUDENT':
            raise PermissionDenied('Only students can track lesson progress.')
        serializer.save(student=user)
