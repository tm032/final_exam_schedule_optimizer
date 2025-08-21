
""" 
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

View that handles the HTTP request to save the schedule version.
"""
import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from ..models import Schedule, ScheduleVersion


@csrf_exempt
def save_schedule_version(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        schedule_pk = data.get('schedule_pk')
        group2slot = data.get('group2slot')
        summary = data.get('summary')
        issues = summary['issues']
        problems = summary['problems']
        print(problems.keys())

        schedule = get_object_or_404(Schedule, pk=schedule_pk)
        schedule_version = ScheduleVersion.objects.create(
            schedule=schedule,
            group2slot=group2slot,
            students_overlap=issues.get('student_overlap'),
            students_3in24=issues.get('three_in_24'),
            students_4in48=issues.get('four_in_48'),
            students_b2b=issues.get('student_back_to_back'),
            students_night_morning=issues.get('night_morning'),
            faculty_overlap=issues.get('faculty_overlap'),
            faculty_b2b=issues.get('faculty_back_to_back'),

            student_overlap_problems=problems.get('student_overlap'),
            student_3in24_problems=problems.get('three_in_24'),
            student_4in48_problems=problems.get('four_in_48'),
            student_b2b_problems=problems.get('student_back_to_back'),
            student_night_morning_problems=problems.get('night_morning'),
            faculty_overlap_problems=problems.get('faculty_overlap'),
            faculty_b2b_problems=problems.get('faculty_back_to_back'),
        )

        return JsonResponse({"message": "Schedule version saved successfully"})
    return JsonResponse({'error': 'Invalid request'}, status=400)