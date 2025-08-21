"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Optimization view that sets initial constraints, conducts phase 1 and 2 optimization, and analyze the results.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ExamScheduling.settings")
django.setup()

from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
import datetime
import json
import html
import os
import django
import traceback
from django.conf import settings

from ..internal import optimize, analyze, schedule
from .settings import get_course_group_list
from ..models import CourseGroup, Semester, Schedule, PreferenceProfile, PortfolioID


def main(request):
    context = {
        "course_groups": get_course_group_list(remove_no_exam=True),
        "optimizationType": PreferenceProfile.objects.all(),
        "semesters": get_semesters() 
    }
    return render(request, "optimizer/optimize.html", context)

def get_semesters():
    semesters = []
    semester_entries = Semester.objects.all().order_by("-exam_start_date")
    for semester_entry in semester_entries:
        semester = dict()
        semester["name"] = semester_entry.name
        semester["pk"] = semester_entry.pk
        semesters.append(semester)

    return semesters

def get_semester_course_data(request, semester_pk):
    semester_entry = Semester.objects.get(pk=semester_pk)
    end_date = semester_entry.exam_end_date
    available_slot = {}

    time_strings = semester_entry.exam_start_times.split(",")
    daily_num_exams = len(time_strings)
    duration = semester_entry.exam_end_date - semester_entry.exam_start_date
    last_exam_time = datetime.datetime.strptime(time_strings[daily_num_exams - 1].lstrip(), "%I:%M %p").time()
    total_exams = (duration.days + 1) * daily_num_exams

    for timeslot in range(0, total_exams -1):
        date = timeslot_to_time(semester_entry, timeslot)
        if (date.weekday() > 4): # remove weekends slot.
            continue
        if (date.date() == end_date or date.weekday() == 4) and date.time() == last_exam_time: # if it is the last block and either a friday or the last day.
            continue
        available_slot[timeslot] = date.strftime("%m/%d (%a) %I:%M %p")

    return_data = dict()
    return_data["timeslot"] = available_slot
    return_data["course_group"] = get_course_group_list(remove_no_exam=True, semester_pk=semester_entry.pk)
    
    json_data = json.dumps(return_data)
    return HttpResponse(json_data, content_type="application/json")

def begin(request):
    """
    Creates a new schedule by the user's inputs. pulls information from the form the user filled up and was a part of parameter request
    Begins by finding the semester object. Then solves phase1 to narrow the problem down, then solves phase2 to optimality
    IMPORTANT VALUES ARE SET INSIDE THIS FUNCTION
    The phase1 call has an argument for a list of numbers. For each INTEGER in this list, a process will be created to optimize phase1 for that many courses
    phase1 call has an argument for an INTEGER to set the time limit for phase1. This is used as a time limit for grasp and time minimum for scip, so longer is potentially a better solve
    phase1 call has a boolean argument as to whether or not to use grasp to warm scip phase1, this sometimes produces better, sometimes worse solutions
    param request: html request by the browser
    param semester_pk: database id to select the semester to optimize for
    """
    if request.method == "GET":
        return HttpResponseRedirect(reverse("optimize"))
    else:
        try:
            data = json.loads(request.body)

            print(request.body)
            preference_profile_id = data["opt_type"]
            preference_profile = PreferenceProfile.objects.get(pk=preference_profile_id)

            semester_pk = data["semester_pk"]
            schedule_name = html.escape(data["schedule_name"])
            opt_type = data["opt_type"]
            constraints = data["constraints"]
            no_last_day = comma2list(data["nolastday"])
            no_last_2days = comma2list(data["nolast2days"])
            no_night = comma2list(data["nonight"])
            no_fri_mon = comma2list(data["no_fri_mon"])
            predefined_constraints = data["predefined_constraints"]

            group2slot = dict()
            for entry in constraints:
                group2slot[entry["course_group"]] = entry["timeslot"]

            group_constraints = {
                "no_last_day": no_last_day,
                "no_last_2days": no_last_2days,
                "no_night": no_night,
                "no_fri_mon": no_fri_mon
            }


            predefined_constraints_dict = dict()
            for entry in predefined_constraints:
                predefined_constraints_dict[entry["course_group"]] = entry["timeslot"]
            

            semester_entry = Semester.objects.get(pk=semester_pk)
            
            for catagory in group_constraints:
                for course in group_constraints[catagory]:
                    print("course:", course)
            
            
            no_group2slot = get_no_group2slot(semester_entry, no_last_day, no_last_2days, no_night, no_fri_mon)

            time_strings = semester_entry.exam_start_times.split(",")
            daily_num_exams = len(time_strings)
            duration = semester_entry.exam_end_date - semester_entry.exam_start_date
            total_exams = (duration.days + 1) * daily_num_exams

            optimizer = optimize.ExamOptimizer(semester_pk, group2slot, no_group2slot)
            course_info = optimizer.get_course_info()
            
            # Schedule is created with the name and semester, but no timeslot information yet
            schedule_entry = initialize_schedule(schedule_name, semester_entry, course_info, penalties=preference_profile.get_penalty_dictionary(), group_constraints=group_constraints, predefined_constraints=predefined_constraints_dict)   

            # Phase 1 optimization
            phase1_group2slot = phase1(optimizer, 
                                       schedule_entry, 
                                       group2slot, 
                                       total_exams, 
                                       settings.PHASE_1_NUM_COURSES, 
                                       preference_profile.get_phase1_penalty_dictionary(), 
                                       settings.PHASE_1_TIME_LIMIT, 
                                       settings.USE_GRASP)
            
            if -1 in phase1_group2slot: #-1 indicates model was found to be infeasible
                schedule.update_status(schedule_entry, Schedule.INFEASIBLE)
                return HttpResponse(status=200)
            
            # Phase 2 optimization.
            phase2_group2slot, cost = phase2(optimizer, schedule_entry, preference_profile.get_penalty_dictionary(), total_exams, phase1_group2slot)
    
        # next, update the Schedule by specifying which group belongs to which exam slot
            schedule.save(schedule_entry, phase2_group2slot)
            # next analyze to generate the summary table (number of cases for each type of constraint)
            schedule.analyze(schedule_entry)
            return HttpResponse(status=200)
        except Exception as e:
            schedule.update_status(schedule_entry, Schedule.ERROR)
            print(traceback.format_exc())
            return HttpResponse(status=200)


def comma2list(comma_separated):
    result_list = comma_separated.replace(' ', '').split(",")

    if result_list is None:
        result_list = []
    elif len(result_list) == 1 and len(result_list[0]) == 0:
        result_list = []
    return result_list

def get_no_group2slot(semester_entry, no_last_day, no_last_2days, no_night, no_fri_mon):
    """
    Converts the user inputted constraints into formats easier to work with
    param semester_entry: the semester object currently being worked on
    param schedule_entry: schedule object currently being worked on
    param no_last_day: list of courses that should not be placed on the last day
    param no_last_2days: list of courses that should not be placed on the last 2 days
    you get the point
    returns dict of the form {course: [t1, t2]} where t1 and t2 are disallowed times for the course
    """
    no_group2slot = dict()
    daily_num_exams = len(semester_entry.exam_start_times.split(","))
    duration = semester_entry.exam_end_date - semester_entry.exam_start_date
    total_exams = (duration.days + 1) * daily_num_exams
    for course_group in no_last_day:
       for i in range(total_exams - daily_num_exams, total_exams-1):
            _add_element(no_group2slot, course_group, i, semester_entry)

    for course_group in no_last_2days:
        for i in range(total_exams - (2 * daily_num_exams), total_exams-1):
                _add_element(no_group2slot, course_group, i, semester_entry)

    for course_group in no_night:
        for i in range(total_exams-1):
            if i % daily_num_exams == daily_num_exams - 1:
                _add_element(no_group2slot, course_group, i, semester_entry)

    mon_fri_slots = []
    for i in range(0, total_exams - 1):
        date = timeslot_to_time(semester_entry, i)
        if (date.weekday() == 0 or date.weekday() == 4): # if it is monday or friday
            mon_fri_slots.append(i)

    for course_group in no_fri_mon:
        for slot in mon_fri_slots:
            _add_element(no_group2slot, course_group, slot, semester_entry)
            
    return no_group2slot

def _add_element(no_group2slot, course_group, timeslot, semester):
    try:
        CourseGroup.objects.get(name=course_group, semester=semester)
        if course_group in no_group2slot:
            no_group2slot[course_group] += [timeslot]
        else:
            no_group2slot[course_group] = [timeslot]
    except CourseGroup.DoesNotExist:
        print(course_group)
    



def phase0(semester_pk, constraints, no_group2slot, schedule_entry):
    schedule.update_status(schedule_entry, Schedule.PHASE_0)
    optimizer = optimize.ExamOptimizer(semester_pk, constraints, no_group2slot)
    return optimizer

def phase1(optimizer, schedule_entry, group2slot, num_exam_slots, num_phase1_courses, preference_profile, time_limit, warm_start_grasp):
    schedule.update_status(schedule_entry, Schedule.PHASE_1)
    phase1_group2slot = optimizer.SCIP_optimize_phase1(num_exam_slots, num_phase1_courses, preference_profile, time_limit, warm_start_grasp)
    return phase1_group2slot

def phase2(optimizer, schedule_entry, preference_profile, num_exam_slots, group2slot):
    output_dir = os.path.join(settings.OPT_HOME_DIR, schedule_entry.name)
    os.makedirs(output_dir, exist_ok=True)
    schedule.update_status(schedule_entry, Schedule.PHASE_2)
    phase2_group2slot, cost = optimizer.SCIP_optimize_phase2(preference_profile, group2slot, num_exam_slots, output_dir)
    
    print(phase2_group2slot)
    
    return phase2_group2slot, cost

# Create a Schedule instance without specifying timeslot information.
def initialize_schedule(schedule_name, semester_entry, course_info, penalties, group_constraints={}, predefined_constraints={}):
    if schedule_name == "":
        schedule_name = str(semester_entry.name)
    
    return schedule.create(schedule_name, semester_entry, course_info, penalties, group_constraints, predefined_constraints)

def timeslot_to_time(semester_entry, timeslot):
        exam_strings = semester_entry.exam_start_times.split(",")
        daily_num_exams = len(exam_strings)
        exam_slot = int(timeslot % daily_num_exams)
        exam_day = int(timeslot // daily_num_exams)

        exam_time = datetime.datetime.strptime(exam_strings[exam_slot].lstrip(), "%I:%M %p")
        date = datetime.datetime(semester_entry.exam_start_date.year, semester_entry.exam_start_date.month, semester_entry.exam_start_date.day + exam_day,
                        hour= exam_time.hour, minute= exam_time.minute)
        return date  



def create_schedule_portfolio(request):
    SURVEY_PENALTY = {
            "overlap": 1,
            "threein24": 0.075,
            "fourin48": 0.0068,
            "B2B": 0.064,
            "PMtoAM": 0.059,
            "night": 0,
            "facultyoverlap": 0.2,
            "facultyB2B": 0.1,
        }
    SLEEPY_STUDENT_PENALTY = {
                "overlap": 1,
                "threein24": 0.1,
                "fourin48": 0.05,
                "B2B": 0.03,
                "PMtoAM": 0.06,
                "night": 0,
                "facultyoverlap": 0.2,
                "facultyB2B": 0.1,
            }
    PRIORITIZE_FACULTY_PENALTY = {
                "overlap": 1,
                "threein24": 0.1,
                "fourin48": 0.04,
                "B2B": 0.05,
                "PMtoAM": 0.05,
                "night": 0,
                "facultyoverlap": 10,
                "facultyB2B": 2,
            }
    SHORT_ATTENSION_SPAN_PENALTY = {
                "overlap": 1,
                "threein24": 0.12,
                "fourin48": 0.05,
                "B2B": 0.06,
                "PMtoAM": 0.04,
                "night": 0,
                "facultyoverlap": 0.2,
                "facultyB2B": 0.1,
            }
    print("running portfolio")
    if request.method == "GET":
        return HttpResponseRedirect(reverse("optimize"))
        
    penalties = [("Survey", SURVEY_PENALTY), ("Less Night to Morning", SLEEPY_STUDENT_PENALTY), ("Minimize Back to Back", SHORT_ATTENSION_SPAN_PENALTY), ("Prioritize Faculty", PRIORITIZE_FACULTY_PENALTY)]
    # penalties = [("Survey", SURVEY_PENALTY), ("Less Night to Morning", SLEEPY_STUDENT_PENALTY)]
    data = json.loads(request.body)

    print(request.body)

    semester_pk = data["semester_pk"]
    schedule_name = html.escape(data["schedule_name"])
    constraints = data["constraints"]
    no_last_day = comma2list(data["nolastday"])
    no_last_2days = comma2list(data["nolast2days"])
    no_night = comma2list(data["nonight"])
    no_fri_mon = comma2list(data["no_fri_mon"])
    predefined_constraints = data["predefined_constraints"]

    group2slot = dict()
    for entry in constraints:
        group2slot[entry["course_group"]] = entry["timeslot"]

    group_constraints = {
        "no_last_day": no_last_day,
        "no_last_2days": no_last_2days,
        "no_night": no_night,
        "no_fri_mon": no_fri_mon
    }

    predefined_constraints_dict = dict()
    for entry in predefined_constraints:
        predefined_constraints_dict[entry["course_group"]] = entry["timeslot"]
    semester_entry = Semester.objects.get(pk=semester_pk)   
    time_strings = semester_entry.exam_start_times.split(",")
    daily_num_exams = len(time_strings)
    duration = semester_entry.exam_end_date - semester_entry.exam_start_date
    total_exams = (duration.days + 1) * daily_num_exams
    

    portfolio_id_value = get_portfolio_id()
    schedules = []
    no_group2slot = get_no_group2slot(semester_entry, no_last_day, no_last_2days, no_night, no_fri_mon) 
    optimizer = optimize.ExamOptimizer(semester_pk, group2slot, no_group2slot)
    course_info = optimizer.get_course_info()
    for name, penalty in penalties:
        schedule_entry = initialize_schedule(schedule_name + " " + name, semester_entry, course_info, penalty, group_constraints=group_constraints, predefined_constraints=predefined_constraints_dict)
        schedule.update_status(schedule_entry, Schedule.PHASE_0)
        phase1_group2slot = phase1(optimizer, schedule_entry, group2slot, total_exams, [20, 19, 18, 17], penalty, 300, True)
        if -1 in phase1_group2slot: #-1 indicates model was found to be infeasible
            schedule.update_status(schedule_entry, Schedule.INFEASIBLE)
            return HttpResponse(status=200)
        
        grasp_phase2_group2slot, warm_cost = phase2(optimizer, schedule_entry, penalty, total_exams, phase1_group2slot)

        # now try without grasp as a baseline
        schedule.update_status(schedule_entry, Schedule.PHASE_0)
        phase1_group2slot = phase1(optimizer, schedule_entry, group2slot, total_exams, [20, 19, 18, 17], penalty, 300, False)
        if -1 in phase1_group2slot:
            schedule.update_status(schedule_entry, Schedule.INFEASIBLE)
            return HttpResponse(status=200)
        
        reg_phase2_group2slot, reg_cost = phase2(optimizer, schedule_entry, penalty, total_exams, phase1_group2slot)

        phase2_group2slot = grasp_phase2_group2slot if warm_cost < reg_cost else reg_phase2_group2slot

        schedule_entry.portfolio_id = portfolio_id_value
        schedule.save(schedule_entry, phase2_group2slot)
        schedule.analyze(schedule_entry)
        
        schedules.append(schedule_entry)
    return HttpResponse(status=200)

def get_portfolio_id():
    portfolio_id = PortfolioID.objects.first()
    if portfolio_id is None:
        portfolio_id = PortfolioID.objects.create()
    return portfolio_id.get_new_id()