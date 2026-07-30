from django.contrib import admin
from .models import Enrollment


class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'course', 'status', 'enrolled_at')
    list_filter = ('status', 'enrolled_at')
    search_fields = ('student__email', 'course__title')


admin.site.register(Enrollment, EnrollmentAdmin)
