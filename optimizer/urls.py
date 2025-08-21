"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Definition of URL on the website. This file defines which function handles the requests.
"""

from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.views.generic import TemplateView

from .views import analyze, dashboard, load, optimize, schedule_data, settings
from .views.create_preference_profile import create_preference_profile, preference_profile_list, delete_preference_profile
from .views.schedule_version import save_schedule_version


# Dummy function to generate the URL without the required parameters. Used together with jQuery populating the parameters.
def dummy(request):
    return HttpResponseRedirect(reverse("index"))

urlpatterns = [
    # Step 3: Dashboard page.
    path("", dashboard.main, name="index"),

    # Step 2: optimization page.
    path("optimize", optimize.main, name="optimize"),
    
    # Step 1: Settings page.
    path("settings", settings.choose_semester, name="settings"),
    
    # Viewing a specific semester's settings.
    path("settings/<int:pk>", settings.main, name="settings"),

    # Update a specific course group assignment.    
    path("update_group", settings.update_group, name="update_group"),

    
    # Viewing a specific semester's conflict matrix.
    path("settings/show_matrix/<int:pk>", settings.show_overlap_matrix, name="show_matrix"),

    # Deleting a Schedule.
    path("delete_schedule/<int:schedule_pk>", dashboard.delete, name="delete"),

    # Loading a new semester.
    path("load", load.main, name="load"),

    # Deleting a semester.
    path('semester/delete/<int:pk>/', settings.delete_semester, name='delete_semester'),

    # Optimization requests.
    path("begin_optimization/", optimize.begin, name="begin_optimization"),
    path("optimize_portfolio", optimize.create_schedule_portfolio, name="optimize_portfolio"),
    
    # Analyzing a schedule.
    path("analyze/<int:schedule_pk>", analyze.analyze_schedule, name="analyze"),

    # Analysis related URLs.
    path("portfolio_summary/<int:portfolio_id>/", analyze.portfolio_summary, name="portfolio_summary"), 
    path("save", analyze.save, name="save"),
    path("schedule/", dummy, name="schedule_dummy"),
    path("schedule/<int:schedule_pk>", analyze.main, name="schedule"),
    path("save_schedule_version", save_schedule_version, name="save_schedule_version"),
    path('schedule/version/<int:version_pk>/', analyze.get_schedule_version, name='get_schedule_version'),
    path('schedule/version/update/<int:version_id>/', analyze.update_schedule_version_name, name='update_schedule_version_name'),
    path('schedule/current/<int:schedule_pk>/', analyze.get_current_schedule, name='get_current_schedule'),
    path('schedule/version/delete/<int:version_id>/', analyze.delete_schedule_version, name='delete_schedule_version'),
    path('schedule/create_spreadsheet/<int:schedule_pk>/', analyze.create_spreadsheet, name='create_spreadsheet'),

    # Importing and exporting course groups.
    path("import_course_group/<int:semester_pk>", schedule_data.import_course_group, name="import_course_group"),
    path("export_course_group/<int:semester_pk>", schedule_data.export_course_group, name="export_course_group"),
    path('export_cg_from_schedule/<int:schedule_pk>', schedule_data.export_course_group_from_schedule, name="export_cg_from_schedule"),

    path("get_semester_course_data/<int:semester_pk>", optimize.get_semester_course_data, name="get_semester_course_data"),
    path("get_semester_course_data/", dummy, name="get_semester_course_data_dummy"),

    # Creating and managing preference profiles.
    path('create_preference_profile/', create_preference_profile, name='create_preference_profile'),
    path('preference_profiles/', preference_profile_list, name='preference_profile_list'),
    path('preference_profile/<int:pk>/delete/', delete_preference_profile, name='delete_preference_profile'),
    path('preference_profile_success/', TemplateView.as_view(template_name="create_preference_profile_success.html"), name='preference_profile_success'),  # Example success page
]
