
from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db import transaction

from enrollments.models import Enrollment
from enrollments.serializers import (
    EnrollmentSerializer, EnrollmentAdminCreateSerializer,
)
from users.permissions import IsStudent, IsAdmin
from courses.models import Course


@extend_schema_view(
    list=extend_schema(
        summary='List my enrollments',
        description='Get all enrollments for the current student. Admins see all.',
    ),
    retrieve=extend_schema(
        summary='Get an enrollment',
        description='Get details of a specific enrollment.',
    ),
)
class EnrollmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Student-facing enrollment management:
    - GET  /enrollments/         → list (student's own, admin sees all)
    - GET  /enrollments/{id}/    → retrieve
    - POST /enrollments/{id}/drop/ → drop
    """
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        return EnrollmentSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'ADMIN':
            return Enrollment.objects.all().select_related('student', 'course')
        return Enrollment.objects.filter(student=user).select_related('course')

    @extend_schema(
        summary='Drop an enrollment',
        description='Mark an enrollment as dropped.',
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


# ── Admin Enrollment Views ────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        summary='Admin: List all enrollments',
        description='Inspect all enrollment records across students and courses.',
    ),
    create=extend_schema(
        summary='Admin: Enroll a student',
        description='Administratively enroll any student in any course.',
    ),
)
class AdminEnrollmentViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Admin-only enrollment management:
    - GET  /admin/enrollments/  → list all
    - POST /admin/enrollments/  → enroll a student
    """
    http_method_names = ['get', 'post', 'head', 'options']
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    queryset = Enrollment.objects.all().select_related('student', 'course')

    def get_serializer_class(self):
        if self.action == 'create':
            return EnrollmentAdminCreateSerializer
        return EnrollmentSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(status=Enrollment.STATUS_ACTIVE)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
