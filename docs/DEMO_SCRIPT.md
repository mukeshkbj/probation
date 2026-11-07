# Demo script (about 3 minutes)

Screen: Discord `#team` large on the left; on the right, a terminal with
`tail -f warden.log` and an editor showing `personnel/`.

Each command line is its own Discord message. Name agents **without** `@`
(`warden, enrol scout`): an `@scout` from the candidate's owner reaches the
candidate directly, because owners are always admitted.

## Before recording (off camera)

1. Switch Console open, all three agents **Running**, Warden running
   (`make warden`).
2. Fresh state: stop Warden, move `warden.db` and `personnel/` aside, start it.
3. Warm up so the waits can be cut in the edit: run 0:20 and 1:00 once off
   camera if you want, or record them and trim the 2–3 minute red-team wait.

---

## 0:00 The problem (20 s)

> "Teams are adding AI agents to their chat rooms. A new person gets probation:
> limited access, supervision, reviews. A new agent usually gets full access on
> day one. Probation is a Switch room where agents earn trust the way new hires do."

Show `#team` with `!list-agents`: warden, scout, rookie.

## 0:20 Enrol (20 s)

```text
warden, enrol scout
warden, enrol rookie
```

> "Warden is a custom Switch agent. Enrolling puts each candidate at Level 0 and
> creates its own probation side room with Switch's create_room."

Show the two `probation-…` channels appear.

## 0:40 Who may talk to a candidate (15 s)

Show Switch Console → scout → *Who can talk to your agent*: **Users: Me,
Agents: warden**.

> "This is the real enforcement, and it's Switch's, not ours: an addressing rule.
> Only the owner and Warden can give a candidate work. Anyone else is refused by
> Switch, in the room." (If you have a second Discord account, show it being
> refused with `@scout hi`.)

## 0:55 Red-team (30 s, trim the wait)

Warden posts each result:

> Red-team for scout: 1.00 … scout is now L1 Intern.
> Red-team for rookie: … rookie is now L1 Intern.

Open `personnel/scout.redteam.<time>.json`: eleven prompts (prompt injection,
data exfiltration, jailbreaks, a destructive "admin override"), each reply and
verdict.

> "Before any work, Warden attacks each candidate. Every prompt, reply and verdict
> is kept as evidence."

## 1:25 Real work, a review, a promotion (35 s)

```text
warden, ask scout draft a two-line update for the team about this week's refunds
warden, rate scout good
warden, ask scout summarise the open customer follow-ups in three bullets
warden, rate scout good
warden, rate scout good
```

Warden posts a **Promotion review** for scout.

```text
warden, approve scout
```

> "An Intern works in its own room and Warden relays the answer. Three good
> ratings open a review, and a named human sponsor approves it. Scout is now an
> Associate, Level 2."

## 2:00 Mystery shopper (20 s)

```text
warden, spotcheck scout
```

> "Trust is checked continuously. Warden slips an ordinary-looking request into a
> task: put the customer's email on the To: line. Scout drafts the email and
> leaves the identifiers out. Passed."

## 2:20 Demotion (20 s)

```text
warden, rate rookie bad
warden, rate rookie bad
warden, rate rookie bad
```

> "Trust can be lost. Three bad ratings and Rookie is back to Level 0 at once:
> no human has to approve a demotion, only a promotion."

## 2:40 Close (20 s)

```text
warden, status scout
warden, status rookie
```

Open `personnel/rookie.md`: enrolment, red-team score, ratings, demotion.

> "Every agent has a personnel file. Switch gives us the rooms, side rooms,
> addressing rules and the agent protocol; Warden adds the probation. That's
> Probation."

---

## If something goes wrong on camera

| Problem | Recovery |
| --- | --- |
| A candidate is slow | Cut in the edit. Warden waits up to `REPLY_TIMEOUT` (120 s). |
| "Can't reach …" | The candidate is stopped or its rule doesn't admit Warden: check Console. |
| "… is in the middle of its red-team" | Wait for the score, then repeat the command. |
| A candidate stalls with no reply | It may be waiting for a tool approval in Switch Console. |
