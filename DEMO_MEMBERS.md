# Fictional demo members

Run from the FitSync folder on macOS:

```bash
source venv/bin/activate
python manage.py seed_demo_members --password 'YOUR_LOCAL_DEMO_PASSWORD'
```

The local demonstration creates 10 fictional members, active all-access memberships,
10 coach assignments, 20 workout plans, 60 completed workouts with individual set
records, 70 weight records, 70 water records, six upcoming classes and 20 bookings.
No payments, emails, SMS or push messages are sent or created.

| Email | Fictional member | Assigned coach |
| --- | --- | --- |
| rachel_green_m@fitsync.com | Rachel Green | Chris Bumstead |
| monica_geller_m@fitsync.com | Monica Geller | Sarah Safforti |
| phoebe_buffay_m@fitsync.com | Phoebe Buffay | Chris Heria |
| joey_tribbiani_m@fitsync.com | Joey Tribbiani | Emily Watson |
| chandler_bing_m@fitsync.com | Chandler Bing | Sam Sulek |
| ross_geller_m@fitsync.com | Ross Geller | Chloe Ting |
| gunther_m@fitsync.com | Gunther | Chris Bumstead |
| janice_hosenstein_m@fitsync.com | Janice Hosenstein | Sarah Safforti |
| mike_hannigan_m@fitsync.com | Mike Hannigan | Chris Heria |
| carol_willick_m@fitsync.com | Carol Willick | Emily Watson |

Usernames match the email handles (for example, `rachel_green_m`). `_m` identifies a
member. To rename an existing older demo dataset without reseeding anything:

```bash
python manage.py rename_demo_members
```

Both commands recognise the old numbered accounts and rename the existing rows,
preserving their IDs, passwords, assignments, workouts, progress and bookings.
They also recognise the older `@fitsync.local` member addresses. The rename command
changes existing Our Team accounts to `@fitsync.com` without creating coaches.

Sign in with the email and the initial password supplied to the command. Existing
passwords and edited records are preserved when rerunning. The command also creates
missing Our Team accounts and service choices. It does not alter Lionel Messi's data.

Dates remain anchored to the first demo member's creation date, so rerunning does not
produce duplicate history or move existing bookings. These classes are initially
scheduled two to seven days ahead; after they pass, create fresh classes normally.
Cancelled/completed demo classes are never silently reopened.

Workout duration and calories are intentionally unmeasured, matching set-by-set
logging. Weight changes and workouts populate the Progress page without inventing
measured calorie data. This shared-password dataset is for local testing only.
