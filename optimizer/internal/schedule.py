"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Handles database calls for generated schedules.
"""

import copy

from ..internal import analyze as schedule_analyzer
from ..models import (
    CourseGroupSchedule,
    Schedule,
    ScheduleVersion,
)

# Create a new Schedule instance, only specifying 'name' and 'semester' fields at this point
def create(name, semester_entry, course_info, penalties = {}, group_constraints={}, predefined_constraints={}):
    """_summary_

    Args:
        name (_type_): _description_
        semester_entry (_type_): _description_
        course_info (_type_): _description_
        penalties (dict, optional): _description_. Defaults to {}.
        group_constraints (dict, optional): _description_. Defaults to {}.
        predefined_constraints (dict, optional): _description_. Defaults to {}.

    Returns:
        _type_: _description_
    """
    created = False
    i = 1
    name_candidate = copy.deepcopy(name)
    while not created:      
        schedule, created = Schedule.objects.get_or_create(semester=semester_entry, name=name_candidate, course_info=course_info, group_constraints=group_constraints, predefined_constraints=predefined_constraints, preference_profile=penalties)
        name_candidate = name + " (" + str(i) + ")"
        i += 1
    
    return schedule

def get_schedule_entry(name, semester_entry):
    return Schedule.objects.get(name=name, semester=semester_entry)

def save(schedule_entry, group2slot):
    '''
    Update each CourseGroupSchedule instance in the database with its corresponding 'slot_id"

    Parameters: 
        group2slot: a dictionary in which keys are course name, values are slot id
    '''
    for group in group2slot:        
        group_entry, created = CourseGroupSchedule.objects.get_or_create(
            name=str(group), 
            schedule=schedule_entry)
        #this is a very silly solution. the optimizer kicks out the first one, while saving a schedule from drag-drop does the second so hopefully this works
        try:
            group_entry.slot_id = int(group2slot[group])
        except:
            group_entry.slot_id = int(group2slot[group]["slot_id"])

        group_entry.save()  # save to the database

    schedule_entry.analyzed = False
    update_status(schedule_entry, Schedule.NOT_YET_ANALYZED)
    schedule_entry.save()

# Update the status of the schedule entry
def update_status(schedule_entry, status):
    schedule_entry.status = status
    schedule_entry.save()
    
# Deletes the schedule entry and all its CourseGroupSchedule entries
def delete(schedule_entry):
    CourseGroupSchedule.objects.filter(schedule=schedule_entry).delete()
    schedule_entry.delete()

# Rename the schedule entry to a new name
def rename(schedule_entry, name):
    schedule_entry.name = name
    schedule_entry.save()

'''
Map each CourseGroup (eg: MWF1600) to slot_id (eg: 4)
'''
def get_group2slot(schedule_entry):
    group2slot = dict()
    # retrieve all CourseGroupSchedule instances that belong to 'schedule_entry
    course_group_schedule_entries = CourseGroupSchedule.objects.filter(schedule=schedule_entry)
    
    for course_group_schedule in course_group_schedule_entries:
        course_group_name = course_group_schedule.name
        slot_id = course_group_schedule.slot_id
        group2slot[course_group_name] = slot_id

    return group2slot

def get_group2slot_special(schedule_entry):
    group2slot = dict()
    # retrieve all CourseGroupSchedule instances that belong to 'schedule_entry'
    course_group_schedule_entries = CourseGroupSchedule.objects.filter(schedule=schedule_entry)
    
    for course_group_schedule in course_group_schedule_entries:
        course_group_name = course_group_schedule.name
        is_special = False 
        slot_id = course_group_schedule.slot_id
        group2slot[course_group_name] = {'slot_id': slot_id, 'is_special': is_special}

    return group2slot


def duplicate(schedule_entry):
    name = "[DUPLICATED] " + schedule_entry.name
    created = False
    i = 1
    while not created:
        new_schedule_entry, created = Schedule.objects.get_or_create(semester=schedule_entry.semester, name=name, 
                                                           is_duplicated=True, original=schedule_entry)
        name = name + " (" + str(i) + ")"
        i += 1

    course_group_schedule_entries = CourseGroupSchedule.objects.filter(schedule=schedule_entry)
    for course_group_schedule in course_group_schedule_entries:
        new_course_group_schedule = CourseGroupSchedule.objects.create(name=course_group_schedule.name,
                                                                       schedule=new_schedule_entry,
                                                                       slot_id=course_group_schedule.slot_id,
                                                                       has_exam=course_group_schedule.has_exam)
    
    new_schedule_entry.students_overlap = schedule_entry.students_overlap
    new_schedule_entry.students_3in24 = schedule_entry.students_3in24
    new_schedule_entry.students_4in48 = schedule_entry.students_4in48
    new_schedule_entry.students_b2b = schedule_entry.students_b2b
    new_schedule_entry.students_night_morning = schedule_entry.students_night_morning
    new_schedule_entry.inconvenient_students = schedule_entry.inconvenient_students
    new_schedule_entry.faculty_overlap = schedule_entry.faculty_overlap
    new_schedule_entry.faculty_b2b = schedule_entry.faculty_b2b
    new_schedule_entry.analyzed = True

    new_schedule_entry.save()
    
        

def analyze(schedule_entry):
    """
    param schedule_entry: schedule object to be analized
    creates and runs a schedule_analyzer, saves the results to the schedule
    """
    OVERLAP = "student_overlap"
    FORCED_OVERLAP = "forced_overlap"
    THREE_IN_24 = "three_in_24"
    FOUR_IN_48 = "four_in_48"
    BACK_TO_BACK = "student_back_to_back"
    NIGHT_MORNING = "night_morning"
    F_OVERLAP = "faculty_overlap"
    F_B2B = "faculty_back_to_back"
    INCONVENIENT_STUDENT = "inconvenient_students"

    update_status(schedule_entry, Schedule.ANALYZING)
    analyzer = schedule_analyzer.Analyzer(schedule_entry)
    global_issues, problem_dict = analyzer.analyze_sol()

    schedule_entry.students_overlap = global_issues[OVERLAP]
    schedule_entry.student_forced_overlap = global_issues[FORCED_OVERLAP]
    schedule_entry.students_3in24 = global_issues[THREE_IN_24]
    schedule_entry.students_4in48 = global_issues[FOUR_IN_48]
    schedule_entry.students_b2b = global_issues[BACK_TO_BACK]
    schedule_entry.students_night_morning = global_issues[NIGHT_MORNING]
    schedule_entry.inconvenient_students = global_issues[INCONVENIENT_STUDENT]

    schedule_entry.faculty_overlap = global_issues[F_OVERLAP]
    schedule_entry.faculty_b2b = global_issues[F_B2B]

    schedule_entry.student_overlap_problems = problem_dict[OVERLAP]
    schedule_entry.student_3in24_problems = problem_dict[THREE_IN_24]
    schedule_entry.student_4in48_problems = problem_dict[FOUR_IN_48]
    schedule_entry.student_b2b_problems = problem_dict[BACK_TO_BACK]
    schedule_entry.student_night_morning_problems = problem_dict[NIGHT_MORNING]
    schedule_entry.inconvenient_students_list = problem_dict[INCONVENIENT_STUDENT]
    schedule_entry.faculty_overlap_problems = problem_dict[F_OVERLAP]
    schedule_entry.faculty_b2b_problems = problem_dict[F_B2B]


    schedule_entry.analyzed = True
    # schedule_entry.current_version = schedule_version

    schedule_entry.save()

    # Check if there are any existing ScheduleVersion instances
    if not ScheduleVersion.objects.filter(schedule=schedule_entry).exists():
        # create a new schedule version 
        schedule_version = ScheduleVersion.objects.create(
            schedule=schedule_entry,
            group2slot=get_group2slot_special(schedule_entry),
            students_overlap = global_issues[OVERLAP],
            students_3in24 = global_issues[THREE_IN_24],
            students_4in48 = global_issues[FOUR_IN_48],
            students_b2b = global_issues[BACK_TO_BACK],
            students_night_morning = global_issues[NIGHT_MORNING],
            inconvenient_students = global_issues[INCONVENIENT_STUDENT],
            faculty_overlap = global_issues[F_OVERLAP],
            faculty_b2b = global_issues[F_B2B],
        )
        schedule_version.save()

    update_status(schedule_entry, Schedule.ANALYZED)

def get_analysis_data(schedule_entry):
    """
    param schedule_entry: schedule object to get data for
    collects issue data into a dictionary and returns that for ease of use
    """
    OVERLAP = "student_overlap"
    FORCED_OVERLAP = "forced_overlap"
    THREE_IN_24 = "three_in_24"
    FOUR_IN_48 = "four_in_48"
    BACK_TO_BACK = "student_back_to_back"
    NIGHT_MORNING = "night_morning"
    INCONVENIENT_STUDENT = "inconvenient_students"
    F_OVERLAP = "faculty_overlap"
    F_B2B = "faculty_back_to_back"

    issue_data = dict()
    if schedule_entry.analyzed:
        issue_data[OVERLAP] = schedule_entry.students_overlap
        issue_data[FORCED_OVERLAP] = schedule_entry.student_forced_overlap
        issue_data[THREE_IN_24] = schedule_entry.students_3in24
        issue_data[FOUR_IN_48] = schedule_entry.students_4in48
        issue_data[BACK_TO_BACK] = schedule_entry.students_b2b
        issue_data[NIGHT_MORNING] = schedule_entry.students_night_morning
        issue_data[F_OVERLAP] = schedule_entry.faculty_overlap
        issue_data[F_B2B] = schedule_entry.faculty_b2b
        issue_data[INCONVENIENT_STUDENT] = schedule_entry.inconvenient_students
        
    else:
        issue_data[OVERLAP] = ""
        issue_data[FORCED_OVERLAP] = ""
        issue_data[THREE_IN_24] = ""
        issue_data[FOUR_IN_48] = ""
        issue_data[BACK_TO_BACK] = ""
        issue_data[NIGHT_MORNING] = ""
        issue_data[F_OVERLAP] = ""
        issue_data[F_B2B] = ""
        issue_data[INCONVENIENT_STUDENT] = ""

    return issue_data

def get_problem_data(schedule_entry):
    """
    param schedule_entry: schedule object to get data for
    collects problem data into a dictionary and returns that for ease of use
    """
    OVERLAP = "student_overlap"
    THREE_IN_24 = "three_in_24"
    FOUR_IN_48 = "four_in_48"
    BACK_TO_BACK = "student_back_to_back"
    NIGHT_MORNING = "night_morning"
    F_OVERLAP = "faculty_overlap"
    F_B2B = "faculty_back_to_back"
    INCONVENIENT_STUDENT = "inconvenient_students"

    issue_data = dict()
    if schedule_entry.analyzed:
        issue_data[OVERLAP] = schedule_entry.student_overlap_problems
        issue_data[THREE_IN_24] = schedule_entry.student_3in24_problems
        issue_data[FOUR_IN_48] = schedule_entry.student_4in48_problems
        issue_data[BACK_TO_BACK] = schedule_entry.student_b2b_problems
        issue_data[NIGHT_MORNING] = schedule_entry.student_night_morning_problems
        issue_data[F_OVERLAP] = schedule_entry.faculty_overlap_problems
        issue_data[F_B2B] = schedule_entry.faculty_b2b_problems
        issue_data[INCONVENIENT_STUDENT] = schedule_entry.inconvenient_students_list

    else:
        issue_data[OVERLAP] = ""
        issue_data[THREE_IN_24] = ""
        issue_data[FOUR_IN_48] = ""
        issue_data[BACK_TO_BACK] = ""
        issue_data[NIGHT_MORNING] = ""
        issue_data[F_OVERLAP] = ""
        issue_data[F_B2B] = ""
        issue_data[INCONVENIENT_STUDENT] = ""

    return issue_data




