from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('email', 'full_name', 'role', 'is_creator_approved', 'status_active', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_creator_approved', 'status_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'full_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'avatar_url', 'clerk_id')}),
        ('Roles & Status', {'fields': ('role', 'is_creator_approved', 'status_active')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = ('created_at', 'updated_at')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'is_staff', 'is_superuser'),
        }),
    )


admin.site.register(User, CustomUserAdmin)
