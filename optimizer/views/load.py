"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

View that loads the schedule file in the beginning.
"""

from django.shortcuts import render
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect

from ..forms import LoaderForm
from ..models import Semester
from ..internal import read_data, create_model

import pandas as pd
import datetime
"""
view for loading in a new semester object. validates the data and, if valid, creates a DataParser object which creates the semester
"""
def main(request):
    fall_name, fall_special, spring_name, spring_special = get_previous_special_courses()
    if request.method == "GET":
        context = {
            "form": LoaderForm(),
            "fall_name" : fall_name,
            "fall_special" : fall_special,
            "spring_name" : spring_name,
            "spring_special": spring_special,
        }
        return render(request, "optimizer/load.html", context)
    else:
        form = LoaderForm(request.POST, request.FILES)
        
        if form.is_valid():
            # file = request.FILES["schedule_file"]
            semester = form.cleaned_data["semester"]
            start_date = form.cleaned_data["start_date"]
            end_date = form.cleaned_data["end_date"]
            student_csv = form.cleaned_data["student_file_csv"]
            course_csv = form.cleaned_data["course_file_csv"]
            special_courses = comma2list(form.cleaned_data["special_courses"])
            no_exam_crns = comma2list(form.cleaned_data["no_exam_crns"])
            times = form.cleaned_data['times']

            if "/" in semester or "\\" in semester:
                context = {
                'form': form,
                'errors': "<b>Error: Cannot have slashes in the name of the semsester.</b>"
                }
                return render(request, "optimizer/load.html", context)

            if start_date > end_date:
                context = {
                'form': form,
                'errors': "<b>Error: Exam start date is after exam end date.</b>"
                }
                return render(request, "optimizer/load.html", context)
            

            if end_date - start_date <= datetime.timedelta(days=3):
                context = {
                'form': form,
                'errors': "<b>Error: Exam period is less than four days.</b>"
                }
                return render(request, "optimizer/load.html", context)
            
            if end_date - start_date > datetime.timedelta(days=10):
                context = {
                'form': form,
                'errors': "<b>Error: Exam period is more than 10 days.</b>"
                }
                return render(request, "optimizer/load.html", context)
            
            print("Read:", student_csv, course_csv, semester)

            parser = read_data.DataParser(student_csv=student_csv, schedule_csv=course_csv, semester=semester, start_date=start_date, end_date=end_date, exam_times=times, special_course_string=form.cleaned_data["special_courses"])
            data = parser.read_data(special_courses, no_exam_crns)


            context = {
                'form': LoaderForm(),
                'errors': "The data is loaded successfully."
            }
            return HttpResponseRedirect(reverse("settings"))
        
        else:
            print(form.errors)
            
            context = {
                'form': form,
                'errors': form.errors
            }
            return render(request, "optimizer/load.html", context)


def comma2list(comma_separated):
    result_list = comma_separated.replace(' ', '').split(",")

    if result_list is None:
        result_list = []
    return result_list


def get_previous_special_courses():
    # Get the most recent academic periods for Fall and Spring
    latest_fall = Semester.objects.filter(academic_period__icontains='Fall').order_by('-academic_period').first()
    latest_spring = Semester.objects.filter(academic_period__icontains='Spring').order_by('-academic_period').first()

    if latest_fall is None:
        latest_fall_academic_period = ""
        fall_special = ""
    else:
        latest_fall_academic_period = latest_fall.academic_period
        
        # Get all semesters for the latest Fall and Spring academic periods
        fall_semesters = Semester.objects.filter(academic_period=latest_fall.academic_period)
        # Convert QuerySets to lists
        fall_semesters_list = list(fall_semesters)
        unique_fall = set()
        # Extract special courses from fall semesters
        for semester in fall_semesters_list:
            if semester.special_courses:
                courses = semester.special_courses.split(", ")
                unique_fall.update(courses)
                
        # Combine the unique courses into a single string
        fall_special = ", ".join(sorted(unique_fall))


    if latest_spring is None:
        latest_spring_academic_period = ""
        spring_special = ""
    else:
        latest_spring_academic_period = latest_spring.academic_period
        
        # Get all semesters for the latest Fall and Spring academic periods
        spring_semesters = Semester.objects.filter(academic_period=latest_spring.academic_period)
        # Convert QuerySets to lists
        spring_semesters_list = list(spring_semesters)
        unique_spring = set()
        # Extract special courses from fall semesters
        for semester in spring_semesters_list:
            if semester.special_courses:
                courses = semester.special_courses.split(", ")
                unique_spring.update(courses)
                
        # Combine the unique courses into a single string
        spring_special = ", ".join(sorted(unique_fall))

    return latest_fall_academic_period, fall_special, latest_spring_academic_period, spring_special
