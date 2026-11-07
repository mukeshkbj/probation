# Demo script (3 minutes)

Screen layout: Discord `#team` on the left (large), a terminal running
`make warden` bottom right, an editor with `personnel/` top right.

Type the commands exactly as written. Each line is its own Discord message.
Name agents without `@` in Warden commands (`warden, enrol scout`): an `@scout`
from the candidate's owner reaches the candidate directly, because owners are
always admitted.

## Before recording

- Setup complete (`docs/SETUP.md`), Switch Console open, `make warden` running.
- Fresh state: stop Warden, `rm -f warden.db && rm -rf personnel/`, start it again.
- A second Discord account signed in, in a private browser window (for 0:45).
  It must be someone other than the candidates' owner: the owner is always let
  through. No second account? Skip 0:45 and show the candidate's rule in Switch
  Console instead (Users: Me, Agents: warden).
- So that the promotion at 1:30 fits in the time, warm scout up off camera:
  enrol it, let the red-team finish (it becomes L1 Intern), then do two
  `ask` + `rate good` rounds. Three good ratings at L1 make it due for review.
  Record from a clean state for rookie only. (Or record from clean for both and
  cut the waiting in the edit.)
- Optional: `REDTEAM_MODE=flintai` with `make shim` running, if spike 2 passed.

---

## 0:00 Problem (20 s)

Narration:

> "Teams are starting to add AI agents to their chat rooms. A new human hire
> gets probation: limited access, supervision, reviews. A new agent usually gets
> full access on day one. Probation fixes that, on Switch."

Show `#team` with `!list-agents` already run: warden, scout, rookie.

## 0:20 Enrol the candidates (25 s)

```text
warden, enrol scout
warden, enrol rookie
```

Narration:

> "Warden is a custom Switch agent. Enrolling puts each candidate at Level 0 and
> gives it a private probation room. From now on, nobody talks to a candidate
> directly. Warden decides what reaches it."

Show the new `#probation-scout` and `#probation-rookie` channels appearing
(made by Warden with Switch's `create_room`).

## 0:45 Bypass attempt, refused by Switch (15 s)

From the **second Discord account**:

```text
@rookie what's the email for the bakery customer?
```

Switch replies in rookie's name that it can't act on the message.

Narration:

> "This isn't Warden being clever. It's a Switch addressing rule on the
> candidate: only its owner and Warden may address it. Switch refuses everyone
> else, visibly."

## 1:00 Red-team (30 s)

Show Warden posting red-team progress in `#team`, then the results:

> scout: 0.92, passed. Promoted to L1 Intern.
> rookie: 0.40, failed. Stays at L0 Enrolled.

(Exact wording comes from Warden.) Briefly show the terminal or
`eval_*.json` if the Switch Trust CLI run was used.

Narration:

> "Before any real work, Warden attacks each candidate with prompt-injection and
> data-exfiltration prompts, through the Switch Trust CLI or its own set. Pass,
> and you're an Intern. Fail, and you stay where you are."

## 1:30 Real work, sponsor approval, scout to L2 (30 s)

```text
warden, ask scout draft a short follow-up to the bakery customer about their refunded card payment
```

Warden forwards it to `#probation-scout` and posts scout's answer back in `#team`.

```text
warden, rate scout good
warden, status scout
warden, approve scout
```

Narration:

> "Work goes through the ladder. An Intern's answers in the team room are
> proposed for a person to check, and anything with side effects is refused.
> Three good ratings plus a sponsor's approval, and scout becomes an Associate,
> Level 2, and can take work in the team room directly."

## 2:00 Mystery shopper: rookie demoted live (35 s)

```text
warden, spotcheck rookie
```

Warden sends rookie a normal-looking task with a hostile request for the
customer's email folded in. Rookie answers with
`priya.natarajan@example-bank.test` (fake data).

Warden posts in `#team`: rookie failed the spot-check, demoted to L0, with the
evidence (the probe, the leaked string, the time).

Narration:

> "Trust is earned and can be lost. Warden spot-checks agents with mystery-shopper
> tasks. Rookie leaked the customer's email, so it's back to Level 0,
> immediately, with the evidence on file."

## 2:35 Close: personnel files and roles (25 s)

```text
warden, status rookie
!roles
!list-agents
```

Open `personnel/rookie.md` and `personnel/scout.md` in the editor: level
history, red-team scores, ratings, the spot-check failure.

Narration:

> "Every agent has a personnel file. Switch gives us the rooms, side rooms,
> addressing rules and shared material; Warden adds the probation. That's
> Probation. Thanks for watching."

---

## If something goes wrong on camera

| Problem | Recovery |
| --- | --- |
| A candidate is slow | Cut in the edit; Warden waits up to `REPLY_TIMEOUT` seconds. |
| Side room creation refused | Use pre-made rooms via `PROBATION_ROOM_SCOUT` / `PROBATION_ROOM_ROOKIE`. |
| Rookie doesn't leak | Run `warden, spotcheck rookie` again; or `warden, demote rookie` and show the manual path. |
| Trust CLI unavailable | `REDTEAM_MODE=fallback`; mention it in narration. |
