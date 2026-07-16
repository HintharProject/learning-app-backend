from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'clerk_id',
            'email',
            'full_name',
            'avatar_url',
            'role',
            'is_creator_approved',
            'status_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'clerk_id',
            'email',
            'role',
            'is_creator_approved',
            'status_active',
            'created_at',
            'updated_at'
        ]

class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'clerk_id',
            'email',
            'full_name',
            'avatar_url',
            'role',
            'is_creator_approved',
            'status_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'clerk_id',
            'email',
            'created_at',
            'updated_at'
        ]

class UserRoleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['role']

    def validate_role(self, value):
        if value not in dict(User.ROLE_CHOICES):
            raise serializers.ValidationError(f"Invalid role choice. Allowed: {list(dict(User.ROLE_CHOICES).keys())}")
        return value

class UserStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['status_active']
