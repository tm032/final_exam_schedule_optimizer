"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

View that handles the HTTP request to edit and analyze the schedule.
"""

from datetime import datetime, timedelta
import json
import csv
import re

from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from ..forms import ScheduleImportForm, CourseSearchForm
from ..internal import analyze, schedule
from ..models import (
    Course,
    CourseGroup,
    CourseGroupSchedule,
    Schedule,
    ScheduleVersion,
    Semester,
)


def main(request, schedule_pk):
    if request.method == "GET":
        """
        param schedule_pk: primary key for the schedule that is meant to be displayed
        displays the detailed view of the schedule, with the drag and drop area, issue summary, and issues details
        computes all the information needed to display the page then return it as context for the html file
        return analyzer.html
        """
        try:
            schedule_entry = Schedule.objects.get(pk=schedule_pk)
            semester_entry = schedule_entry.semester
            preference_profile = schedule_entry.preference_profile
            group_constraints = schedule_entry.group_constraints
            predefined_constraints = schedule_entry.predefined_constraints
            versions = schedule_entry.versions.all()
        except Schedule.DoesNotExist:
            return HttpResponseRedirect(reverse("index"))

        exam_indicides, max_index, num_days = get_indices(semester_entry.exam_start_date, semester_entry.exam_end_date, len(semester_entry.exam_start_times.split(",")))
        exam_times = semester_entry.exam_start_times.split(",")
        exam_times = [x.lstrip() for x in exam_times]

        times = get_exam_slots(semester_entry.exam_start_date, semester_entry.exam_end_date)

        exam_slots = []
        for i, exam_time in enumerate(exam_times):
            slots = exam_indicides[i]
            exam_slots.append({
                'time': exam_time,
                'slots': slots
            })

        try:
            slot2group = get_slot2group(schedule_entry, semester_entry.exam_start_date, semester_entry.exam_end_date)
        except ValueError as e:
            return HttpResponseRedirect(reverse("index"))
        
        context = {
            "schedule": schedule_entry,
            "semester": semester_entry.name,
            "exam_times": exam_times,
            "daily_num_exams": len(exam_times),
            "portfolio_id": schedule_entry.portfolio_id,
            "iterator" : list(range(len(exam_times) * num_days)),
            "exam_slots" : exam_slots,
            "schedule_dates_display": get_dates_display_list(semester_entry.exam_start_date, semester_entry.exam_end_date),
            "exam_indicies": exam_indicides,
            "exams": slot2group,
            "max_id": max_index,
            "form": ScheduleImportForm(),
            "issues": schedule.get_analysis_data(schedule_entry),
            "problems": schedule.get_problem_data(schedule_entry),
            "versions": versions,
            "num_slots": len(slot2group),
            "preference_profile": preference_profile,
            "group_constraints": group_constraints,
            "predefined_constraints": predefined_constraints,
            "schedule_pk" : schedule_pk,
        }
        
        context.update(get_course_group_display(schedule_entry.course_info))

        return render(request, "optimizer/analyzer.html", context)

def get_courses_info(entries):
    template_entries = []
    course_groups = []
    
    for crn in entries.keys():
        course_entry = entries[crn]
        template_entry = dict()
        template_entry["crn"] = crn
        template_entry["course_id"] = course_entry["course_id"]
        template_entry["title"] = course_entry['title']
        template_entry["instructor"] = course_entry['instructor']
        template_entry["meeting_times"] = course_entry['meeting_times'].replace(",", "<br/>")
        template_entry["course_group"] = course_entry["course_group"]

        template_entries.append(template_entry)
        
        if template_entry["course_group"] not in course_groups:
            course_groups.append(template_entry["course_group"])

    return template_entries, course_groups

def get_course_group_display(courses_info):
    search_form = CourseSearchForm()
    template_entries, course_groups = get_courses_info(courses_info)
    
    context = {
        'courses_info': template_entries,
        'course_groups': course_groups,
        'search_form': search_form,
        'entries': len(template_entries)
    }

    return context

def save(request):
    """
    called when you hit the green "save schedule" button after reanalyzing a schedule after drag and dropping
    gets what the current schedule looks like and saves that
    """
    if request.method == "GET":
        return HttpResponseRedirect(reverse("index"))
    else:
        received_data = json.loads(request.body)
        group2slot = received_data["group2slot"]
        schedule_pk = received_data["schedule_pk"]

        try:
            schedule_entry = Schedule.objects.get(pk=schedule_pk)
        except Schedule.DoesNotExist:
            return HttpResponse(status=500)

        schedule.save(schedule_entry, group2slot)
        return HttpResponse("The schedule is successfully saved")

def analyze_schedule(request, schedule_pk):
    """
    param schedule_pk: primary key for what schedule is being analyzed
    called when you reanalyze a schedule from the detailed schedule view
    gets the proper schedule, throws it into the analyzer and returns the results to the html page
    """
    try:
        schedule_entry = Schedule.objects.get(pk=schedule_pk)
    except Schedule.DoesNotExist:
        return HttpResponse(status=500)

    schedule.analyze(schedule_entry)
    issues_table = schedule.get_analysis_data(schedule_entry)
    problems = schedule.get_problem_data(schedule_entry)
    # json_data = json.dumps(issues_table)
    
    combined_data = {
        'issues': issues_table,
        'problems': problems,
    }

    # Convert to JSON
    json_data = json.dumps(combined_data)

    return HttpResponse(json_data, "application/json")




def get_schedule_version(request, version_pk):
    version = get_object_or_404(ScheduleVersion, pk=version_pk)
    issues = {
        'overlap':version.students_overlap,
        'three_in_24': version.students_3in24,
        'four_in_48': version.students_4in48,
        'back_to_back': version.students_b2b,
        'night_morning': version.students_night_morning,
        'f_overlap': version.faculty_overlap,
        'f_back_to_back': version.faculty_b2b,
    }
    return JsonResponse({
        'name': version.name,
        'group2slot': version.group2slot,
        'issues': issues
    })

@csrf_exempt
def update_schedule_version_name(request, version_id):
    if request.method == 'PATCH':
        try:
            version = ScheduleVersion.objects.get(pk=version_id)
            data = json.loads(request.body)
            new_name = data.get('name', None)
            print("NEW NAME IS: ", new_name)
            if new_name:
                version.name = new_name
                version.save()
                return JsonResponse({'message': 'Version name updated successfully'})
            else:
                return JsonResponse({'error': 'New name not provided'}, status=400)
        except ScheduleVersion.DoesNotExist:
            return JsonResponse({'error': 'Schedule version not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only PATCH requests are allowed'}, status=405)

def get_current_schedule(request, schedule_pk):
    schedule = get_object_or_404(Schedule, pk=schedule_pk)
    group2slot = schedule.group2slot if hasattr(schedule, 'group2slot') else {}
    issues = {
        'overlap': schedule.students_overlap,
        'three_in_24': schedule.students_3in24,
        'four_in_48': schedule.students_4in48,
        'back_to_back': schedule.students_b2b,
        'night_morning': schedule.students_night_morning,
        'f_overlap': schedule.faculty_overlap,
        'f_back_to_back': schedule.faculty_b2b,
    }
    return JsonResponse({
        'group2slot': group2slot,
        'issues': issues
    })

@csrf_exempt
@require_POST
def delete_schedule_version(request, version_id):
    """
    param version_id: id of the version to delete
    """
    try:
        version = ScheduleVersion.objects.get(id=version_id)
        version.delete()
        return JsonResponse({'success': True})
    except ScheduleVersion.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Version not found'}, status=404)

class ExamData:
    def __init__(self, name, is_special):
        self.name = name
        self.is_special = is_special

        if self.is_special:
            self.style_type = "bg-light"
        else:
            self.style_type = "bg-primary text-white"



def create_spreadsheet(request, schedule_pk):
    """
    param schedule_pk: primary key for what schedule we are working on
    called when you press create spreadsheet in the detailed schedule view
    downloads a csv file similar to the large table of detailed exams info normally published. It has blank fields for room information.
    """
    try:
        schedule_entry = Schedule.objects.get(pk=schedule_pk)
    except Schedule.DoesNotExist:
        return HttpResponse(status=404)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="schedule_{schedule_pk}.csv"'

    course_data = []
    course_group_schedule_entries = CourseGroupSchedule.objects.filter(schedule=schedule_entry)
    for course_group_schedule in course_group_schedule_entries:
        course_group = CourseGroup.objects.filter(name=course_group_schedule.name, semester=schedule_entry.semester)[0]
        courses = Course.objects.filter(course_group=course_group)
        time_info = timeslot_to_time(course_group_schedule.slot_id, schedule_entry.semester)
        for course in courses:
            course_data.append([
                course.course_identification, course.section, course.crn, course.instructor,
                "", "", "", time_info[0], time_info[1], time_info[2], time_info[3]])

    # Sort course data alphabetically by course name and then by section number
    sorted_course_data = sorted(course_data, key=lambda x: (x[0], int(x[1])))
    writer = csv.writer(response)
    writer.writerow(['Course', 'Section', 'CRN', 'Primary Instructor', 'Building', 'Room', 'Room Description', 'Exam Day', 'Exam Date', 'Start Time', 'End Time'])  # Write the CSV header
    for row in sorted_course_data:
        writer.writerow(row)

    # Create the HTTP response object with the appropriate CSV header.
    
    return response


def portfolio_summary(request, portfolio_id):
    """
    param porfolio_id: integer value representing which portfolio is trying to be viewed
    gets all schedules with the matching id, then displays both a summary table for them and their schedules
    runs when you hit show portfolio from schedule detailed view
    """
    schedules = Schedule.objects.filter(portfolio_id=portfolio_id)
    semester_entry = schedules[0].semester

    exam_indicides, max_index, num_days = get_indices(semester_entry.exam_start_date, semester_entry.exam_end_date, len(semester_entry.exam_start_times.split(",")))
    exam_times = semester_entry.exam_start_times.split(",")
    exam_times = [x.lstrip() for x in exam_times]

    times = get_exam_slots(semester_entry.exam_start_date, semester_entry.exam_end_date)

    exam_slots = []
    for i, exam_time in enumerate(exam_times):
        slots = exam_indicides[i]
        exam_slots.append({
            'time': exam_time,
            'slots': slots
        })
    info = []
    for schedule_entry in schedules:
        try:
            slot2group = get_slot2group(schedule_entry, semester_entry.exam_start_date, semester_entry.exam_end_date)
        except ValueError as e:
            return HttpResponseRedirect(reverse("index"))
        info.append( [schedule_entry.name, schedule.get_analysis_data(schedule_entry), schedule_entry.pk, slot2group])
    context = {
        "info" : info,
        "schedule": schedule_entry,
        "semester": semester_entry.name,
        "exam_times": exam_times,
        "daily_num_exams": len(exam_times),
        "iterator" : list(range(len(exam_times) * num_days)),
        "exam_slots" : exam_slots,
        "schedule_dates_display": get_dates_display_list(semester_entry.exam_start_date, semester_entry.exam_end_date),
        "exam_indicies": exam_indicides,
        "max_id": max_index,
        "form": ScheduleImportForm(),
        "num_slots": len(slot2group),
    }   
    return render(request, "optimizer/portfolio_summary.html", context)

"""
The rest of these are helper methods, mostly for main. they compute some information that is needed for displaying a page
"""
def get_slot2group(schedule_entry, start_date, end_date):
    duration = end_date - start_date
    slot2group = dict()
    for i in range(0, (duration.days + 1) * len(schedule_entry.semester.exam_start_times.split(","))):
        slot2group[i] = []

    group_entries = CourseGroupSchedule.objects.filter(schedule=schedule_entry)

    for course_group_schedule_entry in group_entries:
        name = course_group_schedule_entry.name
        timeslot = course_group_schedule_entry.slot_id
        is_special = re.search("^[MTWRFS]+[0-9]{4}$", name) # TODO - course_group_entry.is_special
        slot2group[timeslot].append(ExamData(name, is_special))
    
    return slot2group

def timeslot_to_time(timeslot, semester_entry):
    exam_strings = semester_entry.exam_start_times.split(",")
    daily_num_exams = len(exam_strings)
    exam_slot = int(timeslot % daily_num_exams)
    exam_day = int(timeslot // daily_num_exams)
    exam_time = datetime.strptime(exam_strings[exam_slot].lstrip(), "%I:%M %p")
    date = datetime(semester_entry.exam_start_date.year, semester_entry.exam_start_date.month, semester_entry.exam_start_date.day + exam_day,
                    hour= exam_time.hour, minute= exam_time.minute)
    day_of_week = date.strftime('%A')
    day = date.strftime('%B %d, %Y')
    time_of_day = date.strftime('%I:%M %p')
    time_of_day_plus_3_hours = (date + timedelta(hours=3)).strftime('%I:%M %p')
    return [day_of_week, day, time_of_day, time_of_day_plus_3_hours]
   
def get_dates_display_list(start_date, end_date):
    date_list = []
    current_date = start_date

    while current_date <= end_date:
        if current_date.weekday() < 5:
            date_list.append(current_date.strftime("%m/%d (%a)"))
        
        current_date += timedelta(days=1)

    return date_list

def get_indices(start_date, end_date, num_daily_exams):
    exam_indicies = dict()
    for i in range(0, num_daily_exams):
        exam_indicies[i] = []
    current_date = start_date
    index = 0
    num_days = 0

    while current_date <= end_date:
        if current_date.weekday() < 5: # if not the weekend
            num_days += 1
            for idx in range(0, num_daily_exams):
                exam_indicies[idx].append(index + idx)
        
        current_date += timedelta(days=1)
        index += num_daily_exams
    return exam_indicies, index, num_days

def get_exam_slots(start_date, end_date):
    time = dict()
    current_date = start_date
    index = 0
    slot = 0
    num_days = (end_date - start_date).days
    while current_date <= end_date:
        if current_date.weekday() < 5: # if not the weekend
            time[slot] = list(range(index, index + num_days-1))
        slot += 1
        current_date += timedelta(days=1)
        index += num_days-1
    return time, index