"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Defines admin webpage where admin can look at the database entries. Used for debugging and development.
"""

from django.contrib import admin

from .models import (
    Course,
    CourseGroup,
    CourseGroupSchedule,
    PreferenceProfile,
    Schedule,
    ScheduleVersion,
    Semester,
    PortfolioID,
)

# Register your models here.
admin.site.register(Semester)
admin.site.register(CourseGroupSchedule)
admin.site.register(Schedule)
admin.site.register(Course)
admin.site.register(CourseGroup)
admin.site.register(PreferenceProfile)
admin.site.register(ScheduleVersion)
admin.site.register(PortfolioID)
