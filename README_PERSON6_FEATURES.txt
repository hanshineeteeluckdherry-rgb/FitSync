PERSON 6 — FITSYNC FEATURES PAGE
================================

Recommended branch
------------------

feature/features-page


What this package adds
----------------------

This package adds the public FitSync Features page from the supplied Figma
frame. It uses the project's existing base template, shared navbar, shared
footer, original FitSync logo, Inter font, Bootstrap setup, authentication
controls, and light/dark theme system.

The page URL is:

http://127.0.0.1:8000/features/

No database migrations are required.


Files included
--------------

MODIFIED FILES

1. core/views.py
   - Adds the simple public features view.
   - Preserves the existing home view.

2. core/urls.py
   - Adds the named /features/ route as core:features.
   - Preserves all existing URL patterns.

3. templates/includes/navbar.html
   - Connects the shared Features link to core:features.
   - Shows the existing active-page style on the Features page.
   - Connects the existing Our Team and Contact items to their current routes.
   - Does not replace the navbar, logo, theme toggle, or authentication logic.

4. templates/includes/footer.html
   - Connects the existing Features, Bookings, About Us, Our Team, and Contact
     footer links to the current Django routes.
   - Does not redesign or replace the shared footer.

NEW FILES

5. templates/core/features.html
   - Contains the Features page content and five Figma-based feature cards.
   - Extends the existing base.html; it does not duplicate the document,
     navbar, footer, Bootstrap, or global scripts.

6. static/css/features.css
   - Adds only page-specific responsive Features styles.
   - Supports the existing light and dark themes.

7. static/img/features/gym-management.svg
8. static/img/features/workout-tracking.svg
9. static/img/features/coach-support.svg
10. static/img/features/progress-tracking.svg
11. static/img/features/analytics-insights.svg
    - These are the five page-specific icons from the supplied Figma design.
    - The package does not contain or replace the FitSync logo.

12. README_PERSON6_FEATURES.txt
    - These copy, test, commit, and push instructions.


Exactly where to copy the package
---------------------------------

Copy the CONTENTS inside Person6_Features_Page into the root of the current
FitSync project — the same folder that contains manage.py.

Correct result:

FitSync/
├── manage.py
├── core/
│   ├── views.py
│   └── urls.py
├── templates/
│   ├── core/features.html
│   └── includes/
│       ├── navbar.html
│       └── footer.html
├── static/
│   ├── css/features.css
│   └── img/features/
│       ├── gym-management.svg
│       ├── workout-tracking.svg
│       ├── coach-support.svg
│       ├── progress-tracking.svg
│       └── analytics-insights.svg
└── README_PERSON6_FEATURES.txt

Do not put Person6_Features_Page beside manage.py as a nested folder.
Do not try to run the Person6_Features_Page folder as a command.


Exact branch and copy steps (macOS Terminal)
--------------------------------------------

1. Open Terminal and enter the CURRENT FitSync folder. Replace the example
   path below if your folder has a different name:

   cd "/Users/apple/Desktop/FitSync"

2. Confirm this is the project root:

   pwd
   ls manage.py

3. Start from the latest main branch:

   git checkout main
   git pull origin main
   git checkout -b feature/features-page

4. Unzip Person6_Features_Page.zip. Then merge the package contents into the
   current FitSync root. Replace PACKAGE_LOCATION with the folder that contains
   the unzipped Person6_Features_Page folder:

   ditto "PACKAGE_LOCATION/Person6_Features_Page" "/Users/apple/Desktop/FitSync"

   Example, if the ZIP was extracted on the Desktop:

   ditto "/Users/apple/Desktop/Person6_Features_Page" "/Users/apple/Desktop/FitSync"

   The ditto command copies and merges the files. Do not type only the package
   folder path at the prompt; that attempts to execute the directory and causes
   a "permission denied" message.


Finder copy method
------------------

1. Open the unzipped Person6_Features_Page folder.
2. Open the current FitSync folder that contains manage.py in another window.
3. Select core, templates, static, and README_PERSON6_FEATURES.txt inside the
   package.
4. Drag them into the FitSync root folder.
5. Choose Merge when macOS asks about folders, then allow the listed files to
   be replaced. Do not replace the entire FitSync project folder.


Set up and test
---------------

If the project's virtual environment is already active, keep using it.
Otherwise, from the FitSync root, activate it using the environment name used
by the project. A common command is:

   source venv/bin/activate

Run the Django checks:

   python manage.py check
   python manage.py test core

Start the website:

   python manage.py runserver

Open:

   http://127.0.0.1:8000/features/

Test all of the following:

- The page displays five feature cards.
- Features is active in the shared navbar.
- Home, About Us, Memberships, Features, Bookings, Our Team, and Contact open.
- Logged-out users see the existing Login and Get Started controls.
- Logged-in users see the existing Profile, Dashboard, and Logout controls.
- The existing theme button switches the page between light and dark mode.
- The layout has no horizontal scrollbar on desktop, tablet, or mobile.
- Images/icons load and the browser console has no JavaScript errors.

Stop the server with Control + C after testing.


Review, commit, and push
------------------------

1. Review the changes before staging:

   git status --short
   git diff --check
   git diff

2. Stage only the files belonging to this Features task. This is safer than
   staging unrelated files or local database backups:

   git add core/views.py core/urls.py
   git add templates/core/features.html
   git add templates/includes/navbar.html templates/includes/footer.html
   git add static/css/features.css static/img/features
   git add README_PERSON6_FEATURES.txt

   If git status confirms the working tree contains only this package, the
   shorter command requested by the team is also valid:

   git add .

3. Check exactly what will be committed:

   git status
   git diff --cached --check
   git diff --cached

   Do not commit db.sqlite3, db_backup.sqlite3, venv, .DS_Store, or unrelated
   work from another person.

4. Create the commit:

   git commit -m "Create Features page from Figma"

5. Push the branch:

   git push -u origin feature/features-page

6. Open the repository website and create a pull request from:

   feature/features-page -> main


Migrations
----------

No migrations are required. This feature does not change models or database
schema.
