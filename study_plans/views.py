
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from drf_spectacular.utils import extend_schema, extend_schema_view

from study_plans.models import StudyPlan, StudyPlanItem
from study_plans.serializers import (
    StudyPlanSerializer, StudyPlanCreateSerializer, StudyPlanUpdateSerializer,
    StudyPlanItemSerializer, StudyPlanItemCreateSerializer, StudyPlanItemUpdateSerializer,
)
from users.permissions import IsStudent


@extend_schema_view(
    list=extend_schema(
        summary='List my study plans',
        description='Get all study plans for the current student.'
    ),
    create=extend_schema(
        summary='Create a study plan',
        description='Create a new study plan.'
    ),
    retrieve=extend_schema(
        summary='Get a study plan',
        description='Get details of a specific study plan (only the owner or admin).'
    ),
    partial_update=extend_schema(
        summary='Update a study plan',
        description='Modify a study plan (only the owner or admin).'
    ),
    destroy=extend_schema(
        summary='Delete a study plan',
        description='Delete a study plan (only the owner or admin).'
    ),
)
class StudyPlanViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return StudyPlanCreateSerializer
        if self.action == 'partial_update':
            return StudyPlanUpdateSerializer
        return StudyPlanSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsStudent()]

    def get_queryset(self):
        return StudyPlan.objects.filter(student=self.request.user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary='List study plan items',
        description='Get all items in a study plan.'
    ),
    create=extend_schema(
        summary='Add an item to a study plan',
        description='Add a new course/module/lesson to a study plan.'
    ),
    retrieve=extend_schema(
        summary='Get a study plan item',
        description='Get details of a specific study plan item.'
    ),
    partial_update=extend_schema(
        summary='Update a study plan item',
        description='Modify a study plan item (e.g., scheduled date).'
    ),
    destroy=extend_schema(
        summary='Remove a study plan item',
        description='Delete an item from a study plan.'
    ),
)
class StudyPlanItemViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return StudyPlanItemCreateSerializer
        if self.action == 'partial_update':
            return StudyPlanItemUpdateSerializer
        return StudyPlanItemSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsStudent()]

    def get_queryset(self):
        if 'study_plan_pk' in self.kwargs:
            return StudyPlanItem.objects.filter(study_plan_id=self.kwargs['study_plan_pk'])
        return StudyPlanItem.objects.filter(study_plan__student=self.request.user)

    def _get_study_plan(self):
        study_plan_pk = self.kwargs.get('study_plan_pk')
        try:
            return StudyPlan.objects.get(pk=study_plan_pk, student=self.request.user)
        except StudyPlan.DoesNotExist:
            raise NotFound('Study plan not found.')

    def list(self, request, *args, **kwargs):
        self._get_study_plan()  # Check permission
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        study_plan = self._get_study_plan()
        next_order = StudyPlanItem.objects.filter(study_plan=study_plan).count() + 1
        serializer.save(study_plan=study_plan, order=next_order)
