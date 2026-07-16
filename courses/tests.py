"""
Comprehensive tests for the Courses app.

Covers:
  - Model behaviours (slug auto-generation, ordering uniqueness)
  - Course lifecycle state machine (all valid + invalid transitions)
  - Permission matrix (Admin / approved Creator / unapproved Creator / Student)
  - Post-publication editing restrictions (title/video_url locked)
  - Module and Lesson CRUD with auto-ordering
  - Reorder endpoints (happy path + validation errors)
  - Resource CRUD
"""

import uuid
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch

from users.models import User
from courses.models import Course, Module, Lesson, Resource


# ── Factories ─────────────────────────────────────────────────────────────────

def make_user(role='STUDENT', approved=False, suffix=None):
    suffix = suffix or str(uuid.uuid4())[:8]
    return User.objects.create_user(
        clerk_id=f'clerk_{suffix}',
        email=f'user_{suffix}@test.com',
        role=role,
        is_creator_approved=(approved if role == 'CREATOR' else False),
    )


def make_course(creator, status=Course.STATUS_DRAFT, title='Test Course'):
    return Course.objects.create(
        title=title,
        creator=creator,
        status=status,
        description='A test course.',
    )


def make_module(course, order=1, title='Module 1'):
    return Module.objects.create(
        course=course,
        title=title,
        order=order,
    )


def make_lesson(module, order=1, title='Lesson 1'):
    return Lesson.objects.create(
        module=module,
        title=title,
        order=order,
        content='Some content.',
    )


def make_resource(lesson, title='Resource 1', rtype='PDF'):
    return Resource.objects.create(
        lesson=lesson,
        title=title,
        type=rtype,
        url='https://example.com/resource.pdf',
    )


# ── Authenticated API Client ──────────────────────────────────────────────────

def authed_client(user):
    """Return an API client that forces authentication as the given user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── Model Tests ───────────────────────────────────────────────────────────────

class CourseModelTests(TestCase):
    def setUp(self):
        self.creator = make_user(role='CREATOR', approved=True)

    def test_slug_auto_generated_from_title(self):
        course = make_course(self.creator, title='My Awesome Course')
        self.assertEqual(course.slug, 'my-awesome-course')

    def test_slug_uniqueness_collision(self):
        make_course(self.creator, title='Duplicate Title')
        course2 = make_course(self.creator, title='Duplicate Title')
        self.assertNotEqual(course2.slug, 'duplicate-title')
        self.assertTrue(course2.slug.startswith('duplicate-title-'))

    def test_slug_not_overwritten_on_update(self):
        course = make_course(self.creator, title='Original Title')
        original_slug = course.slug
        course.description = 'Updated description'
        course.save()
        course.refresh_from_db()
        self.assertEqual(course.slug, original_slug)

    def test_is_editable_only_in_draft(self):
        course = make_course(self.creator, status=Course.STATUS_DRAFT)
        self.assertTrue(course.is_editable)
        course.status = Course.STATUS_PUBLISHED
        self.assertFalse(course.is_editable)

    def test_str_representation(self):
        course = make_course(self.creator, title='Test')
        self.assertIn('Test', str(course))
        self.assertIn('DRAFT', str(course))


class ModuleModelTests(TestCase):
    def setUp(self):
        self.creator = make_user(role='CREATOR', approved=True)
        self.course = make_course(self.creator)

    def test_unique_together_order_per_course(self):
        from django.db import IntegrityError
        make_module(self.course, order=1)
        with self.assertRaises(IntegrityError):
            Module.objects.create(course=self.course, title='Dupe Order', order=1)

    def test_ordering_by_order_field(self):
        make_module(self.course, order=3, title='Third')
        make_module(self.course, order=1, title='First')
        make_module(self.course, order=2, title='Second')
        titles = list(Module.objects.filter(course=self.course).values_list('title', flat=True))
        self.assertEqual(titles, ['First', 'Second', 'Third'])


# ── Course Lifecycle / State Machine Tests ────────────────────────────────────

class CourseLifecycleTests(APITestCase):
    def setUp(self):
        self.admin = make_user(role='ADMIN')
        self.creator = make_user(role='CREATOR', approved=True)
        self.student = make_user(role='STUDENT')
        self.course = make_course(self.creator)

    def _url(self, action):
        return f'/api/v1/courses/{self.course.pk}/{action}/'

    def test_creator_can_submit_draft_for_review(self):
        client = authed_client(self.creator)
        resp = client.post(self._url('submit-review'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, Course.STATUS_PENDING)

    def test_cannot_submit_non_draft_for_review(self):
        self.course.status = Course.STATUS_PUBLISHED
        self.course.save()
        client = authed_client(self.creator)
        resp = client.post(self._url('submit-review'))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_approve_pending_course(self):
        self.course.status = Course.STATUS_PENDING
        self.course.save()
        client = authed_client(self.admin)
        resp = client.post(self._url('approve'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, Course.STATUS_PUBLISHED)

    def test_admin_can_reject_pending_course(self):
        self.course.status = Course.STATUS_PENDING
        self.course.save()
        client = authed_client(self.admin)
        resp = client.post(self._url('reject'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, Course.STATUS_DRAFT)

    def test_creator_cannot_approve_course(self):
        self.course.status = Course.STATUS_PENDING
        self.course.save()
        client = authed_client(self.creator)
        resp = client.post(self._url('approve'))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_approve_course(self):
        self.course.status = Course.STATUS_PENDING
        self.course.save()
        client = authed_client(self.student)
        resp = client.post(self._url('approve'))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_creator_can_archive_published_course(self):
        self.course.status = Course.STATUS_PUBLISHED
        self.course.save()
        client = authed_client(self.creator)
        resp = client.post(self._url('archive'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, Course.STATUS_ARCHIVED)

    def test_cannot_archive_non_published_course(self):
        # DRAFT courses cannot be archived directly
        client = authed_client(self.admin)
        resp = client.post(self._url('archive'))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_approve_already_published_course(self):
        self.course.status = Course.STATUS_PUBLISHED
        self.course.save()
        client = authed_client(self.admin)
        resp = client.post(self._url('approve'))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ── Course CRUD Permission Tests ──────────────────────────────────────────────

class CoursePermissionTests(APITestCase):
    base_url = '/api/v1/courses/'

    def setUp(self):
        self.admin = make_user(role='ADMIN')
        self.creator = make_user(role='CREATOR', approved=True)
        self.unapproved_creator = make_user(role='CREATOR', approved=False)
        self.student = make_user(role='STUDENT')
        self.course = make_course(self.creator)
        self.other_creator = make_user(role='CREATOR', approved=True)

    def test_student_can_list_published_courses_only(self):
        make_course(self.creator, status=Course.STATUS_PUBLISHED, title='Published')
        make_course(self.creator, status=Course.STATUS_DRAFT, title='Hidden')
        client = authed_client(self.student)
        resp = client.get(self.base_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # No pagination configured — resp.data is a plain list
        titles = [c['title'] for c in resp.data]
        self.assertIn('Published', titles)
        self.assertNotIn('Hidden', titles)

    def test_creator_sees_only_own_courses(self):
        make_course(self.other_creator, title='Other Course')
        client = authed_client(self.creator)
        resp = client.get(self.base_url)
        # No pagination configured — resp.data is a plain list
        for c in resp.data:
            self.assertEqual(str(c['creator']), str(self.creator.id))

    def test_admin_sees_all_courses(self):
        make_course(self.other_creator, title='Other Course')
        client = authed_client(self.admin)
        resp = client.get(self.base_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # No pagination configured — resp.data is a plain list
        self.assertGreaterEqual(len(resp.data), 2)

    def test_approved_creator_can_create_course(self):
        client = authed_client(self.creator)
        resp = client.post(self.base_url, {'title': 'New Course'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], Course.STATUS_DRAFT)

    def test_unapproved_creator_cannot_create_course(self):
        client = authed_client(self.unapproved_creator)
        resp = client.post(self.base_url, {'title': 'New Course'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_create_course(self):
        client = authed_client(self.student)
        resp = client.post(self.base_url, {'title': 'New Course'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_view_draft_course(self):
        # The student queryset excludes non-published courses, so they receive
        # a 404 (not 403) — this avoids leaking whether a draft course exists.
        client = authed_client(self.student)
        resp = client.get(f'{self.base_url}{self.course.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_can_view_published_course(self):
        self.course.status = Course.STATUS_PUBLISHED
        self.course.save()
        client = authed_client(self.student)
        resp = client.get(f'{self.base_url}{self.course.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_other_creator_cannot_view_another_creators_draft(self):
        # The creator queryset filters to own courses only, so another creator
        # receives a 404 (not 403) — avoids leaking existence of other drafts.
        client = authed_client(self.other_creator)
        resp = client.get(f'{self.base_url}{self.course.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_creator_cannot_patch_another_creators_course(self):
        # Similarly, PATCH on a course not in the creator's queryset returns 404.
        client = authed_client(self.other_creator)
        resp = client.patch(f'{self.base_url}{self.course.pk}/', {'title': 'Hacked'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ── Post-Publication Editing Restriction Tests ────────────────────────────────

class PostPublicationEditingTests(APITestCase):
    def setUp(self):
        self.admin = make_user(role='ADMIN')
        self.creator = make_user(role='CREATOR', approved=True)
        self.course = make_course(self.creator, status=Course.STATUS_PUBLISHED)
        self.module = make_module(self.course)
        self.lesson = make_lesson(self.module)

    def test_cannot_update_course_title_when_published(self):
        client = authed_client(self.creator)
        resp = client.patch(
            f'/api/v1/courses/{self.course.pk}/',
            {'title': 'New Title'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', resp.data)

    def test_can_update_cover_image_when_published(self):
        client = authed_client(self.creator)
        resp = client.patch(
            f'/api/v1/courses/{self.course.pk}/',
            {'cover_image': 'https://example.com/new.jpg'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cannot_update_module_title_when_published(self):
        client = authed_client(self.creator)
        resp = client.patch(
            f'/api/v1/modules/{self.module.pk}/',
            {'title': 'Changed Title'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', resp.data)

    def test_cannot_update_lesson_title_when_published(self):
        client = authed_client(self.creator)
        resp = client.patch(
            f'/api/v1/lessons/{self.lesson.pk}/',
            {'title': 'Changed Title'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', resp.data)

    def test_cannot_update_lesson_video_url_when_published(self):
        client = authed_client(self.creator)
        resp = client.patch(
            f'/api/v1/lessons/{self.lesson.pk}/',
            {'video_url': 'https://example.com/new_video.mp4'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('video_url', resp.data)

    def test_creator_can_add_module_to_published_course(self):
        client = authed_client(self.creator)
        resp = client.post(
            f'/api/v1/courses/{self.course.pk}/modules/',
            {'title': 'New Module'},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_creator_can_add_lesson_to_published_module(self):
        client = authed_client(self.creator)
        resp = client.post(
            f'/api/v1/modules/{self.module.pk}/lessons/',
            {'title': 'New Lesson'},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_cannot_edit_course_when_pending(self):
        self.course.status = Course.STATUS_PENDING
        self.course.save()
        client = authed_client(self.creator)
        resp = client.patch(
            f'/api/v1/courses/{self.course.pk}/',
            {'cover_image': 'https://example.com/img.jpg'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ── Module Auto-Ordering Tests ────────────────────────────────────────────────

class ModuleOrderingTests(APITestCase):
    def setUp(self):
        self.creator = make_user(role='CREATOR', approved=True)
        self.course = make_course(self.creator)
        self.client = authed_client(self.creator)

    def test_first_module_gets_order_1(self):
        resp = self.client.post(
            f'/api/v1/courses/{self.course.pk}/modules/',
            {'title': 'Module A'},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['order'], 1)

    def test_second_module_gets_order_2(self):
        make_module(self.course, order=1, title='Module A')
        resp = self.client.post(
            f'/api/v1/courses/{self.course.pk}/modules/',
            {'title': 'Module B'},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['order'], 2)

    def test_cannot_add_module_to_pending_course(self):
        self.course.status = Course.STATUS_PENDING
        self.course.save()
        resp = self.client.post(
            f'/api/v1/courses/{self.course.pk}/modules/',
            {'title': 'New Module'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_add_module_to_archived_course(self):
        self.course.status = Course.STATUS_ARCHIVED
        self.course.save()
        resp = self.client.post(
            f'/api/v1/courses/{self.course.pk}/modules/',
            {'title': 'New Module'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ── Reorder Tests ─────────────────────────────────────────────────────────────

class ModuleReorderTests(APITestCase):
    def setUp(self):
        self.creator = make_user(role='CREATOR', approved=True)
        self.course = make_course(self.creator)
        self.m1 = make_module(self.course, order=1, title='M1')
        self.m2 = make_module(self.course, order=2, title='M2')
        self.m3 = make_module(self.course, order=3, title='M3')
        self.client = authed_client(self.creator)

    def test_reorder_modules_successfully(self):
        payload = {'ordered_ids': [str(self.m3.pk), str(self.m1.pk), str(self.m2.pk)]}
        resp = self.client.post(
            f'/api/v1/courses/{self.course.pk}/modules/reorder/',
            payload,
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.m3.refresh_from_db()
        self.m1.refresh_from_db()
        self.m2.refresh_from_db()
        self.assertEqual(self.m3.order, 1)
        self.assertEqual(self.m1.order, 2)
        self.assertEqual(self.m2.order, 3)

    def test_reorder_with_missing_ids_fails(self):
        payload = {'ordered_ids': [str(self.m1.pk), str(self.m2.pk)]}  # m3 missing
        resp = self.client.post(
            f'/api/v1/courses/{self.course.pk}/modules/reorder/',
            payload,
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reorder_with_duplicate_ids_fails(self):
        payload = {
            'ordered_ids': [str(self.m1.pk), str(self.m1.pk), str(self.m3.pk)]
        }
        resp = self.client.post(
            f'/api/v1/courses/{self.course.pk}/modules/reorder/',
            payload,
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_cannot_reorder_modules(self):
        student = make_user(role='STUDENT')
        client = authed_client(student)
        payload = {'ordered_ids': [str(self.m1.pk), str(self.m2.pk), str(self.m3.pk)]}
        resp = client.post(
            f'/api/v1/courses/{self.course.pk}/modules/reorder/',
            payload,
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class LessonReorderTests(APITestCase):
    def setUp(self):
        self.creator = make_user(role='CREATOR', approved=True)
        self.course = make_course(self.creator)
        self.module = make_module(self.course)
        self.l1 = make_lesson(self.module, order=1, title='L1')
        self.l2 = make_lesson(self.module, order=2, title='L2')
        self.l3 = make_lesson(self.module, order=3, title='L3')
        self.client = authed_client(self.creator)

    def test_reorder_lessons_successfully(self):
        payload = {'ordered_ids': [str(self.l3.pk), str(self.l2.pk), str(self.l1.pk)]}
        resp = self.client.post(
            f'/api/v1/modules/{self.module.pk}/lessons/reorder/',
            payload,
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.l3.refresh_from_db()
        self.l2.refresh_from_db()
        self.l1.refresh_from_db()
        self.assertEqual(self.l3.order, 1)
        self.assertEqual(self.l2.order, 2)
        self.assertEqual(self.l1.order, 3)

    def test_reorder_with_extra_ids_fails(self):
        payload = {
            'ordered_ids': [str(self.l1.pk), str(self.l2.pk), str(self.l3.pk), str(uuid.uuid4())]
        }
        resp = self.client.post(
            f'/api/v1/modules/{self.module.pk}/lessons/reorder/',
            payload,
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ── Resource Tests ────────────────────────────────────────────────────────────

class ResourceTests(APITestCase):
    def setUp(self):
        self.admin = make_user(role='ADMIN')
        self.creator = make_user(role='CREATOR', approved=True)
        self.student = make_user(role='STUDENT')
        self.course = make_course(self.creator, status=Course.STATUS_PUBLISHED)
        self.module = make_module(self.course)
        self.lesson = make_lesson(self.module)

    def test_creator_can_add_resource_to_published_lesson(self):
        client = authed_client(self.creator)
        resp = client.post(
            f'/api/v1/lessons/{self.lesson.pk}/resources/',
            {'title': 'Slides', 'type': 'PDF', 'url': 'https://example.com/slides.pdf'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_student_cannot_add_resource(self):
        client = authed_client(self.student)
        resp = client.post(
            f'/api/v1/lessons/{self.lesson.pk}/resources/',
            {'title': 'Slides', 'type': 'PDF', 'url': 'https://example.com/slides.pdf'},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_can_list_resources_on_published_course(self):
        make_resource(self.lesson)
        client = authed_client(self.student)
        resp = client.get(f'/api/v1/lessons/{self.lesson.pk}/resources/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_patch_resource(self):
        resource = make_resource(self.lesson)
        client = authed_client(self.admin)
        resp = client.patch(
            f'/api/v1/resources/{resource.pk}/',
            {'title': 'Updated Title'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'Updated Title')

    def test_other_creator_cannot_add_resource(self):
        other = make_user(role='CREATOR', approved=True)
        client = authed_client(other)
        resp = client.post(
            f'/api/v1/lessons/{self.lesson.pk}/resources/',
            {'title': 'Steal', 'type': 'LINK', 'url': 'https://example.com'},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
