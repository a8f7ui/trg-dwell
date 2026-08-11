# Deployment redesign: the plan

Written against `docs/DEPLOYMENT_AUDIT.md`. The goal is to **remove** technical
work, not to explain it better.

## The test this design must pass

A person who does not know what Python, pip, a virtual environment, Node, npm,
Expo, EAS, SQLite, WSGI, an environment variable, an API endpoint, an HTTPS
certificate or a database migration *is* must be able to reach a working course
server. They should not encounter any of those words in a place where they are
expected to act on one.

Anything that fails that test is either automated away, generated, or isolated
into a clearly-marked section of things only a human can do.

---

## What becomes automated

Done by the software, silently, with no question asked:

| Today | After |
|---|---|
| Create a virtual environment | Automatic |
| `pip install -r requirements.txt` | Automatic |
| Generate sample data | Automatic |
| Create the database, run migrations | Automatic |
| Choose a free port | Automatic |
| Work out the right bind address | Automatic |
| Generate the session secret | Automatic, and atomically (fixes H1) |
| Generate the instructor password | Automatic, strong, shown once |
| Remove the demo account | Automatic at the end of setup |
| Derive UTC offset for sample data | Automatic from the chosen timezone |
| Run the test suite | Automatic, as the last step of setup |
| Decide where the database lives | Automatic |
| Allocate participant labels | Automatic and collision-free (fixes H2) |

## What becomes configuration

One generated file, `data/local/course.json`, written by the wizard and read by
the server. **The user never opens it.** It holds: course name, city,
coordinates, timezone, public address, and a marker that setup completed.

Precedence stays sane for hosts that prefer environment variables:
`environment variable → generated file → built-in default`.

## What becomes a setup wizard

`python3 setup.py` — the single command. Twelve stages, matching the brief:

1. Check the computer, in plain English
2. Explain anything missing, with the exact fix
3. Install everything needed
4. Ask **four** questions, all answerable without technical knowledge
5. Generate the secret and the instructor password
6. Write the configuration
7. Create the database
8. Load teaching data
9. Remove the demo account
10. Run every automated test
11. State plainly whether it worked
12. Print the exact next step

### The only four questions

Chosen because each is a fact the user already knows:

1. **What is this course called?** (free text, used on screen)
2. **Which city?** (offline table of US cities; coordinates accepted; geocoding
   used only if it happens to be available)
3. **Which timezone?** (six US zones by plain name — "Central — Chicago,
   Milwaukee, Dallas". Never an identifier like `America/Chicago`.)
4. **What is your name?** (becomes the login username)

Everything else is decided or generated.

## What becomes an environment variable

Environment variables continue to exist for hosting platforms, and the **user
never sets one by hand**. `deploy.py` writes them into the generated host
files. The names stay as they are: `DWELL_DB`, `DWELL_PUBLIC_URL`,
`DWELL_SECRET_KEY`, `DWELL_BIND`, `DWELL_PORT`.

For the mobile app, the server address moves from a hand-edited TypeScript file
to `EXPO_PUBLIC_DWELL_SERVER`, written into `app/.env` by the wizard. This
eliminates blocker C4 and the only source-code edit in the whole process.

## What is eliminated

| Removed | Why |
|---|---|
| Editing `app/src/config.ts` | Replaced by a generated `app/.env` |
| Editing a WSGI file, replacing `YOURNAME` three times | `deploy.py` generates it complete |
| `manage.py add-instructor` as a required step | Wizard does it |
| `manage.py set-location` as a required step | Wizard does it |
| `manage.py check-production` as a separate step | Folded into `verify.py --production` |
| Knowing which of twelve commands to run | Three commands exist: `setup.py`, `verify.py`, `dwell.py` |
| Typing a server URL on thirty phones | Baked into the build |
| Choosing a port, a bind address, a database path | Decided automatically |

## What is generated automatically

- Session secret — 48 random bytes, created atomically so concurrent workers
  cannot disagree (fixes H1)
- Instructor password — four random words plus digits, readable aloud, shown
  once
- `data/local/course.json` — the configuration
- `app/.env` — the server address for the app build
- `deploy/wsgi_for_host.py` — a complete WSGI file with real values
- `deploy/UPLOAD_THIS.zip` — everything the host needs, nothing it does not
- `deploy/YOUR_NEXT_STEPS.txt` — the manual steps, with values filled in

## What absolutely must remain manual

These require a human to accept terms, prove identity, or pay. No software can
do them. They are isolated into one file and one screen, and everything
around them is automated.

| Step | Why it cannot be automated | Cost |
|---|---|---|
| Create a hosting account | Terms acceptance, email verification | Free |
| Upload one file to the host | Account credentials | — |
| Create an Apple Developer account | Legal identity verification | $99/year |
| Create a Google Play developer account | Legal identity verification | $25 once |
| Create an Expo account | Terms acceptance | Free |
| Approve the app store submission | Apple/Google human review | 2–7 days |
| Decide who the instructors are | A human judgement | — |

Everything downstream of each account — API tokens, project creation, build
configuration, file generation — is automated once the account exists.

---

## Resulting architecture

```
  ONE command on the instructor's computer
        │
        ▼
   setup.py  ──▶ checks, installs, asks 4 questions, generates
        │        secrets, configures, tests, reports
        ▼
   Working server on this computer  ──▶ teach the whole course from here
        │
        │  (only if the course needs real phones)
        ▼
   dwell.py deploy ──▶ generates everything the host needs
        │
        ▼
   [MANUAL] create host account, upload one file, click Reload
        │
        ▼
   dwell.py app ──▶ writes the server address into the app build
        │
        ▼
   [MANUAL] Apple / Google / Expo accounts, then one command per platform
```

**External services: one** (the host) for a laptop-taught course, **four** if
the app must reach real phones (host, Expo, Apple, Google). That is the floor —
the last three are imposed by the platforms, not by this design.

---

## Order of implementation

1. Fix the setup-path defects the wizard depends on: C1 (data destruction),
   H1 (secret race), H2 (duplicate labels). A wizard built on these is unsafe.
2. Configuration file and its precedence.
3. `setup.py`, the wizard.
4. `app/.env` generation, eliminating the source edit (C4).
5. `dwell.py`, one entry point wrapping setup / verify / deploy / app.
6. `verify.py --production`.
7. Rewrite the quick start around the wizard.

## Definition of done for this phase

- [ ] A person can go from download to working server with one command and four
      plain questions
- [ ] No password, secret, port, path or identifier is ever typed by the user
- [ ] No source file is edited by the user, ever
- [ ] The words venv, pip, WSGI, SQLite, migration and environment variable do
      not appear in anything the user is asked to act on
- [ ] The manual account steps are in exactly one place, with values pre-filled
- [ ] Setup ends by saying plainly whether it worked and what to do next
- [ ] `setup.py` cannot destroy real participant data
