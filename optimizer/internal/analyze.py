"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

This file contains the internal logic for analyzing the schedule and computes inconvenience statistics.
"""


from ..internal import create_model, schedule
from datetime import datetime
import pandas as pd
import copy

"""
Class that analyzes the given schedule
"""
class Analyzer:
    def __init__(self, schedule_entry):
        """
        param schedule_entry: schedule object to be analyzed
        This object is meant to get information on what issues this schedule object has. The object must already have been optimized.
        Reuses some of the model_creator sets to do so. It saves the results into the schedule_entry itself so no return values here.
        """

        self.semester_entry = schedule_entry.semester
        model_creator = create_model.ModelCreator(self.semester_entry)
        model_creator.load_course_info(schedule_entry.course_info)
        model_creator.compute_sets()
        model_creator.compute_d_n()
        model_creator.compute_h_nx()

        self.data = model_creator.get_params()
                
        self.semester = self.semester_entry.name
        start_date = self.semester_entry.exam_start_date
        end_date = self.semester_entry.exam_end_date
        self.duration = (end_date - start_date).days + 1
        self.course_info = model_creator.get_course_info()
        self.course_groupings = model_creator.get_course_groupings()
        self.students_df = model_creator.get_students_df() 

        self.group2slot = schedule.get_group2slot(schedule_entry)
        self.compute_sol_schedule(self.group2slot, self.semester_entry)

    def compute_sol_schedule(self, group2slot, semester_entry):
        """
        Gets group2slot and sol_schedule list from group2slot
        """    
        time_strings = semester_entry.exam_start_times.split(",")
        daily_num_exams = len(time_strings)
        duration = semester_entry.exam_end_date - semester_entry.exam_start_date
        self.sol_schedule = [[] for i in range(self.duration * daily_num_exams)]

        for group in group2slot.keys():
            self.sol_schedule[group2slot[group]].append(group)

    def analyze_sol(self):
        """
        Analyze a given solution
        """    
        students_df = self.students_df
        copy_students_df = copy.deepcopy(students_df)
        schedule_info = self.course_info

        n = self.data["n"]

        students_processed = 0
        missing = {}
        
        for id in students_df["Randomized ID"].tolist():
            for i in range(1, 16):
                crn = students_df.loc[students_df["Randomized ID"] == id]["CRN " + str(i)].values[0]
                        
                if pd.isnull(crn) or pd.isna(crn) or crn == -1:
                    continue

                # CRN may be a string or an int, so check both
                if str(crn) not in schedule_info and int(crn) not in schedule_info:
                    copy_students_df.loc[copy_students_df["Randomized ID"] == id,"CRN " + str(i)] = -1
                    continue
                elif str(crn) in schedule_info:
                    group = schedule_info[str(crn)]["course_group"]
                elif int(crn) in schedule_info:
                    group = schedule_info[int(crn)]["course_group"]
                
                if pd.isnull(group) or pd.isna(group):
                    copy_students_df.loc[copy_students_df["Randomized ID"] == id,"CRN " + str(i)] = -1
                    continue
                elif group not in self.group2slot: # the group does exist but it is not in the optimized schedule
                    copy_students_df.loc[copy_students_df["Randomized ID"] == id,"CRN " + str(i)] = -1
                    if crn not in missing:
                        missing[crn] = 1
                    else:
                        missing[crn] += 1
                    continue

                copy_students_df.loc[copy_students_df["Randomized ID"] == id,"CRN " + str(i)] = self.group2slot[group]

            students_processed += 1   
                     
        bad_groups = []        
        for crn in missing:
            print(f"{crn} missed {missing[crn]} times")

            if str(crn) in schedule_info:
                group = schedule_info[str(crn)]["course_group"]
            else:
                group = schedule_info[int(crn)]["course_group"]

            if group not in bad_groups:
                bad_groups.append(group)
            

        print(f"missing crns: {len(missing)}, total misses: {sum(missing.values())}")
        print(f"missing groups: {len(bad_groups)}\n {bad_groups}")
        
        OVERLAP = "student_overlap"
        FORCED_OVERLAP = "forced_overlap"
        THREE_IN_24 = "three_in_24"
        FOUR_IN_48 = "four_in_48"
        BACK_TO_BACK = "student_back_to_back"
        NIGHT_MORNING = "night_morning"
        INCONVENIENT_STUDENT = "inconvenient_students"
        F_OVERLAP = "faculty_overlap"
        F_B2B = "faculty_back_to_back"

        global_issues = dict()
        global_issues[OVERLAP] = 0
        global_issues[FORCED_OVERLAP] = self.data["forced_overlap"]
        global_issues[BACK_TO_BACK] = 0
        global_issues[NIGHT_MORNING] = 0
        global_issues[THREE_IN_24] = 0
        global_issues[FOUR_IN_48] = 0
        global_issues[INCONVENIENT_STUDENT] = 0
        
        student_overlap_problems = []
        student_b2b_problems = []
        night_morning_problems = []
        three_in_24_problems = []
        four_in_48_problems = []
        inconvenience_problems = []

        global_issues[F_OVERLAP], fac_overlap_problems = self.find_faculty_overlaps(schedule_info,self.sol_schedule)
        global_issues[F_B2B], fac_b2b_problems = self.find_faculty_back_to_back(schedule_info,self.sol_schedule)

        students_analyzed = 0

        inconvenient_count = 0


        for id in students_df["Randomized ID"].tolist():
            inconvenient = False

            timeslots = list()
            local_issues = dict()
            crns = list()
            local_issues[OVERLAP] = 0
            local_issues[THREE_IN_24] = 0
            local_issues[FOUR_IN_48] = 0
            local_issues[BACK_TO_BACK] = 0
            local_issues[NIGHT_MORNING] = 0

            for i in range(1, 16):
                timeslot = copy_students_df.loc[copy_students_df["Randomized ID"] == id]["CRN " + str(i)].values[0]
                if timeslot != -1:
                    timeslots.append(timeslot)
                    crns.append(int(students_df.loc[copy_students_df["Randomized ID"] == id]["CRN " + str(i)].values[0]))
            if len(timeslots) == 0:
                continue

            
            #combine so sorting the timeslots sorts the crns into the same order
            combined_data = list(zip(crns, timeslots))

            # Sort the tuples based on the timeslots
            sorted_data = sorted(combined_data, key=lambda x: x[1])  # Sort based on the second element (timeslot)

            # Unzip the sorted tuples back into separate crns and timeslots lists
            crns, timeslots = zip(*sorted_data)

            unique_timeslots = list(copy.deepcopy(timeslots))

            # Overlap
            for i in range(len(timeslots) - 1):
                if timeslots[i] == timeslots[i + 1]:
                    inconvenient = True
                    local_issues[OVERLAP] += 1
                    unique_timeslots.remove(timeslots[i])
                    print("Overlap!", id, timeslots[i], "Enrolled Groups:", end=" ")
                    print("timeslot:", self.timeslot_to_time(timeslots[i]))
                    student_overlap_problems.append("ID: {}, timeslot: {}, crns: {}, {}".format(id, self.timeslot_to_time(timeslots[i]), crns[i], crns[i+1]))
                    for j in range(1, 16):
                        crn = students_df.loc[students_df["Randomized ID"] == id]["CRN " + str(j)].values[0]
                        timeslot = copy_students_df.loc[copy_students_df["Randomized ID"] == id]["CRN " + str(j)].values[0]
                        if pd.isnull(crn) or pd.isna(crn) or crn == -1 or pd.isna(timeslot) or timeslot == -1:
                            continue
                        
            timeslots = unique_timeslots
                
            for i in range(len(timeslots) - 1):
                # 4 in 48 hours
                if i < len(timeslots) - 3:
                    if timeslots[i + 3] - timeslots[i] < 8:
                        first_exam_time = self.timeslot_to_time_object(timeslots[i])
                        fourth_exam_time = self.timeslot_to_time_object(timeslots[i + 3])
                        hours = (fourth_exam_time - first_exam_time).total_seconds() / 3600
                        if hours < 48:
                            local_issues[FOUR_IN_48] = 1
                            four_in_48_problems.append("ID: {}, timeslot: {}".format(id, self.timeslot_to_time(timeslots[i])))
                            inconvenient = True
                        

                # 3 in 24 hours
                if i < len(timeslots) - 2:
                    first_exam_time = self.timeslot_to_time_object(timeslots[i])
                    third_exam_time = self.timeslot_to_time_object(timeslots[i + 2])
                    hours = (third_exam_time - first_exam_time).total_seconds() / 3600
                    if hours < 24:
                        local_issues[THREE_IN_24] = 1
                        three_in_24_problems.append("ID: {}, timeslot: {}".format(id, self.timeslot_to_time(timeslots[i])))
                        inconvenient = True

                # Back to back exam
                if timeslots[i + 1] - timeslots[i] == 1 and n[timeslots[i]] == 0: 
                    local_issues[BACK_TO_BACK] += 1
                    student_b2b_problems.append("ID: {}, first timeslot: {}".format(id, self.timeslot_to_time(timeslots[i])))
                    inconvenient = True

                # Night to morning exam
                if timeslots[i + 1] - timeslots[i] == 1 and n[timeslots[i]] == 1:
                    local_issues[NIGHT_MORNING] += 1
                    night_morning_problems.append("ID: {}".format(id))
                    inconvenient = True
                    
            global_issues[OVERLAP] += local_issues[OVERLAP]
            global_issues[THREE_IN_24] += 0 if local_issues[THREE_IN_24] == 0 else 1
            global_issues[FOUR_IN_48] += 0 if local_issues[FOUR_IN_48] == 0 else 1
            global_issues[BACK_TO_BACK] += local_issues[BACK_TO_BACK]
            global_issues[NIGHT_MORNING] += local_issues[NIGHT_MORNING]
            
            if inconvenient:
                inconvenient_count += 1

            # Computes the number of students with inconvenient schedules
            if local_issues[OVERLAP] > 0 or local_issues[THREE_IN_24] > 0 or local_issues[FOUR_IN_48] > 0 or local_issues[BACK_TO_BACK] > 0 or local_issues[NIGHT_MORNING] > 0:
                global_issues[INCONVENIENT_STUDENT] += 1
                inconvenience_problems.append("ID: {}".format(id))
            
            students_analyzed += 1
            
            if students_analyzed % 1000 == 0:
                print(students_analyzed, "students analyzed")
            
        print("Total students analyzed:", students_analyzed)
        print("Total students with issues:", inconvenient_count)
        for key in [OVERLAP, FORCED_OVERLAP, THREE_IN_24, FOUR_IN_48, BACK_TO_BACK, NIGHT_MORNING, INCONVENIENT_STUDENT, F_OVERLAP, F_B2B]:
            print(key, global_issues[key])

        problem_dict = dict()
        problem_dict[OVERLAP] = student_overlap_problems
        problem_dict[BACK_TO_BACK] = student_b2b_problems
        problem_dict[NIGHT_MORNING] = night_morning_problems
        problem_dict[THREE_IN_24] = three_in_24_problems
        problem_dict[FOUR_IN_48] = four_in_48_problems
        problem_dict[INCONVENIENT_STUDENT] = inconvenience_problems
        problem_dict[F_OVERLAP] = fac_overlap_problems
        problem_dict[F_B2B] = fac_b2b_problems
        return global_issues, problem_dict



    def find_faculty_overlaps(self, info, sol_schedule):
        """
        Analyze faculty overlaps. 
        We consider an overlap if a faculty has two courses with different course titles scheduled at the same time.
        Crosslisted courses are not considered as overlaps.
        """
        num_overlaps = 0
        problems = []

        for i in range(len(sol_schedule)):
            d = {}
            for g in sol_schedule[i]:
                if g not in self.course_groupings:
                    continue
                crns = self.course_groupings[g]
                for crn in crns:
                    instructor = info[crn]['instructor']
                    if instructor != "":
                        course = (info[crn]['course_id'], info[crn]['title'])
                        if not pd.isna(instructor) and instructor != "TBD":
                            if instructor not in d:
                                d[instructor] = [course]
                            else:
                                names = [t[1] for t in d[instructor]]

                                # Check if the name of the new tuple is already in the list
                                if course[1] not in names: 
                                    d[instructor].append(course)
            for inst in d:
                if len(d[inst]) > 1:
                    print("Overlap:", inst, i, d[inst])
                    problems.append("Faculty: {}, Time: {}, courses: {}".format(inst, self.timeslot_to_time(i), d[inst]))
                    num_overlaps += 1
        return num_overlaps, problems

    def find_faculty_back_to_back(self, info, sol_schedule): 
        """
        Analyze faculty back to backs.
        We consider a back to back exam if a faculty has two courses with different course titles scheduled in consecutive time slots.
        Crosslisted courses are not considered as back to backs.
        """
        instructors = []
        for crn in info:
            instructor = info[crn]['instructor']
            if instructor not in instructors and not pd.isna(instructor) and instructor != "TBD":
                instructors.append(instructor)

        problems = []    
        num_B2B = 0
        for f in instructors:   
            for i in range(0,len(sol_schedule)-1): # starting time slot index
                exam_in_first_slot = False
                exam_in_second_slot = False
                crn1 = -1
                crn2 = -1
                for g in sol_schedule[i]:
                    if g not in self.course_groupings:
                        continue
                    crns = self.course_groupings[g]
                    for crn in crns:
                        instructor = info[crn]['instructor']
                        if f == instructor:
                            exam_in_first_slot = True
                            crn1 = crn
                            break
                for g in sol_schedule[i+1]:
                    if g not in self.course_groupings:
                        continue
                    crns = self.course_groupings[g]
                    for crn in crns:
                        instructor = info[crn]['instructor']
                        if f == instructor:
                            exam_in_second_slot = True
                            crn2 = crn
                            break
                if exam_in_first_slot and exam_in_second_slot:
                    num_B2B += 1
                    # problems.append((f, int(crn1), int(crn2)))
                    problems.append("Faculty: {}, CRNS: {}, {}".format(f, int(crn1), int(crn2)))
        
        return num_B2B, problems

    def timeslot_to_time(self, timeslot):
        """ Converts a timeslot index to a human-readable time string.

        Args: timeslot (int): the index of the timeslot to convert.
        
        Returns: date and time in string format
        """
        exam_strings = self.semester_entry.exam_start_times.split(",")
        daily_num_exams = len(exam_strings)
        exam_slot = int(timeslot % daily_num_exams)
        exam_day = int(timeslot // daily_num_exams)

        exam_time = datetime.strptime(exam_strings[exam_slot].lstrip(), "%I:%M %p")
        date = datetime(self.semester_entry.exam_start_date.year, self.semester_entry.exam_start_date.month, self.semester_entry.exam_start_date.day + exam_day,
                        hour= exam_time.hour, minute= exam_time.minute)
        return date.strftime("%A, %m/%d, %I:%M %p")
     
    def timeslot_to_time_object(self, timeslot):
        """ Converts a timeslot index to a datetime object.

        Args: timeslot (int): the index of the timeslot to convert.

        Returns: datetime object of the corresponding exam time
        """
        exam_strings = self.semester_entry.exam_start_times.split(",")
        daily_num_exams = len(exam_strings)
        exam_slot = int(timeslot % daily_num_exams)
        exam_day = int(timeslot // daily_num_exams)

        exam_time = datetime.strptime(exam_strings[exam_slot].lstrip(), "%I:%M %p")
        date = datetime(self.semester_entry.exam_start_date.year, self.semester_entry.exam_start_date.month, self.semester_entry.exam_start_date.day + exam_day,
                        hour= exam_time.hour, minute= exam_time.minute)
        return date  