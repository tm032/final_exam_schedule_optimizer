"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Creates a phase 1 and phase 2 SCIP MIP model from the supplied data.
"""
import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ExamScheduling.settings")
django.setup()

from django.conf import settings

import pyscipopt as scip
from pyscipopt import Model
import pandas as pd
import os 
from datetime import datetime, timedelta
import itertools
from pyscipopt import Eventhdlr, SCIP_EVENTTYPE
import time

import re

class ModelCreator:
    SURVEY_PREF = "survey"
    NIGHT_TO_MORNING_PREF = "fewer_night_morning"
    BACK_TO_BACK_PREF = "fewer_back_to_back"
    FACULTY_PREF = "faculty"
    def __init__(self, semester_entry):
        """
        param semester_entry: semester object to create models for
        grabs information out of the semester object that will be used to create the Integer Programming models
        actually creating the models happens from different function calls
        """
        self.semester_entry = semester_entry
        self.exam_times = [datetime.strptime(time_str.strip(), '%I:%M %p') for time_str in self.semester_entry.exam_start_times.split(",")]
        self.students_df = pd.read_csv(semester_entry.students_file.path)
        self.params = {}


    def get_students_df(self):
        return self.students_df

    def get_params(self):
        return self.params
    
    def get_course_info(self):
        return self.course_info
    
    def get_course_groupings(self):
        return self.course_groupings
    
    def remove_spaces_and_non_ascii_from_faculty_name(self,instructor):
        """ 
        Remove spaces and some non-ASCII characters from faculty name.
        """
        if pd.isna(instructor):
            return ""
        words = instructor.split()
        name = ""
        for word in words:
            word = word.replace("á", "a")
            name += word
        return name

    
    def retrieve_course_info(self):
        '''
        Takes the list of spreadsheet entries and organizes them nicely into a dictionary with the information we need for optimization.
        '''
        from ..models import Course
        course_entries = Course.objects.filter(semester=self.semester_entry)
        self.course_info = {}
        self.course_groupings = {}
        for course_entry in course_entries:
            crn = int(course_entry.crn)
            course_id = course_entry.course_identification
            section = course_entry.section
            instructor = course_entry.instructor
            title = course_entry.title
            has_exam = course_entry.course_group != self.get_no_exam_entry()
            course_group = course_entry.course_group.name
            meeting_times = course_entry.meeting_times
            is_clear = course_entry.clear
            
            self.course_info[crn] = {'course_id' : course_id, 'section' : section, 'instructor': self.remove_spaces_and_non_ascii_from_faculty_name(instructor), 
                      'title': title, 'has_exam': has_exam, 'course_group': course_group, 'meeting_times': meeting_times, 'is_clear': is_clear}
            
            if course_group in self.course_groupings:
                self.course_groupings[course_group] += [crn]
            else:
                self.course_groupings[course_group] = [crn]

    def load_course_info(self, course_info):
        """
        Load course information from the provided dictionary.
        """
        self.course_info = course_info
        self.course_groupings = {}
        for crn in course_info.keys():
            course_group = course_info[crn]["course_group"]
            if course_group in self.course_groupings:
                self.course_groupings[course_group] += [crn]
            else:
                self.course_groupings[course_group] = [crn]

    def retrieve_params(self):
        """
        Compute parameters required for Optimization.
        """
        self.compute_sets()
        self.compute_d_n()
        self.compute_h_nx()
        self.compute_enrollment()
    
    def compute_sets(self):
        """
        Computes basic sets used in the optimization.
        S = list of a student id's
        G = list of all course_groups that have exams
        C = list of all crns that have exams
        T = list of all timeslots, including invalid ones like during weekends
        F = list of all faculty members who are giving exams
        """

        # List of student IDs (anonymized)
        self.params["S"] = self.students_df["Randomized ID"].tolist()  # List of student ID's

        # Course groups (e.g. MWF1100, CHEM211, etc.)
        self.params["G"] = list(g for g in self.course_groupings.keys() if g != "NO_EXAM")
        
        # A list of all CRNs (that have exams)
        self.params["C"] = list(self.course_info.keys())
        
        # duration of the exam period in days.
        duration = self.semester_entry.exam_end_date - self.semester_entry.exam_start_date

        # List of timeslot IDs. This includes invalid timeslots like weekends.
        self.params["T"] = [x for x in range(0, (duration.days + 1) * len(self.exam_times))]

        # List of faculty members.
        self.params["F"] = []
        for crn in self.course_info:
            instructor = self.course_info[crn]["instructor"]
            instructor = self.remove_spaces_and_non_ascii_from_faculty_name(instructor)
            if instructor not in self.params["F"]:
                self.params["F"].append(instructor)

    def compute_d_n(self):
        """
        computes d and n sets used during optimization
        d = dict of the form {timeslot: 1 or 0} with 1 representing the timeslot is valid for scheduling and 0 meaning it is not valid (ex during weekend)
        n = dict of the form (timeslot: 1 or 0) with 1 representing the timeslot is a night exam, 0 meaning it is not a night exam. 
        A night exam is defined to be the last exam of the day, regardless of when that exam actually is
        """
        ## Time slot availablity data: d[t]=1 if time slot t is available for scheduling, 0 otherwise
        # Looks at the start date and end date to automatically construct d. Excludes weekends, Friday night, and night of the last day.

        self.params["d"] = {}
        time_strings = self.semester_entry.exam_start_times.split(",")
        daily_num_exams = len(time_strings)
        duration = self.semester_entry.exam_end_date - self.semester_entry.exam_start_date
        total_exams = (duration.days + 1) * daily_num_exams
        date = self.semester_entry.exam_start_date
        slot_index = 0
        while date <= self.semester_entry.exam_end_date:
            for i in range(slot_index, slot_index + daily_num_exams):
                if date.weekday() == 4 or date == self.semester_entry.exam_end_date: # if friday or last day of exams, don't allow night exams
                    if i % daily_num_exams != daily_num_exams - 1: 
                        self.params["d"][i] = 1
                    else:
                        self.params["d"][i] = 0
                else:
                    if date.weekday() < 4:
                        self.params["d"][i] = 1
                    else:
                        self.params["d"][i] = 0
        
            date = date + timedelta(days=1) 
            slot_index += daily_num_exams

        self.params["d"][total_exams] = 0
        ## Night slot data: n[t]=1 if time slot t is a night exam, 0 otherwise

        self.params["n"] = {}
  
        for x in self.params["T"]:
            if x % len(self.exam_times) == len(self.exam_times) - 1:
                self.params["n"][x] = 1
            else:
                self.params["n"][x] = 0

    def compute_h_nx(self):
        """
        more sets for optimization relating to enrollment. removes students who have 0 exams from set S
        e = dict of the form {student, course: 1 or 0}. 1 if student is in course, 0 otherwise
        r = dict of the form {course, group: 1 or 0}. 1 if course is in group, 0 otherwise
        h = dict of the form {student, group1 or 0}. 1 if student in group, 0 otherwise
        """
        ## Student enrollment data: e[s,c]=1 if student s is enrolled in course c, 0 otherwise
        e = {}
        num_exams = {}
        student_without_exams = []

        self.students_df = self.students_df[["Randomized ID", 
                                            "CRN 1", "CRN 2", "CRN 3", "CRN 4",
                                            "CRN 5", "CRN 6", "CRN 7", "CRN 8",
                                            "CRN 9", "CRN 10", "CRN 11", "CRN 12",
                                            "CRN 13", "CRN 14", "CRN 15"]]

        for s in self.params["S"]:
            num_exams[s] = 0
            student_courses = self.students_df.loc[self.students_df["Randomized ID"] == s].values[0].tolist()
            for c in self.params["C"]:
                if not self.course_info[c]["has_exam"]:
                    continue
                                
                if int(c) in student_courses:
                    e[s,c] = 1
                    num_exams[s] += 1
                else:
                    e[s,c] = 0                 

            if num_exams[s] == 0:
                if s in student_without_exams:
                    print(s)
                else:
                    student_without_exams.append(s)

        print("Removing", len(student_without_exams), "students that have no exams.")

        # Removes the student without having any exams from set S
        for student in student_without_exams:
            self.params["S"].remove(student)
            num_exams.pop(student)
        
        ## Course group data: r[c,g]=1 if course c is in course group g, 0 otherwise
        r = {}
        for c in self.params["C"]:
            if not self.course_info[c]["has_exam"]:
                continue
            for g in self.params["G"]:
                if self.course_info[c]["course_group"] == g:
                    r[c,g] = 1
                else:
                    r[c,g] = 0
                    
        ## Student in coursegroup data
        self.params["h"] = {}
        i = 0
        hit = 0
        for s in self.params["S"]:
            for c in self.params["C"]:
                if not self.course_info[c]["has_exam"]:
                    continue
                for g in self.params["G"]:
                    if e[s,c] == 1 and r[c,g] == 1: # if student s is in course c, and course c is in group g
                        if (s,g) in self.params["h"].keys() and self.params["h"][s,g] == 1: # if student s is in group g
                            # if the student is in a course, that course is in a group, and that student is already known to be inside that group, then this student has two exams in the same group
                            # this is a forced overlap
                            hit += 1
                        self.params["h"][s,g] = 1
                        
                    elif (s,g) not in self.params["h"].keys():
                        self.params["h"][s,g] = 0
            i += 1
        print("total forced overlaps:", hit)
        self.params["num_exams"] = num_exams
        self.params["forced_overlap"] = hit

    def compute_enrollment(self):
        """
        Computes the student's enrollment in each course group.
        Computes the number of students and faculties who has exams in a pair of groups.
        N_s = dict with 2 methods to use it. N_s[group] = number of students in that group. N_s[group, group] = number of students in both groups
        N_f = dict N_f[faculty, group] = 1 if faculty teaches something in group, 0 otherwise
        """
        N_s = dict()
        group_enrollement = dict()
        N_f = dict()

        for g1 in self.params["G"]:
            N_s[g1] = 0

            for g2 in self.params["G"]:
                if g1 == g2:
                    continue
                else:
                    N_s[g1, g2] = 0
                    N_f[g1, g2] = 0

        for i in range(len(self.students_df)):
            groups = []
            for j in range(16):
                crn = int(self.students_df.iloc[i]["CRN " + str(j + 1)])

                if crn == -1:
                    break

                if crn not in self.course_info:
                    continue

                course_group = self.course_info[crn]['course_group']

                if course_group == "NO_EXAM" or pd.isna(course_group) or course_group == "":
                    continue

                N_s[course_group] += 1
                if course_group in group_enrollement.keys():
                    group_enrollement[course_group].add(self.students_df.iloc[i]["Randomized ID"])
                else:
                    group_enrollement[course_group] = {self.students_df.iloc[i]["Randomized ID"]}
                groups.append(course_group)

            permutations = itertools.permutations(groups, 2)
            for pair in permutations:
                if pair[0] != pair[1]:
                    N_s[pair] += 1

        print("Computed students enrollment")
                
        # Faculty data: u[f,g] = 1 if faculty f teaches a course in group g, 0 otherwise
        u = dict()
        f_num_exams = dict()
        for f in self.params["F"]:
            f_num_exams[f] = 0
            for g in self.params["G"]:
                for crn in self.course_groupings[g]:
                    if self.course_info[crn]['instructor'] == f:
                        u[f,g] = 1
                        f_num_exams[f] += 1
                if (f,g) not in u:
                    u[f,g] = 0
            
        for f in self.params['F']:
            for g1 in self.params['G']:
                for g2 in self.params['G']:
                    if g1 == g2:
                        continue
                    if u[f,g1] == 1 and u[f,g2] == 1:
                        N_f[g1, g2] += 1

        v = {}
        for f in self.params["F"]:
            for g1 in self.params["G"]:
                for g2 in self.params["G"]:
                    if u[f,g1] == 1 and u[f,g2] == 1:
                        v[f,g1,g2] = 1
                    else:
                        v[f,g1,g2] = 0

        print("Computed faculty registration")
        self.params['u'] = u
        self.params['f_num_exams'] = f_num_exams
        self.params['v'] = v
        self.params['N_s'] = N_s
        self.params['N_f'] = N_f        
        self.params["group_enrollment"] = group_enrollement 
        
    def matrix_information_retrival(self):
        """
        Computes the number of students in each course group and the number of students in pairs of course groups.
        """
        self.retrieve_course_info()
        self.params["G"] = list(g for g in self.course_groupings.keys() if g != "NO_EXAM")
        N_s = dict()

        for g1 in self.params["G"]:
            N_s[g1] = 0

            for g2 in self.params["G"]:
                if g1 == g2:
                    continue
                else:
                    N_s[g1, g2] = 0

        for i in range(len(self.students_df)):
            groups = []
            for j in range(16):
                crn = int(self.students_df.iloc[i]["CRN " + str(j + 1)])

                if crn == -1:
                    break

                if crn not in self.course_info:
                    continue

                course_group = self.course_info[crn]['course_group']

                if course_group == "NO_EXAM" or pd.isna(course_group) or course_group == "":
                    continue

                N_s[course_group] += 1
                groups.append(course_group)

            permutations = itertools.permutations(groups, 2)
            for pair in permutations:
                if pair[0] != pair[1]:
                    N_s[pair] += 1
        return N_s

    def get_no_exam_entry(self):
        from ..models import CourseGroup
        return CourseGroup.objects.filter(semester=self.semester_entry, name="NO_EXAM")[0]

    """These methods are where you actually get the models needed for optimization"""
    def create_phase1_SCIP_model(self, initial_constraints, no_group2slot, num_phase1_courses, time_minimum, penalties):
        """
        param initial_constrants: dictionary with course and time that must be respected
        param no_group2slot: dictionary with course and list of timeslots that course cannot be scheduled at certain times.
        param num_phase1_courses: number of courses to be placed in phase1
        param time_minimum: min time that phase1 should run for after a new solution is found.
        param penalties: dictionary with key being issue and value is penalty for incurring that issue.
        """
        phase1 = Phase1ModelCreator(self.params, initial_constraints, no_group2slot, self.semester_entry, num_phase1_courses, penalties)
        return phase1.create_SCIP_model(time_minimum)

    def create_phase2_SCIP_model(self, penalties, num_courses, output_dir):
        """
        param penalties: dict with key being issue and value is penalty for incurring that issue.
        param num_courses: number of courses to be fixed in phase 1.
        param output_dir: directory to save the output files to.
        """
        phase2  = Phase2ModelCreator(self.params, penalties, num_courses, output_dir)
        self.phase2SCIP_model = phase2.create_SCIP_model()
        return self.phase2SCIP_model


"""
Creates Phase 1 model
"""
class Phase1ModelCreator:
    def __init__(self, params, initial_group2slot, no_group2slot, semester_entry, num_courses, penalties):
        """
        param params: sets created by model creator to be used during model creation
        param initial_group2slot: dict of the form {course:timeslot}, indicating course must be placed at timeslot
        param no_group2slot: dict of the form {course:[t1, t2, t3...]}, indicating course cannot be placed at timeslots in the list
        param semester_entry: semester object this model is being created for
        param num_courses: number of large courses to place during optimization
        param penalties: dictionary with key being issue and value is penalty for incurring that issue
        """
        self.data = params
        self.semester_entry = semester_entry
        self.bad_things, self.penalties = scip.multidict(penalties)

        self.initial_group2slot = initial_group2slot
        self.no_group2slot = no_group2slot

        self.choose_large_classes(num_courses)
        self.create_issues()

    def choose_large_classes(self, num_classes):
        """
        Chooses num_classes most popular exam groups to include in phase 1 optimization.
        """
        G = self.data["G"]
        N_s = self.data["N_s"]

        G.sort(key=lambda group:-1 * N_s[group])

        new_G = [course for course in self.initial_group2slot.keys()]
        print("self.no_group2slot:", self.no_group2slot)
        for course in self.no_group2slot:
            if course not in new_G:
                new_G.append(course)

        # Add num_classes most popular courses (excluding ones in the initial constraints) and courses specified in the initial constraints.
        i = 0
        counter = len(new_G)
        print("number of phase 1 courses to place:", num_classes)
        while counter < num_classes and i < len(G):
            if G[i] not in new_G:
                new_G.append(G[i])
                counter += 1
            i += 1

        G_choose_2 = itertools.combinations(new_G, 2)
        G_choose_2_list = []

        for pair in G_choose_2:
            G_choose_2_list.append(pair)

        self.data["G_choose_2"] = G_choose_2_list
        self.data["new_G"] = new_G


    def create_issues(self):
        """
        Computes possible decision variables including the issue counter.
        Computes the pair of courses that has no overlap in students. (They can be ignored in the optimization)
        """
        G = self.data["new_G"] 
        T = self.data["T"] 
        d = self.data["d"]
        G_choose_2 = self.data["G_choose_2"]
        N_f = self.data["N_f"] 
        N_s = self.data["N_s"]

        self.decisions = [(g,t) for g in G for t in T  if d[t] == 1]

        self.problem_combos = []

        # Removes a pair of courses that has no overlaps in students and faculties
        self.irrelevant_pairs = [] 
        for key in N_f.keys():
            if N_f[key] == 0 and N_s[key] == 0:
                self.irrelevant_pairs.append(key)

        for pair in G_choose_2:
            if pair in self.irrelevant_pairs:
                continue

            g1 = pair[0]
            g2 = pair[1]
            self.problem_combos += [(g1, g2, "overlap"), (g1, g2, "B2B"), (g1, g2, "PMtoAM")] 
    
    def create_SCIP_model(self, time_minumum):
        """
        Creates the phase 1 model
        """

        G = self.data["new_G"] 
        T = self.data["T"] 
        d = self.data["d"] 
        n = self.data["n"] 
        N_f = self.data["N_f"] 
        N_s = self.data["N_s"] 
        G_choose_2 = self.data["G_choose_2"]


        # Create the model
        
        mod = Model("phase1")

        ## Decision Variables
        sch = {}
        for i in range(len(self.decisions)):
            name = str(self.decisions[i]).replace("'", "").replace("(", "[").replace(")", "]").replace(" ", "")
            sch[self.decisions[i]] = mod.addVar(name="x_gt" + name, vtype="B")

        
        bad = {}
        for i in range(len(self.problem_combos)):
            bad[self.problem_combos[i]] = mod.addVar(vtype="C", name = "badness" + str(self.problem_combos[i]))


        ## Objective Function
        # We want to minimize the total penalty, summed over all students, i.e. total badness
        
        mod.setObjective(sum(self.penalties["overlap"] * N_s[pair] * bad[pair[0], pair[1], "overlap"] 
                               + self.penalties["B2B"] * N_s[pair] * bad[pair[0], pair[1],"B2B"]
                               + self.penalties["PMtoAM"] * N_s[pair] * bad[pair[0], pair[1],"PMtoAM"] for pair in G_choose_2 if pair not in self.irrelevant_pairs), "minimize") 

        #set the constraints to respect the hard constraints
        for group in self.initial_group2slot:
            timeslot = self.initial_group2slot[group]
            mod.addCons((sch[group, int(timeslot)] == 1), group + "_constraint")

        #set constraints to respect the "dont put this there" constraints
        for group in self.no_group2slot:
            timeslots = self.no_group2slot[group]
            for timeslot in timeslots:
                if d[timeslot] == 1:
                    mod.addCons((sch[group, int(timeslot)] == 0), group + "_no_constraint")

        ## Constraints
        # Every course group must be assigned to exactly one time slot
        for g in G:
            mod.addCons(sum(sch[g,t] for t in T if d[t] == 1) == 1, name = "timeslot_Constraint_" + str(g))  

        # Overlapping exam constraint
        for pair in G_choose_2:
            if pair in self.irrelevant_pairs:
                continue

            g1 = pair[0]
            g2 = pair[1]
            for t in T:
                if d[t] == 1 and g1 != g2:
                    mod.addCons(sch[g1,t] + sch[g2,t] <= 1 + bad[g1, g2, "overlap"], name="overlap_"+str(g1)+","+str(g2)+","+str(t))
                

        # Back to back
        for pair in G_choose_2:
            if pair in self.irrelevant_pairs:
                continue

            g1 = pair[0]
            g2 = pair[1]
            for t in T:
                if d[t] == 1 and g1 != g2 and d[t + 1] == 1 and n[t] == 0:
                    mod.addCons(sch[g1,t] + sch[g2,t+1] <= 1 + bad[g1, g2, "B2B"], name="B2B_"+str(g1)+","+str(g2)+","+str(t))
                    mod.addCons(sch[g2,t] + sch[g1,t+1] <= 1 + bad[g1, g2, "B2B"], name="B2B_"+str(g2)+","+str(g1)+","+str(t))
                

        # night to morning
        for pair in G_choose_2:
            if pair in self.irrelevant_pairs:
                continue

            g1 = pair[0]
            g2 = pair[1]
            for t in T:
                if d[t] == 1 and g1 != g2 and d[t + 1] == 1 and n[t] == 1:
                    mod.addCons(sch[g1,t] + sch[g2,t+1] <= 1 + bad[g1, g2, "PMtoAM"], name="PMtoAM_"+str(g1)+","+str(g2)+","+str(t))
                    mod.addCons(sch[g2,t] + sch[g1,t+1] <= 1 + bad[g1, g2, "PMtoAM"], name="PMtoAM_"+str(g2)+","+str(g1)+","+str(t))

        # put a constraints such that a single timeslot cannot have too many students      
        max_size = settings.MAX_STUDENTS_PER_SLOT
        for g in G:
            max_size = N_s[g] if N_s[g] > max_size else max_size
        for t in T:
            if d[t] == 1:
                mod.addCons(sum(N_s[g]*sch[g,t] for g in G) <= max_size, name="MaxNumOfStudents_" + str(t))

        eventhdlr = Phase1SCIPCallback(mod, minimum_time = time_minumum, solution_reward=30)
        mod.includeEventhdlr(eventhdlr, "BESTSOLFOUND", "python event handler to catch BESTSOLFOUND")

        return mod

class Phase1SCIPCallback(Eventhdlr):
    """
    This is a custom event that is added to the phase1 scip model. When a better solution is found, 
        it adjust the timelimit to give the optimizer a little more time. (settings.PHASE_1_TIME_LIMIT)
        eventexec is run every time a better solution is found
    """
    def __init__(self, mod, minimum_time = 60, solution_reward=5):
        self.solution_bonus = solution_reward
        self.start_time = time.time()
        self.min_time = minimum_time
        self.model = mod

    def eventinit(self):
        self.model.catchEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)
        pass

    def eventexit(self):
        self.model.dropEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)

    def eventexec(self, event):
        current_time = time.time()
        execution_time = current_time - self.start_time
        limit = (execution_time + self.solution_bonus) if (execution_time + self.solution_bonus) > self.min_time else self.min_time
        print("optimal solution value:", str(self.model.getPrimalbound()), "new time limit:", limit)
        self.model.setRealParam("limits/time", limit)


"""
Creates phase 2 model
"""
class Phase2ModelCreator:
    def __init__(self, params, penalties, num_courses, output_dir):
        """
        param params: sets computed in Model Creator to use for model creation
        param penalties: dictionary with key being issue and value is penalty for incurring that issue
        """
        self.data = params
        self.bad_things, self.penalties = scip.multidict(penalties)
        self.num_courses = num_courses
        self.output_dir = output_dir
    
    def create_SCIP_model(self):
        decisions, m, o, stud_problem_combos, faculty_problem_combos = self.create_issues()
        scip = self._create_SCIP_model(decisions, m, o, stud_problem_combos, faculty_problem_combos)
        return scip

    def create_issues(self):
        """
        Computes possible decision variables including the issue counter.
        """
        S = self.data["S"] 
        G = self.data["G"] 
        T = self.data["T"] 
        d = self.data["d"]
        F = self.data["F"] 

        decisions = [(g,t) for g in G for t in T  if d[t] == 1]

        m = [(s,t) for s in S for t in T if d[t] == 1]

        o = [(f,t) for f in F for t in T if d[t] == 1]

        stud_problem_combos = []
        for s in S:
            stud_problem_combos += [(s, "threein24"), (s,"fourin48")]
        for s in S:
            for t in T:
                if d[t] == 1:
                    stud_problem_combos += [(s, t, "overlap"), (s, t, "B2B"), (s, t, "PMtoAM")]
            
        faculty_problem_combos = []
        for f in F:
            faculty_problem_combos += [(f, 'facultyoverlap'), (f, 'facultyB2B')]

        return decisions, m, o, stud_problem_combos, faculty_problem_combos

    def _create_SCIP_model(self, decisions, m, o, stud_problem_combos, faculty_problem_combos):
        S = self.data["S"] 
        G = self.data["G"] 
        T = self.data["T"] 
        F = self.data["F"] 
        h = self.data["h"] 
        d = self.data["d"] 
        u = self.data["u"] 
        v = self.data["v"] 
        n = self.data["n"] 
        N_s = self.data["N_s"] 
        num_exams = self.data["num_exams"]
        f_num_exams = self.data["f_num_exams"]

        # Create the model
        
        mod = Model("phase2")

        print("Begin building the model.")
        print("G:", G)

        ## Decision Variables

            # When a decision variable is indexed by a set of items, we can use the addVars method to add all of the variables at once.
       
        sch = {}
        for i in range(len(decisions)):
            name = str(decisions[i]).replace("'", "").replace("(", "[").replace(")", "]").replace(" ", "")
            sch[decisions[i]] = mod.addVar(name="x_gt" + name, vtype="B")

        
        student = {}
        for i in range(len(m)):
            student[m[i]] = mod.addVar(vtype="B", ub=1, name="m_st" + str(m[i]))

        
        faculty = {}
        for i in range(len(o)):
            faculty[o[i]] = mod.addVar(vtype = "B", ub=1, name="o_ft" + str(o[i]))

        
        bad = {}
        for i in range(len(stud_problem_combos)):
            bad[stud_problem_combos[i]] = mod.addVar(vtype="B", name = "badness" + str(stud_problem_combos[i]))

        
        faculty_bad = {}
        for i in range(len(faculty_problem_combos)):
            faculty_bad[faculty_problem_combos[i]] = mod.addVar(vtype="B", name="factuly_badness" + str(faculty_problem_combos[i]))

        ## Objective Function

        # We want to minimize the total penalty, summed over all students, i.e. total badness
        mod.setObjective(sum(sum(self.penalties[thing]*bad[(s, thing)] for thing in self.bad_things if (s,thing) in bad) \
                   + sum(self.penalties[thing]*bad[(s, t, thing)] for t in T for thing in self.bad_things if (s, t, thing) in bad and d[t] == 1) for s in S) \
                   + sum(self.penalties[thing]*faculty_bad[f, thing] for thing in self.bad_things for f in F if (f, thing) in faculty_bad),
                   "minimize")
        print("Objective function set")

        ## Constraints
        # Every course group must be assigned to exactly one time slot
        for g in G:
            mod.addCons(sum(sch[g,t] for t in T if d[t] == 1) == 1, name = "timeslot_Constraint_" + str(g))

        print("Course group assignment constraint set")
            
        # Overlapping exam constraint
        num_student = 0
        for s in S:
            for t in T:
                if d[t] == 1:
                    mod.addCons(sum(h[s,g]*sch[g,t] for g in G) <= (1 + bad[s, t, "overlap"]), name="overlap_"+str(s)+","+str(t))
            num_student += 1
        
        # m[s,t] constraint
        for s in S:
            for t in T:
                # For binary m_st variable
                if d[t] == 1:
                    mod.addCons(sum(h[s,g]*sch[g,t] for g in G) <=  num_exams[s] * student[s,t], name="mst_constraint_"+str(s)+","+str(t))


        print("m[s,t] set")

        # 3 exams in 24 hours
        for s in S:
            if num_exams[s] < 3: # Not setting constraint if the student takes less than 3 exams
                continue

            for start in T[0:len(T)-3]:
                if d[start] == 1 and d[start + 3] == 1: 
                    mod.addCons(sum(student[s,t] for t in range(start, start+4)) <= 2 + (num_exams[s] - 2) * bad[s,"threein24"], name="threein24_constraint_"+str(s)+","+str(start))

        print("3 in 24 set")

        # 4 exams in 48 hours
        for s in S:
            if num_exams[s] < 4: # Not setting constraint if the student takes less than 4 exams
                continue
            for start in T[0:len(T)-7]:
                if start + 7 in d and d[start] == 1 and d[start + 7] == 1:
                    mod.addCons(sum(student[s,t] for t in range(start, start+8)) <= 3 + (num_exams[s] - 3) * bad[s,"fourin48"], name="fourin48_constraint_"+str(s)+","+str(start))
                elif start + 6 in d and d[start] == 1 and d[start + 6] == 1:
                    mod.addCons(sum(student[s,t] for t in range(start, start+7)) <= 3 + (num_exams[s] - 3) * bad[s,"fourin48"], name="fourin48_constraint_"+str(s)+","+str(start))
                

        print("4 in 48 set")


        # Back to back & night to morning
        for s in S:
            if num_exams[s] < 2: # Not setting constraint if the student takes less than 2 exams
                continue
            for start in T[0:len(T)-1]:
                if d[start] == 1 and d[start + 1] == 1:
                    mod.addCons(sum(student[s,t] for t in range(start, start+2)) <= (1 + n[start]*bad[s, start, "PMtoAM"] + (1-n[start])*bad[s, start, "B2B"]), name="backtoback_constraint_"+str(s)+","+str(start))

        print("Back to back set")

        max_size = settings.MAX_STUDENTS_PER_SLOT
        for g in G:
            max_size = N_s[g] if N_s[g] > max_size else max_size
        for t in T:
            if d[t] == 1:
                mod.addCons(sum(N_s[g]*sch[g,t] for g in G) <= max_size, name="MaxNumOfStudents_" + str(t))
        print("Max Num of students per slot =", max_size)


        # Faculty overlap constraint
        for f in F:
            if f == "TBD":
                pass

            for g1 in G:
                for g2 in G:
                    if v[f,g1,g2] == 1:
                        mod.addCons((sum(sch[g1,t] + sch[g2,t] for t in T if d[t] == 1) <=  1 + faculty_bad[f, "facultyoverlap"]), name="faculty_overlap_"+f+"_"+g1+"_"+g2)
        print("Faculty overlaps set")

        # o[f,t] constraint
        for f in F:
            if f == "TBD":
                pass
            
            for t in T:
                if d[t] == 1:
                    mod.addCons(sum(u[f,g] * sch[g,t] for g in G) <=  f_num_exams[f] * faculty[f,t], name="oft_constraint_"+str(f)+","+str(t))

            
            
        print("o[f,t] set")

        # Faculty back to back constraint -- INCLUDES NIGHT TO MORNING
        for f in F:
            if f == "TBD":
                pass

            for start in range(0, len(T)-1):
                if d[start] == 1 and d[start + 1] == 1:
                    mod.addCons(sum(faculty[f,t] for t in range(start, start+2)) <= 1 + faculty_bad[f, "facultyB2B"], name="faculty_B2B_"+f+"_"+str(start))

        print("Faculty back to backs set")
        print("Finish building the model")

        eventhdlr = Phase2SCIPCallback(mod, num_courses=self.num_courses, output_dir=self.output_dir)
        mod.includeEventhdlr(eventhdlr, "BESTSOLFOUND", "python event handler to catch BESTSOLFOUND")

        return mod

class Phase2SCIPCallback(Eventhdlr):
    """
    This is a custom event that is added to the phase 2 scip model. 
    When a new incumbent solution is found, it saves the solution and analysis to files.
    Later, the main thread can read these files to get the best solution and analysis.
    """
    def __init__(self, mod, num_courses, output_dir):
        self.start_time = time.time()
        self.model = mod
        self.name = "Fixed" + str(num_courses)
        self.solnfile = os.path.join(output_dir, self.name + "_best_solution.json")
        self.analysisfile = os.path.join(output_dir, self.name + "_analysis.json")

    def eventinit(self):
        self.model.catchEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)

    def eventexit(self):
        self.model.dropEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)

    def eventexec(self, event):
        current_time = time.time()
        execution_time = current_time - self.start_time

        with open(self.solnfile, "w") as f:
            group2slot = self.get_SCIP_group2slot()
            json.dump(group2slot, f)

        with open(self.analysisfile, "w") as f:
            inconveniences = self.get_SCIP_inconviences()
            inconveniences["ObjVal"] = self.model.getObjVal()
            json.dump(inconveniences, f)

    def get_SCIP_group2slot(self):
        model = self.model

        group2slot = dict()
        for v in model.getVars():
            try:
                solution = model.getBestSol()
                if "x_gt" in v.name and abs(model.getSolVal(solution, v) - 1) < settings.EPSILON:
                        result = re.search(r"x_gt\[(.+),([\d]+)\]", v.name)
                        group2slot[result.group(1)] = int(result.group(2))
            except UnicodeDecodeError:
                print("hecked up on variable", v.name)
                pass

        return group2slot
    
    def get_SCIP_inconviences(self):
        model = self.model
        inconvinience_types = ["overlap", "B2B", "PMtoAM", "threein24", "fourin48", "facultyoverlap", "facultyB2B"]
        inconviences = {key: 0 for key in inconvinience_types}

        solution = model.getBestSol()

        for v in model.getVars():
            inconvience_value = model.getSolVal(solution, v)

            if "facultyoverlap" in v.name:
                inconviences["facultyoverlap"] += inconvience_value
            elif "facultyB2B" in v.name:
                inconviences["facultyB2B"] += inconvience_value
            elif "overlap" in v.name:
                inconviences["overlap"] += inconvience_value
            elif "threein24" in v.name:
                inconviences["threein24"] += inconvience_value
            elif "fourin48" in v.name:
                inconviences["fourin48"] += inconvience_value
            elif "B2B" in v.name:
                inconviences["B2B"] += inconvience_value
            elif "PMtoAM" in v.name:
                inconviences["PMtoAM"] += inconvience_value


        return inconviences