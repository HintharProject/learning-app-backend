from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view

from users.serializers import (
    UserProfileSerializer,
    UserListSerializer,
    UserRoleUpdateSerializer,
    UserStatusUpdateSerializer
)
from users.permissions import IsAdmin

User = get_user_model()

@extend_schema_view(
    list=extend_schema(summary="List all users", description="Retrieve a list of all registered users (Admin only)."),
    retrieve=extend_schema(summary="Retrieve user details", description="Retrieve detailed information for a specific user (Admin only)."),
    create=extend_schema(exclude=True), # Users are created via Clerk auth sync, not manual REST post
    update=extend_schema(exclude=True),
    partial_update=extend_schema(exclude=True),
    destroy=extend_schema(exclude=True),
)
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = [IsAdmin] # Default permission for general views is Admin-only

    def get_queryset(self):
        # Admins can see all users, standard users should only see themselves
        if self.request.user and self.request.user.is_authenticated and self.request.user.role == 'ADMIN':
            return User.objects.all().order_by('-created_at')
        return User.objects.filter(id=self.request.user.id)

    @extend_schema(
        methods=['GET'],
        summary="Retrieve own profile",
        responses={200: UserProfileSerializer}
    )
    @extend_schema(
        methods=['PATCH'],
        summary="Update own profile",
        request=UserProfileSerializer,
        responses={200: UserProfileSerializer}
    )
    @action(
        detail=False,
        methods=['get', 'patch'],
        url_path='me',
        permission_classes=[permissions.IsAuthenticated]
    )
    def me(self, request):
        user = request.user
        if request.method == 'GET':
            serializer = UserProfileSerializer(user)
            return Response(serializer.data)
        
        elif request.method == 'PATCH':
            serializer = UserProfileSerializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

    @extend_schema(
        methods=['PATCH'],
        summary="Update user role",
        request=UserRoleUpdateSerializer,
        responses={200: UserListSerializer}
    )
    @action(
        detail=True,
        methods=['patch'],
        url_path='role',
        permission_classes=[IsAdmin]
    )
    def role(self, request, pk=None):
        user = self.get_object()
        serializer = UserRoleUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # If role is updated, we might also want to handle approval logic or other flags,
        # but spec says just update and return.
        return Response(UserListSerializer(user).data)

    @extend_schema(
        methods=['PATCH'],
        summary="Update user status",
        request=UserStatusUpdateSerializer,
        responses={200: UserListSerializer}
    )
    @action(
        detail=True,
        methods=['patch'],
        url_path='status',
        permission_classes=[IsAdmin]
    )
    def status(self, request, pk=None):
        user = self.get_object()
        serializer = UserStatusUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserListSerializer(user).data)
