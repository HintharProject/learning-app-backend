
from rest_framework import serializers
from study_plans.models import StudyPlan, StudyPlanItem
from courses.models import Course, Module, Lesson


class StudyPlanItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyPlanItem
        fields = [
            'id',
            'study_plan',
            'course',
            'module',
            'lesson',
            'scheduled_date',
            'order',
            'created_at',
        ]
        read_only_fields = ['id', 'study_plan', 'order', 'created_at']


class StudyPlanItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyPlanItem
        fields = [
            'id',
            'course',
            'module',
            'lesson',
            'scheduled_date',
            'order',
            'created_at',
        ]
        read_only_fields = ['id', 'order', 'created_at']


class StudyPlanItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyPlanItem
        fields = ['scheduled_date']


class StudyPlanSerializer(serializers.ModelSerializer):
    items = StudyPlanItemSerializer(many=True, read_only=True)

    class Meta:
        model = StudyPlan
        fields = [
            'id',
            'student',
            'title',
            'start_date',
            'end_date',
            'items',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'student', 'items', 'created_at', 'updated_at']


class StudyPlanCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyPlan
        fields = ['id', 'title', 'start_date', 'end_date', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class StudyPlanUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyPlan
        fields = ['title', 'start_date', 'end_date', 'updated_at']
        read_only_fields = ['updated_at']
