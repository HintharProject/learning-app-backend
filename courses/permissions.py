
from rest_framework import permissions
from courses.models import Course


class IsApprovedCreator(permissions.BasePermission):
    """
    Grants access only to Creator users who have been approved by an Admin.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'CREATOR' and
            request.user.is_creator_approved
        )


class IsAdminOrApprovedCreator(permissions.BasePermission):
    """
    Grants access to Admin users OR approved Creators.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == 'ADMIN':
            return True
        return (
            request.user.role == 'CREATOR' and
            request.user.is_creator_approved
        )


class IsCourseOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission: allows access only to the course's creator (owner)
    or to Admin users.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == 'ADMIN':
            return True
        # obj may be Course, Module, Lesson, Resource, Quiz, Question, Option — resolve up the tree.
        course = _resolve_course(obj)
        if course is None:
            return False
        return (
            request.user.role == 'CREATOR' and
            request.user.is_creator_approved and
            course.creator_id == request.user.id
        )


class CanAddContentToCourse(permissions.BasePermission):
    """
    Permits adding new Modules/Lessons/Quizzes to a course that is PUBLISHED
    (creators may add but not edit existing structures) or DRAFT (fully editable).
    Admins bypass all restrictions.
    Used as an object-level permission on the parent Course.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        course = _resolve_course(obj)
        if course is None:
            return False
        if request.user.role == 'ADMIN':
            return True
        if request.user.role == 'CREATOR' and request.user.is_creator_approved:
            # Creators can add content in DRAFT or PUBLISHED state.
            return (
                course.creator_id == request.user.id and
                course.status in (
                    course.STATUS_DRAFT,
                    course.STATUS_PUBLISHED,
                )
            )
        return False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_course(obj):
    """Walk up the object hierarchy to find the parent Course."""
    from courses.models import Course, Module, Lesson, Resource
    from quizzes.models import Quiz
    if isinstance(obj, Course):
        return obj
    if isinstance(obj, Module):
        return obj.course
    if isinstance(obj, Lesson):
        return obj.module.course
    if isinstance(obj, Resource):
        return obj.lesson.module.course
    if isinstance(obj, Quiz):
        return obj.lesson.module.course
    return None
