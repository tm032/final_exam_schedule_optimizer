"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Imports the enrollment data from the uploaded files and creates a new Semester data.
"""

import pandas as pd
import numpy as np
import datetime
import random
from io import StringIO

from ..models import Semester, CourseGroup, Course

from django.conf import settings

class DataParser:
    def __init__(self, student_csv=None, schedule_csv=None, semester=None, start_date=None, end_date=None, exam_times=None, special_course_string= ""):
        """
        param student_csv: .csv file containing all student enrollment information for the semester being created
        param schedule_csv: .csv file containing all courses and their information
        param semester: name of the current semester being created
        param start_date: datetime object representing when the exam period starts
        param end_date: datetime object for when the last day of exams
        param exam_times: comma seperated string of times when exams happen each day of exams eg "8:00 AM, 11:45 AM, 3:30 PM, 7:00 PM"
        param special_course_string: comma seperated string of what courses are to be optimized seperately from their time group.
        Uses inputed files and information to create and save a new semester object. 
        """
        # Read the data from excel file to load a new Exam Scheduling data.          
        self.semester_entry, created = Semester.objects.get_or_create(name=semester, exam_start_date=start_date, exam_end_date=end_date, exam_start_times=exam_times)
        if not created:
            # Delete all entries in the DB
            Course.objects.filter(semester=self.semester_entry).delete()
            CourseGroup.objects.filter(semester=self.semester_entry).delete()
            self.semester_entry.students_file.delete()
            self.semester_entry.exam_start_date = start_date
            self.semester_entry.exam_end_date = end_date
            

        self.schedule_info = None
        # self.schedule_file = excel_file
        self.semester = semester
        self.start_date = start_date
        self.end_date = end_date
        self.exam_times = exam_times
        self.students_df = self.read_uploaded_file(student_csv)
        if pd.api.types.is_string_dtype(self.students_df[settings.RANDOMIZED_ID_COL]):
            self.students_df[settings.RANDOMIZED_ID_COL] = self.students_df[settings.RANDOMIZED_ID_COL].str.replace(',', '').astype(int)

        self.schedule_df = self.read_uploaded_file(schedule_csv)
        self.semester_entry.special_courses = special_course_string

        self.semester_entry.academic_period = self.schedule_df.iloc[1, 1]
        print("academic period read:", self.semester_entry.academic_period)

        self.students_df = self.students_df.replace(np.NaN, -1)


        typeset = dict()
        for i in range(1, 16):
            typeset[settings.STUDENT_CRN_COL + str(i)] = "int"

        self.students_df = self.students_df.astype(typeset)

        # Standardize column names for students_df
        for i in range(1, 16):
            self.students_df.rename(columns={settings.STUDENT_CRN_COL + str(i): "CRN " + str(i)}, inplace=True)
        self.students_df.rename(columns={settings.RANDOMIZED_ID_COL: "Randomized ID"}, inplace=True)

        student_file_name = "uploads/" + str(semester).replace(" ", "_") + "_" + str(random.randint(100,999)) + ".csv"
        self.students_df.to_csv(student_file_name)
        self.semester_entry.students_file = student_file_name
        self.semester_entry.exam_start_times = exam_times
        self.semester_entry.save()

        
    def read_uploaded_file(self, uploaded_file):
        """safety method to make sure that the file can actually be read by pandas"""
        file_content = uploaded_file.read().decode('utf-8', errors='replace')  # Use appropriate encoding
        return pd.read_csv(StringIO(file_content))

    def read_data(self, special_classes, no_exam_courses):
        """
        Process the data with the definition of special_classes when the data is loaded in the beginning.
        Does not parse the optimization parameters yet, since course grouping may change.
        """

        print("Processing data: Begin reading", self.semester)
        self.store_schedules(special_classes, no_exam_courses)

    def store_schedules(self, special_classes, no_exam_courses):
        self.schedule_info = self.make_course_info_dict(self.schedule_df, no_exam_courses) # schedule_info does not contain courses without exams
        print(self.schedule_info)
        course_groupings = self.make_course_time_blocks(self.schedule_info, special_classes)

    def roundup_time(self, target_time):
        """
            Round up the time if the second field is 59.
            Example: datetime.time(9,59,59,999000) -> datetime.time(10,0) 
        """
        if target_time.second == 59 and target_time.minute == 59:
            target_time = target_time.replace(hour=target_time.hour+1, minute=0, second=0, microsecond=0)
        elif target_time.second == 59 and target_time.minute == 29:
            target_time = target_time.replace(minute=30, second=0, microsecond=0)
        elif target_time.second == 59 and target_time.minute == 9:
            target_time = target_time.replace(minute=10, second=0, microsecond=0)
        elif target_time.second == 59 and target_time.minute == 19:
            target_time = target_time.replace(minute=20, second=0, microsecond=0)
        elif target_time.second == 59 and target_time.minute == 39:
            target_time = target_time.replace(minute=40, second=0, microsecond=0)
        elif target_time.second == 59 and target_time.minute == 49:
            target_time = target_time.replace(minute=50, second=0, microsecond=0)
        else:
            target_time = target_time.replace(second=0, microsecond=0)
        return target_time


    def remove_spaces_and_non_ascii_from_faculty_name(self,instructor):
        if pd.isna(instructor):
            return ""
        words = instructor.split()
        name = ""
        for word in words:
            word = word.replace("á", "a")
            name += word
        return name

    def make_course_info_dict(self, schedule_df, no_exam_courses):
        '''
        Takes the list of spreadsheet entries and organizes them nicely into a dictionary with the information we need that looks something like this:
        {14908 : {'course_id': 'MATH101', 'class_meetings':[('MWF', datetime.time(10,0)),('M', datetime.time(19,0))], 'exam_time' : datetime.time(12,12,22,7,30,0)}}
        Also weed out entries that have NaN values for class time or exam time (i.e. classes that have no final exams)
        '''
        d = {}

        for i in range(len(schedule_df)):
            entry = schedule_df.iloc[i]
            crn = entry[settings.CRN_COL]
            class_days = entry[settings.CLASS_DAYS_COL]
            class_time = entry[settings.CLASS_TIME_COL]
            course_id = entry[settings.COURSE_ID_COL].strip()
            description = entry[settings.SCHEDULE_DESCRIPTION_COL]
            section = entry[settings.SECTION_COL]
            instructor = entry[settings.INSTRUCTOR_COL]
            title = entry[settings.TITLE_COL]

            if entry[settings.GRADABLE_COL] == "Not Gradable":
                continue
                
            # If we pre-supply the has_exam column, use it
            if "has_exam" in schedule_df.columns:
                has_exam = entry["has_exam"]
            else:
                has_exam = class_time != "" and str(crn) not in no_exam_courses

            if isinstance(class_time, str):
                #sometimes the time is in HH:MM AM/PM format... other times its in fraction of the day format... who knows why
                try:
                    class_time = datetime.datetime.strptime(class_time, '%I:%M:%S %p').time()
                except:
                    try:
                        class_time = datetime.datetime.strptime(class_time, '%I:%M %p').time()
                    except:
                        total_minutes = float(class_time) * 24 * 60
                        hours = int(total_minutes // 60)
                        minutes = int(total_minutes % 60)
                        class_time = datetime.time(hour=hours, minute=minutes)
                

            course_entry, created = Course.objects.get_or_create(semester=self.semester_entry, crn=crn)
            course_entry.course_identification = course_id
            course_entry.subject = entry[settings.SUBJECT_COL]
            course_entry.course_number = entry[settings.COURSE_NUMBER_COL]
            course_entry.section = section
            course_entry.title = title
            course_entry.instructor = instructor
            course_entry.clear = False

            # Ignore classes that have no meeting time
            if pd.isna(class_days):
                course_entry.type = Course.NO_MEETING_TIME
                d[crn] = {'course_id' : course_id, 'class_meetings' : [], 'description' : description, 'section' : section, \
                                'instructor': self.remove_spaces_and_non_ascii_from_faculty_name(instructor), 'title': title, 'has_exam': has_exam}

            else:
                if crn not in d:
                    course_entry.meeting_times = class_days + " " + self.roundup_time(class_time).strftime("%I:%M %p")
                    d[crn] = {'course_id' : course_id, 'class_meetings' : [(class_days, self.roundup_time(class_time))], \
                             'description' : description, 'section' : section, \
                                'instructor': self.remove_spaces_and_non_ascii_from_faculty_name(instructor), 'title': title, 'has_exam': has_exam}
                else:
                    course_entry.meeting_times += "," + class_days + " " + self.roundup_time(class_time).strftime("%I:%M %p")
                    d[crn]['class_meetings'] += [(class_days, self.roundup_time(class_time))]

            course_entry.save()

        return d
    
    def make_course_time_blocks(self, schedule, special_classes):
        """ Create a dictionary mapping from course group to a list of CRNs that are in that course group.
        """
        course_block_dict = {}
        course_block_dict["NO_EXAM"] = []
        no_exam_entry, created = CourseGroup.objects.get_or_create(semester=self.semester_entry, name="NO_EXAM", is_special=True)

        for crn in schedule:
            done = False    
            course_id = schedule[crn]['course_id']
            course_entry = Course.objects.get(semester=self.semester_entry, crn=crn)

            if not schedule[crn]["has_exam"] or len(schedule[crn]['class_meetings']) == 0: # No meeting time
                course_entry.course_group = no_exam_entry
                course_entry.clear = True
                course_entry.save()

                course_block_dict["NO_EXAM"] += [crn]
                done = True

            # if it is a special class
            elif course_id in special_classes:
                course_group_entry, created = CourseGroup.objects.get_or_create(semester=self.semester_entry, name=course_id, is_special=True)
                course_entry.course_group = course_group_entry
                course_entry.clear = True
                course_entry.save()

                if course_id not in course_block_dict:
                    course_block_dict[course_id] = [crn]
                else:
                    course_block_dict[course_id] += [crn]
                done = True
            else:
                for cid in special_classes:
                    course_group_entry, created = CourseGroup.objects.get_or_create(semester=self.semester_entry, name=cid, is_special=True)

                    if course_id in cid:
                        if '-' in cid:
                            # e.g. MATH101 is in MATH101-03/04
                            section = schedule[crn]['section']
                            if section in cid[8:]:
                                course_entry.course_group = course_group_entry
                                course_entry.clear = True
                                course_entry.save()

                                if cid not in course_block_dict:
                                    course_block_dict[cid] = [crn]
                                else:
                                    course_block_dict[cid] += [crn]
                                done = True
                        else:
                            # e.g. MATH101 is in MATH101/MATH102
                            course_entry.course_group = course_group_entry
                            course_entry.clear = True
                            course_entry.type = Course.SPECIAL_COURSE
                            course_entry.save()
                            
                            if cid not in course_block_dict:
                                course_block_dict[cid] = [crn]
                            else:
                                course_block_dict[cid] += [crn]
                            done = True
            
            if not done:
                # It's not a special class
                class_meeting = self.describe_meeting_time(self.find_time_to_use(crn, schedule))
                course_group_entry, created = CourseGroup.objects.get_or_create(semester=self.semester_entry, name=class_meeting, is_special=False)

                course_entry.course_group = course_group_entry
                course_entry.clear = False

                if len(schedule[crn]["class_meetings"]) == 1:
                    course_entry.type = Course.ONE_MEETING_TIME
                else:
                    course_entry.type = Course.MULTIPLE_MEETING_TIME

                course_entry.save()
                
                if class_meeting not in course_block_dict:
                    course_block_dict[class_meeting] = [crn]
                else:
                    course_block_dict[class_meeting] += [crn]
                
                
        return course_block_dict
        
    def describe_meeting_time(self, class_meeting):
        """
        Convert the tuple of meeting time and datetime.time to a string

        Example: ('MWF', datetime.time(13, 30)) -> 'MWF1330'
        """
        meeting_days = class_meeting[0]
        meeting_time = class_meeting[1]
        return "{0}{1:02d}{2:02d}".format(meeting_days, meeting_time.hour, meeting_time.minute)

    def find_time_to_use(self, crn, course_info_dict):
        '''
        If a course is assigned multiple different class meeting times,
        there are a number of possibilities. Common hours are a once a
        week meeting time shared by multiple sections. An exam time is
        a once a week meeting time that might be specific to one section.
        
        There are also labs that occur once a week for some courses.
        For common hours and exam times, the final exam tends to be
        associated with this time. For labs, the final exam is associated
        with the regular class time (not the lab). We identify which time
        to use as follows:  

            - If the crn only has one class time, use that one.
            - If it has two: If the type of course is lecture, use the one that 
            occurs less frequently. 
            - If the type is lecture/lab, use the one that
            occurs more frequently. 
            - If it has three: If the type is lecture, 
            use the one that occurs least frequently AND is later in the day. 
            - If the type is lecture/lab, use the one that occurs more frequently.
        '''
        class_meetings = course_info_dict[crn]['class_meetings']
        description = course_info_dict[crn]['description']

        if len(class_meetings) == 2:
            
            if len(class_meetings[0][0]) < len(class_meetings[1][0]):
                less_frequent = class_meetings[0]
                more_frequent = class_meetings[1]
            elif len(class_meetings[0][0]) > len(class_meetings[1][0]):
                less_frequent = class_meetings[1]
                more_frequent = class_meetings[0]
            else: # they are equally as frequent
                if class_meetings[0][1] == class_meetings[1][1]: # at same time
                    less_frequent = more_frequent = self.merge_course_times(class_meetings[0], class_meetings[1])
                else: # Unexpected case, just choose at random
                    less_frequent = more_frequent = class_meetings[0]    
            
            if description == 'Lecture' or description == 'Common Hour':
                return less_frequent
            else:  # Lecture/Lab
                return more_frequent
            
        if len(class_meetings) == 3:
            most_frequent = class_meetings[0]
            least_frequent = class_meetings[0]
            for meeting in class_meetings:
                if len(meeting[0]) > len(most_frequent[0]):
                    most_frequent = meeting
                if len(meeting[0]) < len(least_frequent[0]):
                    least_frequent = meeting
                if len(meeting[0]) == len(least_frequent[0]):  # equally as frequent
                    if meeting[1] > least_frequent[1]:  # one of them occurs later in the day (for example 7pm common hour/exam time)
                        least_frequent = meeting

            if description == 'Lecture':
                return least_frequent
            else:  # Lecture/Lab
                return most_frequent
            
        # If we haven't returned by now, just return the first meeting time
        return class_meetings[0]
    
    def merge_course_times(self,mtg1, mtg2):
        order_of_days = {'M':0, 'T':1, 'W':2, 'R':3, 'F':4}
        if mtg1[1] == mtg2[1]:
            # They have the same time, combine the days
            day1 = mtg1[0]
            day2 = mtg2[0]
            if order_of_days[day1] < order_of_days[day2]:
                combined_days = day1 + day2
            else:
                combined_days = day2 + day1
            return (combined_days, mtg1[1])
        else:
            return mtg1