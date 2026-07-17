
from rest_framework import serializers
from enrollments.models import Enrollment


class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = [
            'id',
            'student',
            'course',
            'enrolled_at',
            'status',
        ]
        read_only_fields = ['id', 'student', 'enrolled_at']


class EnrollmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = ['id', 'enrolled_at', 'status']
        read_only_fields = ['id', 'enrolled_at', 'status']


class EnrollmentAdminCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'course', 'enrolled_at', 'status']
        read_only_fields = ['id', 'enrolled_at']
