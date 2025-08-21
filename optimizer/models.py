"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Definition of the database models (entries) used in the application
"""

from django.db import models

"""
Keeps track of the semester and the exam start and end dates.
This application will assume that there will be no exam on weekends, Friday night, and the night of the last day.
"""
class Semester(models.Model):
    name = models.CharField(max_length=100, unique=True)
    exam_start_date = models.DateField()
    exam_end_date = models.DateField()
    academic_period = models.CharField(default="None", max_length=100)
    date_created = models.DateField(auto_now_add=True)
    special_courses = models.CharField(default= 0, max_length=1000)

    students_file = models.FileField(upload_to ='uploads/', blank=True)
    exam_start_times = models.CharField(max_length=150, default="8:00 AM, 11:45 AM, 3:30 PM, 7:30 PM")

    def __str__(self):
        return "Semester: " + str(self.name)


"""
Keeps track of the generated schedule
"""
class Schedule(models.Model):
    CREATED = 0
    ANALYZED = 1
    ANALYZING = 2
    NOT_YET_ANALYZED = 3
    PHASE_0 = 10
    PHASE_1 = 11
    PHASE_2 = 12
    INIT_ANALYSIS = 13
    INFEASIBLE = 14
    ERROR = 99

    choice_display = {
        CREATED: "The schedule is successfully created.",
        ANALYZED: "The schedule is analyzed.",
        ANALYZING: "Analyzing the schedule...",
        NOT_YET_ANALYZED: "The schedule is updated and hasn't being analyzed yet.",
        PHASE_0: "Step 1/3 Creating the IP model for schedule generation...",
        PHASE_1: "Step 2/3 Initial optimization...",
        PHASE_2: "Step 3/3 Final optimization...",
        INIT_ANALYSIS: "Analyzing the schedule...",
        INFEASIBLE: "ERROR. Conflicting constraints set, delete and try again",
        ERROR: "ERROR. Delete and try again.",
    }

    TYPE_CHOICES = [
        (CREATED, choice_display[CREATED]),
        (ANALYZED, choice_display[ANALYZED]),
        (ANALYZING, choice_display[ANALYZING]),
        (NOT_YET_ANALYZED, choice_display[NOT_YET_ANALYZED]),
        (PHASE_0, choice_display[PHASE_0]),
        (PHASE_1, choice_display[PHASE_1]),
        (PHASE_2, choice_display[PHASE_2]),
        (INIT_ANALYSIS, choice_display[INIT_ANALYSIS]),
        (ERROR, choice_display[ERROR]),
    ]

    name = models.CharField(max_length=100, unique=True)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, null=True)
    preference_profile = models.JSONField(null=True, blank=True)
    group_constraints = models.JSONField(null=True, blank=True)
    predefined_constraints = models.JSONField(null=True, blank=True)
    students_overlap = models.IntegerField(default=0)
    student_forced_overlap = models.IntegerField(default=0)
    students_3in24 = models.IntegerField(default=0)
    students_4in48 = models.IntegerField(default=0)
    students_b2b = models.IntegerField(default=0)
    students_night_morning = models.IntegerField(default=0)
    inconvenient_students = models.IntegerField(default=0)

    faculty_overlap = models.IntegerField(default=0)
    faculty_b2b = models.IntegerField(default=0)
    analyzed = models.BooleanField(default=False)
    current_version = models.OneToOneField('ScheduleVersion', on_delete=models.SET_NULL, null=True, blank=True, related_name='current_version')

    student_overlap_problems = models.JSONField(null=True, blank=True)
    student_3in24_problems = models.JSONField(null=True, blank=True)
    student_4in48_problems = models.JSONField(null=True, blank=True)
    student_b2b_problems = models.JSONField(null=True, blank=True)
    student_night_morning_problems = models.JSONField(null=True, blank=True)
    inconvenient_students_list = models.JSONField(null=True, blank=True)

    faculty_overlap_problems = models.JSONField(null=True, blank=True)
    faculty_b2b_problems = models.JSONField(null=True, blank=True)

    portfolio_id = models.IntegerField(default = -1)

    status = models.CharField(max_length=5, choices=TYPE_CHOICES, default=CREATED)
    is_duplicated = models.BooleanField(default=False)
    original = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    course_info = models.JSONField(default=dict)

    def __str__(self):
        return "Schedule: " + str(self.name)

    def get_status(self):
        return Schedule.choice_display[int(self.status)]

"""
Stores information about the exam course group for a given semester.
There will be a 'NO_EXAM' Course group that is used to group all courses with no exams. 
It will not be used in the scheduling.
"""
class CourseGroup(models.Model):
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, null=True) # Checks if a DB entry's data targets the same semester as the pkl file.
    name = models.CharField(max_length=100)
    is_special = models.BooleanField(default=False)

    def __str__(self):
        return "Course Group: " + str(self.name)
    
"""
Schedule data
Each CourseGroupSchedule describes a course group's assigned slot in the particular schedule
"""
class CourseGroupSchedule(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, null=True)
    slot_id = models.IntegerField(default=-1)
    name = models.CharField(max_length=100, null=True)
    has_exam = models.BooleanField(default=True)
    is_special = models.BooleanField(default=False)


    def __str__(self):
        return "Course Group: " + str(self.name) + " at slot: " + str(self.slot_id)


"""
Stores information about the course in a given semester
"""
class Course(models.Model):
    NO_MEETING_TIME = 9
    ONE_MEETING_TIME = 0
    SPECIAL_COURSE = 1
    MULTIPLE_MEETING_TIME = 2

    TYPE_CHOICES = (
        (NO_MEETING_TIME, "No meeting time"),
        (ONE_MEETING_TIME, "Single meeting time"),
        (SPECIAL_COURSE, "Special Course"),
        (MULTIPLE_MEETING_TIME, "Multiple meeting times"),
    )

    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, null=True)
    course_group = models.ForeignKey(CourseGroup, on_delete=models.CASCADE, null=True)

    crn = models.CharField(max_length=10)
    course_identification = models.CharField(max_length=10) # Example: MATH201
    subject = models.CharField(max_length=4) # Example: MATH
    course_number = models.CharField(max_length=6) # Example: 201
    section = models.CharField(max_length=5) # Example: 01
    title = models.CharField(max_length=200) 
    meeting_times = models.CharField(max_length=200)
    instructor = models.CharField(max_length=200)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=MULTIPLE_MEETING_TIME)
    clear = models.BooleanField(default=False)

    def __str__(self):
        return str(self.crn) + " " + str(self.course_identification) + " " + str(self.title)

"""
Stores a dictionary of penalties used during opimization. 
Created/deleted by the user and selected during schedule creation to influence optimization
"""
class PreferenceProfile(models.Model):
    name = models.TextField(max_length=50)
    overlap = models.FloatField(default=1)
    threein24 = models.FloatField(default=0.1)
    fourin48 = models.FloatField(default=0.2)
    backtoback = models.FloatField(default=0.02)
    nighttomorning = models.FloatField(default=0.04)
    night = models.FloatField(default=0)
    facultyoverlap = models.FloatField(default=0.2)
    facultybacktoback = models.FloatField(default=0.05)
    
    def __repr__(self):
        return (f"Overlap: {self.overlap}, "
                f"Three in 24: {self.threein24}, "
                f"Four in 48: {self.fourin48}, "
                f"Back to Back: {self.backtoback}, "
                f"Night to Morning: {self.nighttomorning}, "
                f"Night: {self.night}, "
                f"Faculty Overlap: {self.facultyoverlap}, "
                f"Faculty Back to Back: {self.facultybacktoback}")
    
    def __str__(self):
        return self.name
    
    def get_penalty_dictionary(self):
        return {
            'overlap': self.overlap,
            'threein24': self.threein24,
            'fourin48': self.fourin48,
            'B2B': self.backtoback,
            'PMtoAM': self.nighttomorning,
            'night': self.night,
            'facultyoverlap': self.facultyoverlap,
            'facultyB2B': self.facultybacktoback}
    
    def get_phase1_penalty_dictionary(self):
        return {
            'overlap': self.overlap,
            'B2B': self.backtoback,
            'PMtoAM': self.nighttomorning,}

"""
Stores a specific version of a schedule. If the user creates changes after optimization by drag and drop, they can save that new version using this database
"""    
class ScheduleVersion(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='versions')
    name = models.TextField(max_length=50, default="New Version")
    group2slot = models.JSONField()
    students_overlap = models.IntegerField(default=0)
    students_3in24 = models.IntegerField(default=0)
    students_4in48 = models.IntegerField(default=0)
    students_b2b = models.IntegerField(default=0)
    students_night_morning = models.IntegerField(default=0)
    faculty_overlap = models.IntegerField(default=0)
    faculty_b2b = models.IntegerField(default=0)
    inconvenient_students = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    student_overlap_problems = models.JSONField(null=True, blank=True)
    student_3in24_problems = models.JSONField(null=True, blank=True)
    student_4in48_problems = models.JSONField(null=True, blank=True)
    student_b2b_problems = models.JSONField(null=True, blank=True)
    student_night_morning_problems = models.JSONField(null=True, blank=True)
    faculty_overlap_problems = models.JSONField(null=True, blank=True)
    faculty_b2b_problems = models.JSONField(null=True, blank=True)
    inconvenient_students_list = models.JSONField(null=True, blank=True)






    def __str__(self):
        return f"Version {self.pk}"
    
class PortfolioID(models.Model):
    current_id = models.IntegerField(default=1)

    def get_new_id(self):
        val = int(self.current_id)
        self.current_id += 1
        self.save()
        return val