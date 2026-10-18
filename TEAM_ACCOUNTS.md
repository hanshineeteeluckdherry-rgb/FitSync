# Local Our Team accounts

These are demonstration accounts for the people displayed on the Our Team page,
not accounts for the university project contributors.

| Person | Login email | Role |
| --- | --- | --- |
| Dwayne The Rock Johnson | dwayne.johnson@fitsync.com | Admin |
| Julie Bowen | julie.bowen@fitsync.com | Staff |
| Chris Bumstead | chris.bumstead@fitsync.com | Coach |
| Sarah Safforti | sarah.safforti@fitsync.com | Coach |
| Chris Heria | chris.heria@fitsync.com | Coach |
| Emily Watson | emily.watson@fitsync.com | Coach |
| Sam Sulek | sam.sulek@fitsync.com | Coach |
| Chloe Ting | chloe.ting@fitsync.com | Coach |

Create them from the project folder on macOS:

```bash
source venv/bin/activate
python manage.py seed_team --password 'YOUR_LOCAL_DEMO_PASSWORD'
python manage.py seed_bookings --services-only
```

The password applies only to new accounts or sample accounts without a usable
password. Existing passwords, account details and coach profiles are preserved.
Use these shared-password accounts only locally; change passwords before any
deployment. They do not grant Django superuser access.

## Coach classes

Sign in as a coach, select **Sessions**, then **Add Class**. Choose an existing
service, date, start/end times and capacity. The signed-in coach is automatically
the instructor. Only that coach's classes appear in their management list.
Coaches can edit upcoming classes, view their rosters and cancel their own classes.
Cancellation also cancels confirmed bookings and notifies the affected members.

Overlapping teaching times and past start times are rejected. Capacity cannot be
reduced below confirmed bookings. Staff/admin retain catalogue management and
access to all sessions; coaches cannot change the shared service catalogue.
The catalogue-only seed creates missing service choices, not scheduled classes.
