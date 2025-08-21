"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

View that handles the setting page where users can change course groupings.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse


from ..forms import CourseSearchForm, CourseGroupImportForm
from ..models import CourseGroup, Course, Semester

from ..internal import read_data, create_model
import re
import json
import os
import copy
from functools import cmp_to_key

def choose_semester(request):
    semester_entries = Semester.objects.all().order_by("-date_created")
    
    if len(semester_entries) == 0:
        return HttpResponseRedirect(reverse("load"))

    semesters = []
    for semester_entry in semester_entries:
        semester_info = dict()
        semester_info["academic_period"] = semester_entry.academic_period
        semester_info["name"] = semester_entry.name
        semester_info["start"] = semester_entry.exam_start_date.strftime("%m/%d/%Y (%a)")
        semester_info["end"] = semester_entry.exam_end_date.strftime("%m/%d/%Y (%a)")
        semester_info["pk"] = semester_entry.pk
        semesters.append(semester_info)

    context = {
        "semesters": semesters,
    }

    return render(request, "optimizer/choose_semester.html", context)

def main(request, pk):
    if request.method == "GET":
        search_form = CourseSearchForm()

        try:
            semester_entry = Semester.objects.get(pk=pk)
        except Semester.DoesNotExist:
            return choose_semester(request)

        courses_info = get_courses_info(Course.objects.filter(semester=semester_entry).order_by("crn"))
        
        exam_times = semester_entry.exam_start_times
        context = {
            "academic_period": semester_entry.academic_period,
            "semester": semester_entry.name,
            "semester_pk": pk,
            'start_date': semester_entry.exam_start_date.strftime("%m/%d/%Y (%a)"),
            'end_date': semester_entry.exam_end_date.strftime("%m/%d/%Y (%a)"),
            'exam_times': exam_times, 
            'special_courses':semester_entry.special_courses,
            'courses_info': courses_info,
            'course_groups': get_course_group_list(semester_pk=pk),
            'search_form': search_form,
            'import_form': CourseGroupImportForm(),
            'entries': len(courses_info)
        }

        return render(request, "optimizer/settings.html", context)
    else:
        form = CourseSearchForm(request.POST)
        if form.is_valid():
            method = int(form.cleaned_data["search_method"])
            query = form.cleaned_data["search_field"]
            only_ambiguous = form.cleaned_data["ambiguous"]
            entries = None

            try:
                semester_entry = Semester.objects.get(pk=pk)
            except Semester.DoesNotExist:
                return choose_semester(request)

            print(method, query, only_ambiguous)

            if query == "":
                entries = Course.objects.filter(semester=semester_entry).order_by("crn")
            elif method == CourseSearchForm.USE_CRN:
                entries = Course.objects.filter(semester=semester_entry, crn__contains=query).order_by("crn")
            elif method == CourseSearchForm.USE_FACULTY_NAME:
                entries = Course.objects.filter(semester=semester_entry, instructor__icontains=query).order_by("section").order_by("course_identification")
            elif method == CourseSearchForm.USE_COURSE_NAME:
                entries = Course.objects.filter(semester=semester_entry, title__icontains=query).order_by("section").order_by("course_identification")
            elif method == CourseSearchForm.USE_COURSE_NUMBER:
                course_with_section = re.match(r"([a-zA-Z]{4}[0-9]{3})[\s]+([\S]*)", query)

                if course_with_section:
                    entries = Course.objects.filter(semester=semester_entry, course_identification__icontains=course_with_section.group(1), section__icontains=course_with_section.group(2)).order_by("section").order_by("course_identification")
                else:
                    entries = Course.objects.filter(semester=semester_entry, course_identification__icontains=query).order_by("section").order_by("course_identification")
            elif method == CourseSearchForm.USE_COURSE_GROUP:
                try:
                    group = CourseGroup.objects.get(semester=semester_entry, name=query)
                    entries = Course.objects.filter(semester=semester_entry, course_group=group).order_by("section").order_by("course_identification")
                except CourseGroup.DoesNotExist:
                    entries = []
            else:
                entries = []

            if entries != [] and only_ambiguous:
                entries = entries.filter(clear=False)

            json_data = json.dumps(get_courses_info(entries))
            return HttpResponse(json_data, content_type="application/json")

        else:
            print(form.errors)
            
            context = {
                'form': form,
                'errors': form.errors
            }
            return render(request, "optimizer/load.html", context)


def get_courses_info(entries):
    template_entries = []
    for course_entry in entries:
        template_entry = dict()
        template_entry["ambiguous"] = '<span class="text-success">Clear</span>' if course_entry.clear else '<span class="text-danger">Ambiguous</span>'
        template_entry["crn"] = course_entry.crn
        template_entry["course_id"] = course_entry.course_identification + " " + course_entry.section
        template_entry["title"] = course_entry.title
        template_entry["instructor"] = course_entry.instructor
        template_entry["meeting_times"] = course_entry.meeting_times.replace(",", "<br/>")
        template_entry["course_group"] = course_entry.course_group.name

        template_entries.append(template_entry)

    return template_entries



def get_course_group_list(remove_no_exam=True, semester_pk=None):
    if semester_pk == None:
        entries = CourseGroup.objects.all()
    else:
        semester_entry = Semester.objects.get(pk=semester_pk)
        entries = CourseGroup.objects.filter(semester=semester_entry) 

    course_groups = list()
    for course_group_entry in entries:
        if remove_no_exam and course_group_entry.name == "NO_EXAM":
            continue
        if course_group_entry.name not in course_groups:
            course_groups.append(course_group_entry.name)
    
    return course_groups

def update_group(request):
    if request == "GET":
        return HttpResponseRedirect(reverse("settings"))
    else:
        data = json.loads(request.body)
        crn = int(data["CRN"])
        group = data["course_group"]
        semester_entry = Semester.objects.get(name=data["semester"])

        return_data = dict()

        is_special = True

        if re.search("^[MTWRFS]+[0-9]{4}$", group):
            is_special = False

        try:
            course_group, created = CourseGroup.objects.get_or_create(semester=semester_entry, name=group, is_special=is_special)
            course = Course.objects.get(semester=semester_entry, crn=crn)
            old_group = course.course_group
            course.course_group = course_group
            course.clear = True

            if is_special:
                course.type = Course.SPECIAL_COURSE

            course.save()

            course_count = Course.objects.filter(course_group=old_group).count()
            if course_count == 0:
                old_group.delete()

            return_data['status'] = "success"
            return_data['created'] = created
            return_data['new_group'] = course_group.name
        except Course.DoesNotExist:
            return_data['status'] = "fail"

        json_data = json.dumps(return_data)
        return HttpResponse(json_data, content_type="application/json")

def delete_semester(request, pk):
    semester = get_object_or_404(Semester, pk=pk)
    if request.method == 'POST':
        try:
            file_path = os.path.join(os.getcwd(), semester.students_file.name)
            os.remove(file_path)
        except:
            print("no student file found at", os.path.join(os.getcwd(), semester.students_file.name))
        semester.delete()
        return HttpResponseRedirect(reverse("settings"))
    return render(request, 'confirm_delete.html', {'object': semester})

def show_overlap_matrix(request, pk):
    semester = get_object_or_404(Semester, pk=pk)
    model_creator = create_model.ModelCreator(semester)
    student_enrollment = model_creator.matrix_information_retrival()
    all_names = model_creator.params["G"]
    matrix = []
    course_names, time_names = [], []
    max_value = 1

    for name in all_names:
        if is_time_name(name):
            time_names.append(name)
        else:
            course_names.append(name)

    # Sort time names by custom sorting
    time_names = sort_time_names(time_names)
    # Sort course name in alphabetical order
    course_names.sort()

    # Concatenate the lists
    sorted_list = course_names + time_names

    cp = copy.deepcopy(sorted_list)
    cp.insert(0, "")
    matrix.append(cp)

    for row in sorted_list:
        row_data = []
        row_data.append(row)
        for col in sorted_list:
            if row == col:
                overlap = student_enrollment[row]
            else:
                overlap =  student_enrollment[(row, col)]
            if overlap > max_value:
                max_value = overlap
            row_data.append(overlap)
        matrix.append(row_data) 

    return render(request, 'optimizer/overlap_matrix.html', {'matrix': matrix, "max_value":max_value, "pk": pk})

def is_time_name(name):
    if not name.isalnum():
        return False
    time_str = name[len(name) - 4:len(name)]
    return len(time_str) == 4 and time_str.isnumeric()

def sort_time_names(names):
    day_order = "MTWRF"
    
    def compare_days(days1, days2):
        for d1, d2 in zip(days1, days2):
            if d1 != d2:
                return day_order.index(d1) - day_order.index(d2)
        # If one string is a prefix of the other, the longer string should come first, eg: MWF comes before MW
        return len(days2) - len(days1)
    
    def sort_key(course):
        # Separate the letters and numbers
        for i, char in enumerate(course):
            if char.isdigit():
                days = course[:i]
                time_str = course[i:]
                break
        else:
            days = course
            time_str = ""
        
        return (days, time_str)
    
    def compare_time_names(name1, name2):
        days1, time_str1 = sort_key(name1)
        days2, time_str2 = sort_key(name2)
        
        # Compare days first
        day_comparison = compare_days(days1, days2)
        if day_comparison != 0:
            return day_comparison
        
        # If days are the same, compare time strings
        if time_str1 < time_str2:
            return -1
        elif time_str1 > time_str2:
            return 1
        else:
            return 0

    return sorted(names, key=cmp_to_key(compare_time_names))
