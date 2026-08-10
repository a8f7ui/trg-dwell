# Putting the server online

A guided walkthrough for somebody who has never hosted anything before.

Allow about **45 minutes** the first time. Nothing here costs money.

---

## What this step is, in plain language

At the moment, the app on a phone is told to send its data to `localhost`, which
means "this same machine". That works when you are testing on a laptop and
nothing else.

Once the app is on somebody's phone, "this same machine" is *their phone*, and
there is no server there. So the phones need a real address on the internet to
send to — something like `https://yourname.pythonanywhere.com` — and that
address needs a computer behind it, running all the time, holding the database.

Renting that computer is what "hosting" means. You do not need to own or
configure a machine; you rent a slice of somebody else's and they keep it
running.

**What has to be true when you finish:**

- There is a web address that works from anywhere.
- It uses `https://`, not `http://`. Participant tokens and your own password
  travel over that connection, and `http://` would send them in the clear.
- The data survives restarts.
- You have an instructor login that is *not* the published demo one.

---

## Which host, and why

**Use [PythonAnywhere](https://www.pythonanywhere.com), free "Beginner" plan.**

It is the right answer here for four specific reasons:

| What matters | Why PythonAnywhere |
|---|---|
| The data must survive | Free accounts get 512 MB of **permanent** disk. A week-long course with 30 people uses a few megabytes. |
| It must not fall asleep | Free web apps stay up. Their daily CPU limit applies to consoles and scheduled tasks, **not to web apps**. |
| No credit card | Genuinely free to sign up. Nothing to cancel later. |
| No code changes | The database is a single SQLite file, which works because the disk is permanent. |

**What I considered and rejected:**

- **Render's free tier** — the disk is wiped on every restart and redeploy, so
  a week of participant data would vanish without warning. Making it safe means
  adding a separate PostgreSQL database and rewriting the storage layer. More
  moving parts, for no benefit at this size.
- **Fly.io** — no longer offers a free tier to new accounts; it now requires a
  credit card and bills per usage.
- **A virtual server** (DigitalOcean, Hetzner, and similar) — around $5/month
  and completely reliable, but you become responsible for operating-system
  updates, firewalls and HTTPS certificates. Reach for this only if your
  institution already has someone who does that.

**The honest limitations of the free plan:** one worker process (fine for 30
phones sending small batches), 512 MB of disk, and free accounts must click a
"renew" button every three months or the site pauses. For a week-long course,
none of these will bite.

---

## Step 1 — Create the account

1. Go to <https://www.pythonanywhere.com>.
2. Click **Pricing & signup**, then **Create a Beginner account** (the free one).
   Do not enter card details; the free plan does not ask for them.
3. Pick a username carefully — **it becomes part of your web address**, as
   `https://YOURNAME.pythonanywhere.com`, and participants will see it. Something
   like `privacycourse` reads better than `dave1987`.
4. Confirm your email address.

---

## Step 2 — Get the code onto the server

1. From the dashboard, open the **Consoles** tab and click **Bash**. A black
   terminal window opens. This is a real command line on your server.
2. Type each of these and press Enter after each one. Replace the repository
   address with your own if it differs.

```bash
git clone https://github.com/a8f7ui/m260921.git
cd m260921
```

3. Now create an isolated Python environment and install what the server needs:

```bash
mkvirtualenv --python=/usr/bin/python3.11 wypk
pip install -r requirements.txt
```

This takes a couple of minutes. Lines scrolling past are normal. When it
finishes you should see your prompt again with `(wypk)` at the start.

4. Make a folder for the database, kept **outside** the code folder so that
   updating the code can never disturb participant data:

```bash
mkdir -p ~/wypk-data
```

---

## Step 3 — Create the web app

1. Go to the **Web** tab and click **Add a new web app**.
2. Click **Next** at the domain-name step (the free plan gives you
   `YOURNAME.pythonanywhere.com`).
3. Choose **Manual configuration** — *not* the Flask option. The Flask option
   writes its own starter app over the top of ours.
4. Choose **Python 3.11**.
5. Click **Next** to finish.

You are now on the configuration page for your web app. Three things to set:

**Source code** — set to:
```
/home/YOURNAME/m260921
```

**Virtualenv** — set to:
```
/home/YOURNAME/.virtualenvs/wypk
```

**WSGI configuration file** — click the link (it looks like
`/var/www/YOURNAME_pythonanywhere_com_wsgi.py`). An editor opens. **Delete
everything in it** and paste this, replacing `YOURNAME` in all three places:

```python
import os
import sys

path = '/home/YOURNAME/m260921'
if path not in sys.path:
    sys.path.insert(0, path)

# Where the database lives. Deliberately outside the code folder, so that
# updating the code cannot touch participant data.
os.environ['WYPK_DB'] = '/home/YOURNAME/wypk-data/course.db'

# The public address. Telling the server this is what makes it mark login
# cookies as HTTPS-only.
os.environ['WYPK_PUBLIC_URL'] = 'https://YOURNAME.pythonanywhere.com'

from wsgi import application  # noqa
```

Click **Save**.

---

## Step 4 — Force HTTPS, then start it

1. Still on the **Web** tab, scroll to **Security** and turn **Force HTTPS**
   to **Enabled**. This means anyone who types `http://` is redirected to the
   encrypted version.
2. Scroll to the top and click the big green **Reload** button.
3. Open `https://YOURNAME.pythonanywhere.com/health` in a new browser tab.

You should see:

```json
{"status": "ok"}
```

**If you see an error instead**, go back to the **Web** tab and click the
**Error log** link. The last few lines will name the problem. The two common
ones are a typo in `YOURNAME` somewhere in the WSGI file, or the virtualenv path
being wrong.

---

## Step 5 — Create your instructor login

Back in a **Bash** console:

```bash
cd ~/m260921
workon wypk
export WYPK_DB=/home/YOURNAME/wypk-data/course.db
python manage.py add-instructor yourname
```

It asks for a password twice. It will not be shown as you type — that is normal.
Use at least 10 characters; a phrase of a few unrelated words is both stronger
and easier to remember than a short mangled word.

**This password protects a map of where your participants have been. Do not
reuse one from elsewhere, and do not share it in a group chat.**

---

## Step 6 — Run the safety check

Still in the console:

```bash
python manage.py check-production
```

This checks the handful of things that are genuinely dangerous to get wrong. It
will tell you what to fix and the exact command to fix it. Two you should expect
to see on a first run:

- **The demo account still exists with its published password.** The password
  `demo-password` is written in this project's public README, so anybody who has
  read it could log in and watch your participants. Remove it:
  ```bash
  python manage.py remove-instructor instructor
  ```
- **Synthetic sample participants are still loaded** — only if you loaded the
  sample data. Clear it so invented people are not mixed in with real ones:
  ```bash
  python manage.py wipe
  ```

Run the check again until it says **No blocking problems found.**

Then reload the web app once more from the **Web** tab.

---

## Step 7 — Point the phones at it

Open `https://YOURNAME.pythonanywhere.com` in a browser and log in with the
account you just made. You should see the instructor dashboard, empty.

Each participant then needs the address. In the app: **Settings → Course
server**, type `https://YOURNAME.pythonanywhere.com`, and tap **Save and test**.
It will say whether it can reach it.

Rather than have thirty people type that, set it as the default before building
the app for distribution: in `app/src/config.ts`, change

```ts
export const DEFAULT_SERVER_URL = 'http://localhost:5000';
```

to your address. Then everyone who installs it is already pointed at the right
place.

---

## Checking it really works, end to end

From your laptop, with the project checked out:

```bash
python3 tools/contract_test.py https://YOURNAME.pythonanywhere.com
```

This performs the exact sequence a real phone performs — signs up, uploads
location points, asks for a daily summary, then withdraws and deletes itself. It
also verifies that the withdrawal genuinely worked, by confirming the deleted
participant's token stops being accepted.

It creates a throwaway participant and removes it, so it is safe to run against
the live server. Expect `31 passed, 0 failed`.

---

## During the course

- **Watch the disk.** The **Files** tab shows usage. A week with 30 participants
  is a few megabytes against 512 MB.
- **Updating the code**: in a Bash console, `cd ~/m260921 && git pull`, then
  **Reload** on the Web tab. Participant data is untouched, because it lives in
  `~/wypk-data`.
- **If something breaks mid-course**, the **Error log** on the Web tab is the
  first place to look. Phones queue their points locally and retry, so a server
  outage of an hour or two loses nothing.

---

## Afterwards — taking it down

This matters. You told participants their data would be deleted at the end.

1. In the dashboard: **Data & teardown → Wipe everything**, type
   `DELETE ALL DATA`, confirm.
2. Then remove the database file itself, in a Bash console:
   ```bash
   rm ~/wypk-data/course.db
   ```
3. On the **Web** tab, **Delete** the web app if you do not intend to run the
   course again.

Step 1 empties the tables; step 2 removes the file that held them. Doing both is
the honest version of the promise you made on the consent screen.

---

## If you would rather not host it at all

There is a legitimate alternative: **run the course entirely on the sample
data**. The dashboard, the reveals and every teaching point work against the
synthetic participants, and no real person's location is ever collected.

You lose the moment where somebody sees *their own* day on the screen, which is
the most powerful part of the week. But if your institution's approval process
is going to take longer than you have, running on sample data this time is far
better than rushing the consent and data-protection work.
