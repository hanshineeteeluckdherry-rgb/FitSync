# FitSync

FitSync is a gym management web application built with Django. It allows members
to manage their memberships, book classes, record workouts and track their
progress. Coaches, staff and administrators have separate dashboards for their
tasks.

This version uses one custom Django app, called `gym`. The `fitsync` folder
contains the project settings and the single URL configuration.

## Main features

- Member registration, login, password reset and profile management.
- Membership packages, renewals, simulated payments and payment receipts.
- Class and service schedules, bookings and cancellations.
- An exercise library, personal workout plans and coach-assigned plans.
- Set-by-set workout recording with separate repetitions and weights.
- Automatically recorded workout duration, workout history and weight progress.
- Daily water intake records.
- Coach assignments and access to assigned members' plans and progress.
- Staff attendance recording, QR code entry and gym occupancy.
- Administrative account, membership, service, notice and report management.
- Database-backed team profiles, contact details and contact enquiries.

Outdoor activity summaries can be recorded on the website. Live GPS recording
is planned for the mobile application and is not implemented here.

## Software needed

- Python 3.13, which was used to test this version.
- pip, normally included with Python.
- A web browser.

The Python packages and their versions are listed in `requirements.txt`.
SQLite is used for the database, so a separate database server is not needed.


### Main files and folders

| `manage.py` | Runs Django commands, such as starting the server and applying migrations. |
| `requirements.txt` | Lists the Python packages needed to run the application. |
| `fitsync/settings.py` | Contains database, template, static file, email and other project settings. |
| `fitsync/urls.py` | Contains all project routes. There is no separate `gym/urls.py`. |
| `gym/models.py` | Defines all database models. |
| `gym/views.py` | Handles requests, processes actions and selects templates. |
| `gym/forms.py` | Defines forms and validates submitted information. |
| `gym/admin.py` | Registers models with Django's built-in admin site. |
| `gym/permissions.py` | Restricts pages and actions to authorised roles. |
| `gym/context_processors.py` | Provides notification menu information to templates. |
| `gym/tests.py` | Contains automated tests. |
| `gym/migrations/` | Records changes to the database structure. |
| `gym/management/commands/` | Contains optional demo-data and database-transfer commands. |
| `gym/seed_data/` | Holds starting data for the public team page. |
| `templates/` | Holds the HTML pages, arranged by role. |
| `templates/includes/` | Holds reusable page sections, such as the navbar and sidebar. |
| `templates/shared/` | Holds pages used by more than one role, including the exercise library. |
| `static/` | Holds the project's CSS, JavaScript and supplied images. |
| `media/` | Holds uploaded files, such as profile pictures and progress photos. |
| `db.sqlite3` | Stores application records. |


## Starting information

The team profiles and gym contact details are added automatically when you run:

```bash
./venv/bin/python manage.py migrate
```

You do not need to run `seed_public_content` during setup. The migration adds
missing information without replacing your edits or creating login accounts.
Administrators can edit the information through the FitSync dashboard.

Demo accounts, exercises, workouts and bookings still use the optional seed
commands. The public-content seed remains available if you later want to restore
missing starting content manually.

## Roles and access

- **Members:** manage their own profile, memberships, bookings and training records.
- **Coaches:** manage assigned members' training and sessions they teach.
- **Staff:** handle attendance, member searches, sessions and bookings.
- **Administrators:** manage accounts, packages, services, notices, public content
  and operational records through the FitSync admin dashboard.



## Current limitations

- Payments are simulated; no real payment gateway is connected.
- Email uses Django's console backend by default. Messages are printed in the
  terminal, not delivered to an inbox. Setting a recipient alone does not enable delivery.
- Contact enquiries are saved even if notification email fails. Changing an
  enquiry's status does not send an email reply.
- Calorie figures still use the existing shortcut of 7 kcal per recorded workout
  minute. These are rough estimates, not measured or personalised values. Some
  homepage calculations treat missing duration as zero. The calculation needs
  further review before being presented as accurate.
- GPS route recording, pause and resume belong to the planned mobile phase.
- Team biographies and demo accounts are sample content.
- Session validation has further edge cases to review.
- Development settings, including `DEBUG=True`, must be reviewed before deployment.

## Demo Data Commands
python manage.py seed_users
python manage.py seed_team --password 'FitSync123!'
python manage.py seed_exercises
python manage.py seed_bookings --services-only
python manage.py seed_demo_members --password 'FitSync123!' 