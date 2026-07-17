
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db import transaction

from enrollments.models import Enrollment
from enrollments.serializers import (
    EnrollmentSerializer, EnrollmentCreateSerializer, EnrollmentAdminCreateSerializer,
)
from users.permissions import IsStudent, IsAdmin
from courses.models import Course


@extend_schema_view(
    list=extend_schema(
        summary='List my enrollments',
        description='Get all enrollments for the current student user.'
    ),
    create=extend_schema(
        summary='Enroll in a course',
        description='Create or reactivate an enrollment for a course.'
    ),
    retrieve=extend_schema(
        summary='Get an enrollment',
        description='Get details of a specific enrollment (only the student or admin).'
    ),
)
class EnrollmentViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'admin_create':
            return EnrollmentAdminCreateSerializer
        if self.action == 'create':
            return EnrollmentCreateSerializer
        return EnrollmentSerializer

    def get_permissions(self):
        if self.action == 'admin_create':
            return [permissions.IsAuthenticated(), IsAdmin()]
        if self.action in ['list', 'create', 'retrieve', 'drop']:
            return [permissions.IsAuthenticated(), IsStudent()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'ADMIN':
            return Enrollment.objects.all()
        return Enrollment.objects.filter(student=user)

    def create(self, request, *args, **kwargs):
        course_id = request.data.get('course')
        if not course_id:
            raise ValidationError('Course ID is required.')
        try:
            course = Course.objects.get(pk=course_id)
        except Course.DoesNotExist:
            raise NotFound('Course not found.')
        if course.status != Course.STATUS_PUBLISHED:
            raise ValidationError('Only published courses can be enrolled in.')

        student = request.user

        with transaction.atomic():
            # Check for existing enrollment
            enrollment, created = Enrollment.objects.get_or_create(
                student=student,
                course=course,
                defaults={'status': Enrollment.STATUS_ACTIVE},
            )
            if not created and enrollment.status != Enrollment.STATUS_ACTIVE:
                # Reactivate the enrollment
                enrollment.status = Enrollment.STATUS_ACTIVE
                enrollment.save()

        return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(
        summary='Drop an enrollment',
        description='Mark an enrollment as dropped.'
    )
    @action(detail=True, methods=['post'], url_path='drop')
    def drop(self, request, pk=None):
        enrollment = self.get_object()
        if enrollment.student != request.user and request.user.role != 'ADMIN':
            raise PermissionDenied()

        if enrollment.status != Enrollment.STATUS_ACTIVE:
            raise ValidationError('Only active enrollments can be dropped.')

        enrollment.status = Enrollment.STATUS_DROPPED
        enrollment.save()
        return Response(EnrollmentSerializer(enrollment).data)

    @extend_schema(
        summary='Admin create enrollment',
        description='Admin can enroll any student in any course.'
    )
    @action(detail=False, methods=['post'], url_path='admin', permission_classes=[IsAdmin])
    def admin_create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(status=Enrollment.STATUS_ACTIVE)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
