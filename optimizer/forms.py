"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Defines forms used in the applications.
"""

from django import forms
from .models import PreferenceProfile
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from datetime import datetime, timedelta


"""
The form used to load the course enrollment information in the beginning.
The application will create a timeslots based on the start_date and end_date.
It will create four slots per every weekday between the start_date and end_date.
"""
class LoaderForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(LoaderForm, self).__init__(*args, **kwargs)

    semester = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.TextInput(attrs={'class': "form-control",
                                      'id': "semester",
                                      'placeholder': 'E.g. Spring Term 2022-2023'})
    )

    # Start date of the exam
    start_date = forms.DateField(
        required=True,
        widget=forms.TextInput(attrs={'class': "form-control", 
                                      'type': "date",
                                       'id': "start_date"})
    )

    # Start date of the exam (inclusive)
    end_date = forms.DateField(
        required=True,
        widget=forms.TextInput(attrs={'class': "form-control", 
                                      'type': "date",
                                       'id': "end_date" })
    )

    # List of special courses separated by comma
    special_courses = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': "form-control", 
            'id': "special_courses",
            'rows': 3
        })
    )

    # List of CRNs without exams separated by comma
    no_exam_crns = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': "form-control", 
            'id': "no_exam_crns",
            'rows': 3
        })
    )

    # 2 separate csv files supplied by the registrar
    student_file_csv = forms.FileField(
        required=True,
        max_length=(5 * 1024 * 1024),
        validators=[FileExtensionValidator(['csv'])],
        widget=forms.FileInput(attrs={'class': "file", 'accept': ".csv"})
    )

    course_file_csv = forms.FileField(
        required=True,
        max_length=(5 * 1024 * 1024),
        validators=[FileExtensionValidator(['csv'])],
        widget=forms.FileInput(attrs={'class': "file", 'accept': ".csv"})
    )

    times = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': "form-control",
            'id': "times",
            'rows': 3,
            'placeholder': 'Enter times seperated by commas. Example: 11:45 AM, 3:30 PM'
        })
    )

    def clean_times(self):
        data = self.cleaned_data['times']
        time_list = data.split(",")

        # Validate number of times
        if not (1 <= len(time_list) <= 5):
            raise forms.ValidationError("You must enter between 1 and 5 exam times.")

        # Convert string times to datetime objects and validate format
        parsed_times = []
        for time_str in time_list:
            try:
                parsed_time = datetime.strptime(time_str.strip(), '%I:%M %p')
                parsed_times.append(parsed_time)
            except ValueError:
                raise forms.ValidationError(f"Invalid time format: {time_str}. Use hour:minute AM/PM format. ex 8:00 AM")

        # Validate times are within the allowed range (6 AM to 9 PM)
        for time in parsed_times:
            if time < datetime.strptime("6:00 AM", '%I:%M %p') or time > datetime.strptime("9:00 PM", '%I:%M %p'):
                raise forms.ValidationError(f"Time {time.strftime('%I:%M %p')} is out of allowed range (6:00 AM to 9:00 PM).")

        # Validate times are at least 3 hours apart
        parsed_times.sort()
        for i in range(len(parsed_times) - 1):
            if parsed_times[i+1] - parsed_times[i] < timedelta(hours=3):
                raise forms.ValidationError("Times must be at least 3 hours apart.")

        return data

""" 
Form that is used to search courses in the settings tab
"""
class CourseSearchForm(forms.Form):
    USE_CRN = 1
    USE_COURSE_NUMBER = 2
    USE_COURSE_NAME = 3
    USE_FACULTY_NAME = 4
    USE_COURSE_GROUP = 5

    SEARCH_OPTION = (
        (USE_COURSE_NUMBER, "Search via course number (e.g. MATH201)"),
        (USE_CRN, "Search via CRN"),
        (USE_COURSE_NAME, "Search via course name"),
        (USE_FACULTY_NAME, "Search via instructor's name"),
        (USE_COURSE_GROUP, "Search via course group (e.g. MWF0900)")
    )

    def __init__(self, *args, **kwargs):
        super(CourseSearchForm, self).__init__(*args, **kwargs)
        self.fields['ambiguous'].required = False
        self.fields['search_field'].required = False

    search_method = forms.ChoiceField(
        required=True,
        choices=SEARCH_OPTION,
        widget=forms.Select(attrs={'class': "form-control",
                                   'id': 'search_method'})
    )

    search_field = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={'class': "form-control", 
                                      'id': 'search_field'})
    )

    ambiguous = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': "form-control",
                                                                        'id': 'ambiguous'}))



""" 
Form that is used to import the saved schedule
"""
class ScheduleImportForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(ScheduleImportForm, self).__init__(*args, **kwargs)
    
    # Schedule file must be a json file downloaded from the application.
    schedule_file = forms.FileField(
        required=True,
        max_length=(5 * 1024 * 1024),
        validators=[FileExtensionValidator(['json'])],
        widget=forms.FileInput(attrs={'class': "", 'accept': ".json"})
    )

""" 
Form that is used to import the saved schedule
"""
class CourseGroupImportForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(CourseGroupImportForm, self).__init__(*args, **kwargs)
    
    # Schedule file must be a json file downloaded from the application.
    group_file = forms.FileField(
        required=True,
        max_length=(5 * 1024 * 1024),
        validators=[FileExtensionValidator(['json'])],
        widget=forms.FileInput(attrs={'class': "", 'accept': ".json"})
    )

class PreferenceProfileForm(forms.ModelForm):
    class Meta:
        model = PreferenceProfile
        fields = [
            'name',
            'threein24',
            'fourin48',
            'backtoback',
            'nighttomorning',
            'night',
            'facultyoverlap',
            'facultybacktoback'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control small-input'}),
        }