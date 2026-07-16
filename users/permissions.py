from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """
    Allows access only to users with the ADMIN role.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'ADMIN'
        )

class IsCreator(permissions.BasePermission):
    """
    Allows access only to approved CREATOR users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'CREATOR' and
            request.user.is_creator_approved
        )

class IsStudent(permissions.BasePermission):
    """
    Allows access only to STUDENT users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'STUDENT'
        )

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Allows access to users checking/modifying their own details, or ADMIN users.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role == 'ADMIN' or obj == request.user
