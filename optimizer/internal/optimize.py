"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Optimizes the exam scheduling model.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ExamScheduling.settings")
django.setup()

import os 
import re
import multiprocessing
import django
import json

from .mutliprocess_workers import SCIP_phase1_worker, SCIP_phase2_worker, multi_process_grasp_solver

from django.conf import settings


"""
Optimizes a given phase. Note that this class will be initialized before each phase.
"""
class ExamOptimizer:
    SURVEY_PREF = "survey"
    NIGHT_TO_MORNING_PREF = "fewer_night_morning"
    BACK_TO_BACK_PREF = "fewer_back_to_back"
    FACULTY_PREF = "faculty"

    def __init__(self, semester_pk, group2slot, no_group2slot):
        """
        param semester_pk: the django database id for what semester this schedule is optimizing
        param group2slot: dict of the form {course_group: timeslot} to indicate hard constraints on where certain groups are placed
        param no_group2slot: dict of the form {course_group: [t1, t2]} to indicate where courses are NOT allowed to be placed
        """
        from ..models import Semester
        from ..internal import create_model

        try:
            self.semester_entry = Semester.objects.get(pk=semester_pk)
        except:
            raise ValueError
        
        self.group2slot = group2slot
        self.no_groupslot = no_group2slot
        
        self.model_creator = create_model.ModelCreator(self.semester_entry)
        self.model_creator.retrieve_course_info()
        self.model_creator.retrieve_params()
        
    def get_course_info(self):
        return self.model_creator.course_info
    
    def print_schedule(self, sol_schedule):
        for i in range(len(sol_schedule)):
            print("Slot " +  str(i) + ": ", end="")
            for j in range(len(sol_schedule[i])):
                print(sol_schedule[i][j], end=" ")
            print()

    def SCIP_optimize_phase1(self, num_exam_slots, num_phase1_courses, penalties, seconds_limit, warm_start_grasp):
        """
        param num_exam_slots: number of possible exam slots this semester has
        param num_phase1_courses: number of courses that phase1 places into the schedule
        param preference_profile: dict of the form {string of problem: float penalty associated with the problem}
        param seconds limit: determines how long phase1 is supposed to run
        """
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ExamScheduling.settings')
        django.setup()
        jobs = []
        manager = multiprocessing.Manager()
        phase1_results = manager.dict()
        for i in range(len(num_phase1_courses)):
                print("creating process for ", num_phase1_courses[i], " courses")
                p = multiprocessing.Process(target=SCIP_phase1_worker, args=(self, num_phase1_courses[i], num_exam_slots, {}, seconds_limit, phase1_results, penalties, warm_start_grasp))
                jobs.append(p)
                p.start()
        for job in jobs:
            job.join()
        return phase1_results
    
    def SCIP_optimize_phase2(self, preference_profile, group2slot_dict, num_exam_slots, results_dir):
        """
        Optimizes the phase 2 with a given Optimization type preference profile.
        param preference_profile: dict of the form {string of problem: float penalty associated with the problem}
        pram group2slot_dict: dict of the form {phase1 cost: phase1 output}, used to create constraints on phase2 model with what was produced in phase1
        param num_exam_slots: number of exam slots this semester has
        """
        manager = multiprocessing.Manager()
        results = manager.dict()
        jobs = []
        num_course_list = []

        for key in group2slot_dict:
                print("phase 2 optimization for process id:", key)
                num_courses = key[1]
                num_course_list.append(num_courses)
                p = multiprocessing.Process(target=SCIP_phase2_worker, args=(self, preference_profile, group2slot_dict[key], num_exam_slots, results, num_courses, results_dir))
                jobs.append(p)
                p.start()
        
        for job in jobs:
            job.join()
        
        solutions = {}
        inconveniences = {}

        minimum_ObjVal = 100000000000000000
        chosen_num_course = -1

        for num_course in num_course_list:
            with open(os.path.join(results_dir, f"Fixed{num_course}_best_solution.json"), "r") as f:
                solutions[num_course] = json.load(f)
            
            with open(os.path.join(results_dir, f"Fixed{num_course}_analysis.json"), "r") as f:
                inconveniences[num_course] = json.load(f)

            if inconveniences[num_course]["ObjVal"] < minimum_ObjVal:
                minimum_ObjVal = inconveniences[num_course]["ObjVal"]
                chosen_num_course = num_course

        
        print(f"Solution with fixing {chosen_num_course} courses for Phase 1 is chosen. ObjVal = {minimum_ObjVal}")
        print(f"len(results) = {len(results)}. Keys = {results.keys()}")
        
        final_inconveniences = inconveniences[chosen_num_course]
        final_inconveniences["num_fixed_courses"] = chosen_num_course

        return solutions[chosen_num_course], minimum_ObjVal
    
    def get_SCIP_group2slot(self, model, num_exam_slots):
        """ Extracts the group to slot mapping from the SCIP model.
        param model: the SCIP model that was solved.
        param num_exam_slots: number of exam slots this semester has
        returns: a tuple of (group2slot, sol_schedule) where group2slot is a dict of the form {course_group: timeslot} and sol_schedule is 
                    a list of lists where each sublist contains the course groups scheduled in that time slot.
        """
        group2slot = dict()
        sol_schedule = [[] for i in range(num_exam_slots)]
        for v in model.getVars():
            try:
                solution = model.getBestSol()
                if "x_gt" in v.name and abs(model.getSolVal(solution, v) - 1) < settings.EPSILON:
                        result = re.search(r"x_gt\[(.+),([\d]+)\]", v.name)
                        sol_schedule[int(result.group(2))].append(result.group(1))
                        group2slot[result.group(1)] = int(result.group(2))
            except UnicodeDecodeError:
                print("hecked up on variable", v.name)
                pass

        return group2slot, sol_schedule

################ grasp algorithm below ########################
    def grasp_optimize(self, num_courses, penalties, seconds):
        """
        uses a Greedy Randomized Adaptive Search algo to optimize phase1. Calls the grasp algorithm as many times as it can and stores the best one
        param num_courses: number of courses to place during optimization
        param preference_profile: dict of the form {string of problem: float penalty associated with the problem}
        param seconds: timelimit on how long GRASP is allowed to run
        """
        group_sizes = self.model_creator.params["N_s"]
        max_size = 1000
        for g in self.model_creator.params["G"]:
            max_size = group_sizes[g] if group_sizes[g] > max_size else max_size

        jobs = []
        manager = multiprocessing.Manager()
        results = manager.dict()
        small = min(num_courses)
        # for _ in range(0, 2):
        for smooth in [0]:
                for i in range(0, 4):
                        large_courses = self.choose_large_classes(num_courses[i])
                        pairs, schedule = self.grasp_pair_creation(large_courses)
                        if pairs == -1:
                            print("stopping grasp due to infeasibility")
                            return {}, -1
                        p = multiprocessing.Process(target=multi_process_grasp_solver, args=(i, pairs, schedule, penalties, self.model_creator.params, max_size, seconds, smooth, results, num_courses[i]))
                        jobs.append(p)
                        p.start()

                for job in jobs:
                    job.join()
                cost = min(results)
                print("best grasp cost found:", cost)
        schedule = results[cost]
        
        #need to convert schedule to match the format phase2 expects
        phase2_format = self.convert_grasp_to_phase2(schedule)
        return phase2_format

    def convert_grasp_to_phase2(self, grasp_sol):
        phase2_format = dict()
        for key in grasp_sol.keys():
            for group in grasp_sol[key]:
                phase2_format[group] = key
        return phase2_format

    def grasp_pair_creation(self, largest_courses):
        """
        Creates all combinations of (group, valid_timeslot) in the form of grasp_pair objects
        param largest_courses: list of course_groups that will be a part of grasp optimization
        returns: list of grasp_pairs with all possible combinations of groups and timeslots
        """
        schedule = {} #key is timeslot, value is list of groups
        timeslots = self.model_creator.params["T"]
        for t in timeslots:
            schedule[t] = list()
        valid_slots = self.model_creator.params["d"]
        timeslots = [key for key in valid_slots if valid_slots[key] == 1] #only consider times that are valid
        group_sizes = self.model_creator.params["N_s"]
        pairs = []
        for g in largest_courses:
            
            if g in self.group2slot: #if there is a specific constraint on this schedule, set that now
                slot = int(self.group2slot[g])
                schedule[slot].append(g)
                if g in self.no_groupslot and slot in self.no_groupslot[g]: # if this mandatory pair is disallowed, return invalid
                    return -1, {}
                continue
            for t in timeslots:
                if g in self.no_groupslot and t in self.no_groupslot[g]: #if this pair is restricted, don't add
                    continue
                pairs.append(GraspPair(g, group_sizes[g], int(t)))
                # put other restrictions and constraints here
        return pairs, schedule

    def choose_large_classes(self, num_classes):
        """
        Chooses num_classes most popular exam groups to include in phase 1 optimization. yoinked from model creator becase I am lazy
        param num_classes: the number of large courses to add to output
        returns: a list containing all the constrained courses AND num_classes amount of the largest courses
        """
        G = self.model_creator.params["G"]
        N_s = self.model_creator.params["N_s"]

        G.sort(key=lambda group:-1 * N_s[group])

        new_G = [course for course in self.group2slot.keys()]
        for course in self.no_groupslot:
            if course not in new_G:
                new_G.append(course)
        # Add num_classes most popular courses (excluding ones in the initial constraints) and courses specified in the initial constraints.
        i = 0
        counter = len(new_G)
        while counter < num_classes and i < len(G):
            if G[i] not in new_G:
                new_G.append(G[i])
                counter += 1
            i += 1

        return new_G

class GraspPair:
    def __init__(self, g, g_size, t):
        self.group = g
        self.timeslot = t
        self.cost = 0
        self.group_size = g_size
        self.overlap = 0
        self.b2b = 0
        self.n2m = 0
        self.last_update = "None"

    def update_cost(self, new_cost):
        self.cost = new_cost

    def get_cost(self):
        return self.cost

    def __str__(self):
        return "g: {}, t: {}, cost: {}, overlap {}, b2b {}, n2m {} last update: {}".format(self.group, self.timeslot, self.cost, self.overlap, self.b2b, self.n2m, self.last_update)
    


