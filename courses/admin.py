from django.contrib import admin

from .models import Course, Module, Lesson, Resource, LessonProgress, Tag

admin.site.register(Course)
admin.site.register(Module)
admin.site.register(Lesson)
admin.site.register(Resource)
admin.site.register(LessonProgress)
admin.site.register(Tag)
