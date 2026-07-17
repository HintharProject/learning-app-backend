import json
import hmac
import hashlib
import logging
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
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

logger = logging.getLogger(__name__)
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


@csrf_exempt
def clerk_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # Verify webhook signature (optional but recommended)
    # For MVP, let's skip verification but note it should be added in production
    try:
        payload = json.loads(request.body.decode('utf-8'))
        event_type = payload.get('type')
        data = payload.get('data', {})

        logger.info(f"Received Clerk webhook: {event_type}")

        if event_type in ('user.created', 'user.updated'):
            clerk_id = data.get('id')
            email_addresses = data.get('email_addresses', [])
            primary_email = None
            for email in email_addresses:
                if email.get('primary'):
                    primary_email = email.get('email_address')
                    break
            if not primary_email:
                primary_email = email_addresses[0].get('email_address') if email_addresses else ''

            profile_image_url = data.get('profile_image_url', '')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            full_name = f"{first_name} {last_name}".strip()

            # Get or create user
            user, created = User.objects.get_or_create(
                clerk_id=clerk_id,
                defaults={
                    'email': primary_email,
                    'full_name': full_name,
                    'avatar_url': profile_image_url,
                    'role': 'STUDENT',  # Default role is STUDENT
                    'is_creator_approved': False,
                    'status_active': True,
                }
            )

            if not created:
                # Update user if needed
                user.email = primary_email
                user.full_name = full_name
                user.avatar_url = profile_image_url
                user.save()

            logger.info(f"User synced: {clerk_id}, created: {created}")

        return JsonResponse({'status': 'success'}, status=200)

    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
