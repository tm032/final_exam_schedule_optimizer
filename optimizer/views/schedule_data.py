"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

View that exports or imports schedules in json file.
"""

from ..models import CourseGroup, Course, Semester, Schedule
from django.http import HttpResponse, HttpResponseRedirect
from ..forms import ScheduleImportForm, CourseGroupImportForm
from django.conf import settings
from django.urls import reverse
import json

def export_course_group_from_schedule(request, schedule_pk):
    schedule_entry = Schedule.objects.get(pk=schedule_pk)
    course_info = schedule_entry.course_info
    send_data = {
        "crn2group": {}
    }
    
    for crn in course_info.keys():
        course_group = course_info[crn]["course_group"]
        is_clear = course_info[crn]["is_clear"] if "is_clear" in course_info[crn] else False
        send_data["crn2group"][int(crn)] = (course_group, is_clear)

    json_data = json.dumps(send_data)

    response = HttpResponse(json_data, content_type='application/json')
    return response
    

def export_course_group(request, semester_pk):
    send_data = {
        "crn2group": {}
    }

    semester_entry = Semester.objects.get(pk=semester_pk)

    course_entries = Course.objects.filter(semester=semester_entry)
    
    for course in course_entries:
        send_data["crn2group"][int(course.crn)] = (course.course_group.name, False)

    json_data = json.dumps(send_data)

    response = HttpResponse(json_data, content_type='application/json')
    return response

def import_course_group(request, semester_pk):
    if request.method == "POST":
        form = CourseGroupImportForm(request.POST, request.FILES)
        if form.is_valid():
            json_file = request.FILES["group_file"]
            received_data = json.loads(json_file.read())
            semester_entry = Semester.objects.get(pk=semester_pk)

            for crn in received_data["crn2group"].keys():
                course_group_name, clear = received_data["crn2group"][crn]

                try:
                    course = Course.objects.get(semester=semester_entry, crn=crn)
                    new_group, created = CourseGroup.objects.get_or_create(semester=semester_entry, name=course_group_name)
                    if course_group_name in semester_entry.special_courses:
                        course.clear = False
                        course.save()
                        continue
                    old_group = course.course_group
                    course.course_group = new_group
                    course.clear = clear
                    course.save()            

                except Course.DoesNotExist:
                    print("Course not found CRN=" + str(crn))
                except Exception:
                    print("error in loading course, please manually vet this output")
                    course.clear = False
                    course.save()

    return HttpResponseRedirect(reverse("settings", args=(semester_pk,)))
