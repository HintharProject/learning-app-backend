from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework import status
from unittest.mock import patch
import jwt

from users.authentication import ClerkAuthentication
from users.permissions import IsAdmin, IsCreator, IsStudent, IsOwnerOrAdmin

User = get_user_model()

class UserModelTests(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(clerk_id="clerk_123", email="student@example.com")
        self.assertEqual(user.clerk_id, "clerk_123")
        self.assertEqual(user.email, "student@example.com")
        self.assertEqual(user.role, "STUDENT")
        self.assertFalse(user.is_creator_approved)
        self.assertTrue(user.status_active)
        self.assertTrue(user.is_active)

    def test_create_superuser(self):
        user = User.objects.create_superuser(clerk_id="clerk_admin", email="admin@example.com")
        self.assertEqual(user.clerk_id, "clerk_admin")
        self.assertEqual(user.email, "admin@example.com")
        self.assertEqual(user.role, "ADMIN")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_is_active_property_setter(self):
        user = User.objects.create_user(clerk_id="clerk_456", email="test@example.com")
        user.is_active = False
        self.assertFalse(user.status_active)
        self.assertFalse(user.is_active)


class ClerkAuthenticationTests(APITestCase):
    def setUp(self):
        self.auth = ClerkAuthentication()
        self.factory = APIRequestFactory()

    @patch('jwt.decode')
    @patch('django.conf.settings.CLERK_JWT_PEM_PUBLIC_KEY', 'fake_key')
    def test_authenticate_success(self, mock_decode):
        mock_decode.return_value = {
            'sub': 'clerk_789',
            'email': 'new_user@example.com',
            'name': 'New User',
            'picture': 'https://example.com/avatar.png'
        }
        
        request = self.factory.get('/api/v1/users/me/', HTTP_AUTHORIZATION='Bearer valid_token')
        user, token = self.auth.authenticate(request)
        
        self.assertEqual(user.clerk_id, 'clerk_789')
        self.assertEqual(user.email, 'new_user@example.com')
        self.assertEqual(user.full_name, 'New User')
        self.assertEqual(user.avatar_url, 'https://example.com/avatar.png')

    @patch('jwt.decode')
    @patch('django.conf.settings.CLERK_JWT_PEM_PUBLIC_KEY', 'fake_key')
    def test_authenticate_expired(self, mock_decode):
        mock_decode.side_effect = jwt.ExpiredSignatureError("Token expired")
        request = self.factory.get('/api/v1/users/me/', HTTP_AUTHORIZATION='Bearer expired_token')
        
        from rest_framework.exceptions import AuthenticationFailed
        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(request)
        self.assertIn("expired", str(context.exception))


class UserPermissionTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(clerk_id="admin_1", email="admin@test.com", role="ADMIN")
        self.student_user = User.objects.create_user(clerk_id="student_1", email="student@test.com", role="STUDENT")
        self.unapproved_creator = User.objects.create_user(clerk_id="creator_1", email="creator1@test.com", role="CREATOR")
        self.approved_creator = User.objects.create_user(clerk_id="creator_2", email="creator2@test.com", role="CREATOR", is_creator_approved=True)
        
        self.factory = APIRequestFactory()

    def test_is_admin_permission(self):
        perm = IsAdmin()
        request = self.factory.get('/')
        
        request.user = self.student_user
        self.assertFalse(perm.has_permission(request, None))
        
        request.user = self.admin_user
        self.assertTrue(perm.has_permission(request, None))

    def test_is_creator_permission(self):
        perm = IsCreator()
        request = self.factory.get('/')
        
        request.user = self.unapproved_creator
        self.assertFalse(perm.has_permission(request, None))
        
        request.user = self.approved_creator
        self.assertTrue(perm.has_permission(request, None))


class UserViewSetTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(clerk_id="admin", email="admin@test.com", role="ADMIN")
        self.student = User.objects.create_user(clerk_id="student", email="student@test.com", role="STUDENT")

    def test_get_me_profile(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['clerk_id'], 'student')

    def test_patch_me_profile(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('user-me')
        response = self.client.patch(url, {'full_name': 'New Student Name'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, 'New Student Name')

    def test_patch_me_role_read_only(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('user-me')
        response = self.client.patch(url, {'role': 'ADMIN'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, 'STUDENT')

    def test_admin_list_users(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('user-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)

    def test_student_list_users_fails(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('user-list')
        response = self.client.get(url)
        # Even though get_queryset filters to self, permission_classes = [IsAdmin] blocks list access completely
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_update_role(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('user-role', args=[self.student.id])
        response = self.client.patch(url, {'role': 'CREATOR'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, 'CREATOR')

    def test_admin_update_status(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('user-status', args=[self.student.id])
        response = self.client.patch(url, {'status_active': False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertFalse(self.student.status_active)
