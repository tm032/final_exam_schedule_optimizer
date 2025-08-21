# Final Exam Schedule Optimizer
Tsugunobu Miyake
tm032@bucknell.edu  
Luke Snyder
las069@bucknell.edu  
Vy Tran
vlt002@bucknell.edu

## User Manual
https://docs.google.com/document/d/1YXb1GXBP5j3najFNDA2rA7T9Nd5G6RHDPI1lY0sZoKM/edit?usp=sharing 

## Preparing the Data
The Exam Scheduler requires two CSV files for the Course Information Data and Student Enrollment Data. More details can be found in the User Manual. Sample dataset with a few entries can be found in the `sample_dataset` folder.

## How to run application locally
1. Download everything into a local computer
2. Open terminal and move to the location of the folder using `cd` command.
3. Execute the following command in the terminal. `python manage.py runserver`
4. Access http://127.0.0.1:8000 on your browser.

## Key Configurations for administrators
The administrator can edit the file `ExamScheduler/settings.py` which contains configurations for the Exam Optimizer system. Here are the descriptions.

### Configuration Variables

| Variable Name              | Description                                                                                                                                     | Recommended Value                         |
|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------|
| `OPT_HOME_DIR`             | Directory that stores the temporary optimization files.                                                                                        | `os.path.join(BASE_DIR, "temp")`          |
| `MAX_STUDENTS_PER_SLOT`    | Maximum number of students per time slot. Hard limit to ensure not too many courses are scheduled at the same time.                            | `1500`                                    |
| `USE_GRASP`                | Whether to use GRASP algorithm during the optimization.                                                                                        | `True`                                    |
| `PHASE_1_NUM_COURSES`      | List of the number of courses to optimize in the phase 1 optimization. Each thread will attempt to optimize a schedule with the given number of fixed courses. | `[17, 18, 19, 20, 21]`         |
| `PHASE_1_TIME_LIMIT`       | Proceed to the phase 2 optimization after phase 1 after not finding any new incumbent solutions for the given seconds.                          | `30`                                      |
| `PHASE_2_TIME_LIMIT`       | Time limit for phase 2 optimization                                                                                                             | `60 * 60 * 3` (2 to 6 hours)              |
| `RANDOMIZED_ID_COL`        | Column name in Students CSV file that represents the randomized student ID                                                                        | `"Randomized ID"`                         |
| `STUDENT_CRN_COL`          | Prefix for course registration number columns in Students CSV file (e.g., `"CRN 1"`, `"CRN 2"`, ...)                                              | `"CRN "`                                  |
| `CRN_COL`                  | Column name in Courses CSV file for course reference number                                                                                       | `"Course Reference Number"`               |
| `CLASS_DAYS_COL`           | Column name in Courses CSV file for meeting days                                                                                                  | `"Meeting Days"`                          |
| `CLASS_TIME_COL`           | Column name in Courses CSV file for section begin time                                                                                           | `"Section Begin Time"`                    |
| `COURSE_ID_COL`            | Column name in Courses CSV file for course identification                                                                                         | `"Course Identification"`                 |
| `SCHEDULE_DESCRIPTION_COL`| Column name in Courses CSV file for schedule description                                                                                           | `"Schedule Description"`                  |
| `SECTION_COL`              | Column name in Courses CSV file for section                                                                                                       | `"Section"`                               |
| `INSTRUCTOR_COL`           | Column name in Courses CSV file for primary instructor name                                                                                       | `"Primary Instructor Name"`               |
| `TITLE_COL`                | Column name in Courses CSV file for course title                                                                                                  | `"Course Title"`                          |
| `GRADABLE_COL`             | Column name in Courses CSV file indicating whether the course is gradable                                                                         | `"Gradable Ind"`                          |
| `SUBJECT_COL`              | Column name in Courses CSV file for subject                                                                                                       | `"Subject"`                               |
| `COURSE_NUMBER_COL`        | Column name in Courses CSV file for course number                                                                                                 | `"Course Number"`                         |

### Manually editing the database.
Administrator can manually look inside the database by accessing `\admin`. The login username is `debug_admin` and the password is `inspectDB`. The user can look at each database entry and edit them if needed.


## Core Technologies used
### Django
- This web application uses Django framework.
- The web application made with Django consists of three major parts: Model, View, and Template. Model represents data entities, which Python code can interact with it to retrieve and update data from the database. View handles HTTP requests, processes data, and returns HTTP response containing the web page. Template is a HTML file with additional Django syntax, which is used when generating a web page.
- When you access a web page, View handles your HTTP request, retrieves and perhaps updates the data using Model, renders information onto HTML file using Template, and returns the HTTP response.
- Install Django from https://docs.djangoproject.com/en/5.0/intro/install/
- If you do not have experience in Django, I recommend this official tutorial: https://docs.djangoproject.com/en/5.0/intro/tutorial01/.

### Other Backend technologies
**SCIP Optimizer**
- Used to optimize the Final exam schedule using the Mixed-Integer Programming.
- When using Conda, run `conda install --channel conda-forge pyscipopt` to install SCIP
- https://pypi.org/project/PySCIPOpt/ for more information on installation

**Pandas and Numpy**
- Used to read excel files that contains student enrollment data and course schedule data.
- Install those using `pip install pandas` and `pip install numpy`.

### Other Backend technologies
**JavaScript and jQuery**
- JavaScript and jQuery, a lightweight JavaScript library, are used in the frontend.
- It is essential to the schedule analyzer dashboard, as JavaScript and jQuery can exchange data with the backend and update the user interface without refreshing the page (this is called AJAX).

**Dragula**
- It is a JavaScript library that enables drag and drop, used in the schedule analyzer dashboard.
- More information can be found here: https://bevacqua.github.io/dragula/.

**Bootstrap**
- It is a JavaScript plugin that allows us to easily develop user interface such as [navigation bars](https://getbootstrap.com/docs/5.3/components/navbar/) and [form elements](https://getbootstrap.com/docs/5.3/forms/form-control/).
- More information can be found at https://getbootstrap.com/.

## Requirements
You do not need to install anything for jQuery, JavaScript, Dragula, and Bootstrap.
### PySCIPopt 5.0.1
- Directions to install at https://pypi.org/project/PySCIPOpt/

### Python 3.12.3 
Install the following libraries using `pip install -r python_requirements.txt`.
- asgiref==3.8.1
- django==5.0.6
- et_xmlfile==1.1.0
- fonttools==4.51.0
- kiwisolver==1.4.4
- numpy==1.26.4
- openpyxl==3.1.2
- packaging==23.2
- pandas==2.2.2
- pip==24.0
- ply==3.11
- pyparsing==3.0.9
- pyqt5-sip==12.13.0
- pyscipopt==5.0.1
- python-dateutil==2.9.0.post0
- pytz==2024.1
- setuptools==69.5.1
- six==1.16.0
- sqlparse==0.5.0
- tornado==6.3.3
- tzdata==2024.1
- unicodedata2==15.1.0
- wheel==0.43.0

Pyscipopt might need to be installed seperately with pip if it causes errors.

### Django Framework
- Install Django from https://docs.djangoproject.com/en/5.0/intro/install/

## Core Files
### `manage.py`
- Run server: `python manage.py runserver`
- Made changes to the Model: `python manage.py makemigrations`, then `python manage.py migrate`. 

### `ExamScheduling/`
- `settings.py`: Contains Django setting parameters.
- `urls.py`: Defines which function handles which URL patterns.

### `optimizer/`
- `admin.py`: Defines which Model to view in the admin webpage (https://localhost:8000/admin/). The credential is username: `admin`, password: `exam_reg`.
- `forms.py`: Defines forms used in this application, including the number and types of fields.
- `models.py`: Defines Models used in this application. Models can be used to retrieve and update data in the database without writing SQL queries.
- `urls.py`: Extension of `/ExamScheduling/urls.py`.

### `optimizer/views/`
This directory contains the Views.
- `analyze.py`: Handles the web page that allows users to edit and analyze the schedule.
- `create_preference_profile.py`: Handles creating a new preference profile and saving it.
- `dashboard.py`: Handles a dashboard that displays the list of generated schedules.
- `load.py`: Loads the excel file containing enrollment data at the beginning of the optimization.
- `optimize.py`: Handles the optimization page that sets initial constraints, conducts phase 1 and 2 optimization, and analyze the results.
- `schedule_data.py`: Exports or imports schedules in json file.
- `settings.py`: Handles the Course Group setting page. Don't mix it up with `/ExamScheduling/settings.py`.

### `optimizer/internal/`
This directory contains the backend programs, including the optimizaiton programs.
- `analyze.py`: Analyzes inconviniences in a given final exam schedule.
- `read_data.py`: Reads relevant enrollment data from the database, which will be used to a schedule optimization.
- `multiprocess_workers.py`: Contains functions meant to be called from optimize.py that use mutltiprocessing during optimization
- `create_model.py`: Creates Mixed-Integer Programming model using data processed by `read_data.py`.
- `optimize.py`: Optimizes a schedule using an MIP model created by `create_model.py`.
- `schedule.py`: Serves as a interface to edit and save an exam schedule. 

### `optimizer/templates/`
This directory contains Templates.
- `base.html`: Base Template loaded in every HTML page.
- `analyzer_copy.html`: Webpage allowing users to modify schedules using drag-and-drop and analyze it.
- `choose_semester.html`: Course Group Setting page that lets user to select a semester.
- `create_preference_profile.html`: Allows user to create a preference profile to use during optimization
- `dashboard.html`: Dashboard that displays the list of generated schedules.
- `load.html`: Parse an excel file to load data for a new semester.
- `optimize.html`: Interface for the schedule optimization.
- `overlap_matrix.html`: Displays a table showing overlapping enrollment between the course groups for a given semester
- `portfolio_summary.html`: Display a summary page to view a portfolio, which is several schedules created together, at once for easy comparison
- `preference_profile_list.html`: List and description of all preference profiles that exist
- `settings.html`: Course Group Setting page.

### `optimizer/templatetags/`
Defines custom Django HTML template tags.

### `optimizer/static/optimizer`
Static files (CSS and JavaScript files) loaded by HTML

### `optimizer/uploads`
Contains .csv files with information needed for semester objects in the database.

### `optimizer/temp`
Temporary directory used during the schedule optimization process. It stores the optimization results generated by different threads, from which the main thread chooses the best result in the end. The contents will not be deleted automatically, but they can be deleted if necessary once the optimization is complete.