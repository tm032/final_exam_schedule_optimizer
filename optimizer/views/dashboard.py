"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

View that displays the analyzer dashboard.
Retrieves exam data and displays them in the draggable table.
"""

import datetime

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from ..forms import ScheduleImportForm
from ..internal import schedule
from ..models import Course, CourseGroup, Schedule, ScheduleVersion

"""
This view handles displaying all schedules for the user so they can view each one in detail or just see their status from this page
"""
def main(request):
    context = {
        "schedules": get_schedule_data()
    }   

    return render(request, "optimizer/dashboard.html", context)

def delete(request, schedule_pk):
    try:
        schedule_entry = Schedule.objects.get(pk=schedule_pk)
    except Schedule.DoesNotExist:
        return HttpResponseRedirect(reverse("index"))
    
    schedule.delete(schedule_entry)
    return HttpResponseRedirect(reverse("index"))


def get_schedule_data():
    schedules_data = []
    
    schedule_entries = Schedule.objects.all().order_by("-semester__exam_start_date")
    for schedule_entry in schedule_entries:
        schedule_info = dict()
        schedule_info["name"] = schedule_entry.name
        schedule_info["pk"] = schedule_entry.pk
        schedule_info["semester"] = schedule_entry.semester.name
        schedule_info["observable"] = int(schedule_entry.status) == Schedule.ANALYZED or int(schedule_entry.status) == Schedule.NOT_YET_ANALYZED
        schedule_info["status_label"] = schedule_entry.get_status()
        schedules_data.append(schedule_info)

    return schedules_data