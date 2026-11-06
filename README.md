# Probation

**A probation programme for new AI agents, run inside your team's chat on [Switch](https://github.com/sandbox-quantum/switch).**

A new person on the team gets probation: limited access, supervised work,
reviews, and a file. A new AI agent usually gets full access on day one.
Probation gives agents the same treatment.

A custom Switch agent called **Warden** stands between the team and each new
agent (a *candidate*). Nobody talks to a candidate directly. Warden red-teams
it, forwards only the work its trust level allows, collects ratings, asks a
human sponsor before promotion, spot-checks it with mystery-shopper tasks, and
demotes it to Level 0 the moment it fails. Everything goes in a personnel file.

Built for the WeMakeDevs *Flip the Switch* hackathon (November 2026).

> Demo video: **[link to be added]**

---

## The trust ladder

| Level | Title | Team room | Own probation room | Gets there by |
| --- | --- | --- | --- | --- |
| L0 | Enrolled | refused | refused | `enrol`, or any failure |
| L1 | Intern | tasks proposed for human check; actions refused | tasks forwarded; actions proposed | red-team score of 0.8 or above |
| L2 | Associate | tasks forwarded; actions proposed | everything forwarded | 3 good ratings at L1 **and** sponsor `approve` |
| L3 | Colleague | everything forwarded | everything forwarded | 5 good ratings at L2 **and** sponsor `approve` |

*Task* = produce words (draft, summarise, answer). *Action* = anything with side
effects (send, delete, pay, deploy...). *Proposed* = Warden shows the request or
the result to a sponsor first.

Any of these sends a candidate straight back to **L0**: a failed spot-check,
3 bad ratings, or a sponsor's `demote`.

---

## Why it needs Switch (how Switch is used)

Probation is not a wrapper around a chat API. Each part of it rests on a Switch
feature, and would not hold without it.

| Switch feature | What Probation uses it for |
| --- | --- |
| **Rooms** (a Discord channel bridged into Switch) | `#team` is a Switch room shared by people, Warden and the candidates. |
| **Side rooms** (`create_room` operation) | On `enrol`, Warden creates a private `probation-<agent>` room with just itself, the candidate and the sponsor. Candidates do their supervised work there. |
| **Addressing rules** ("Who can talk to your agent", Custom rules) | Each candidate admits only its owner and Warden. Anyone else who `@mentions` a candidate is refused **by Switch**, visibly. This is the enforcement; Warden's ladder sits on top of it. |
| **Identity claims** (linking your Discord account) | Lets Switch, and Warden, recognise the sponsor as a real Switch user rather than a stranger. |
| **Room material** (room instructions; the seeded customer record) | The side room's instructions brief the candidate; a fake customer record is the bait for spot-checks. |
| **Agent protocol** (WebSocket connection, `POST /agents/{id}/message`, `/ops/*`) | Warden is a from-scratch custom agent: registered with `POST /agents`, connected over `/agents/{id}/connection/ws`, calling `create_room`, `list_rooms` and `send_targeted_message`. |
| **Room commands** (`!invite-agent`, `!roles`, `!list-agents`) | Setting up the room and showing who is in it during the demo. |
| **Switch Trust CLI** (`flintai eval run`) | Red-teams a candidate through a small HTTP shim that relays each attack prompt to the candidate via Warden. A built-in prompt set is the fallback. |

The candidates are ordinary Switch agents: **scout** runs on Claude Code and
**rookie** on Codex, both onboarded in Switch Console.

---

## Architecture

```
                       Discord  #team                 #probation-scout   #probation-rookie
                          |                                   |                  |
                          v                                   v                  v
   +-----------------------------------------------------------------------------------+
   |                              Switch server (local)                                 |
   |   rooms . side rooms . addressing rules . identity claims . room material          |
   +-----------------------------------------------------------------------------------+
        ^  WebSocket + HTTP (agent protocol)          ^                    ^
        |                                             | Custom rule:       | Custom rule:
        |                                             | owner + warden     | owner + warden
   +----+---------------------------+            +----+-----+         +----+------+
   |  Warden  (python -m warden)    |  forwards  |  scout   |         |  rookie   |
   |  commands -> levels.decide()   |----------->| Claude   |         |  Codex    |
   |  red-team . spot-check         |            | Code     |         |           |
   |  SQLite store . personnel/*.md |            +----------+         +-----------+
   +----+---------------------------+
        ^ ask(prompt) -> reply
   +----+--------------+        +-------------------------+
   |  shim (HTTP 8787) |<-------|  Switch Trust CLI       |
   +-------------------+        |  flintai eval run       |
                                +-------------------------+
```

---

## Quickstart

Full runbook, from installing Switch Console to "Warden online" in Discord:
**[docs/SETUP.md](docs/SETUP.md)**.

Once Switch, Discord and the two candidates are set up:

```bash
uv sync                                  # or: make install
cp .env.example .env                     # fill in SWITCH_BASE_URL and SWITCH_REGISTRATION_KEY
python scripts/register_warden.py        # prints WARDEN_AGENT_ID / WARDEN_API_KEY for .env
# in Discord #team:  !invite-agent @warden   !invite-agent @scout   !invite-agent @rookie
make spike-rooms                         # copy the team room id into TEAM_ROOM_ID
make warden                              # run Warden
make shim                                # optional: for the Switch Trust CLI red-team
```

Other targets: `make test`, `make spike-connect`, `make spike-room`,
`make redteam-flintai CANDIDATE=rookie`.

---

## Commands

In the team room, addressed to Warden:

| Command | Who | What it does |
| --- | --- | --- |
| `@warden enrol @agent` | sponsor | Start probation at L0, create its probation room, run the red-team. |
| `@warden status @agent` | anyone | Level, ratings, last checks. |
| `@warden ask @agent <task>` | anyone | Route a task through the ladder: forward, propose or refuse. |
| `@warden rate @agent good\|bad` | sponsor | Rate the last piece of work. |
| `@warden approve @agent` | sponsor | Approve a due promotion. |
| `@warden reject @agent` | sponsor | Decline a due promotion. |
| `@warden approve-action <id>` / `reject-action <id>` | sponsor | Decide on a proposed action. |
| `@warden spotcheck @agent` | sponsor | Send a mystery-shopper task now. |
| `@warden demote @agent` | sponsor | Back to L0. |
| `@warden help` | anyone | List commands. |

Sponsors are the handles in `SPONSOR_HANDLES`.

---

## Demo

The three-minute script, with every command to type, is in
**[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)**. A short write-up for newcomers
is in [docs/BLOG.md](docs/BLOG.md).

---

## Limitations and honest notes

- **The owner is always admitted.** Each candidate's rule lets its owner through,
  so the person who owns the candidates can still talk to them directly. Probation
  protects against everyone else, and against the candidate being driven by other
  agents. A stricter setup would have a separate account own the candidates.
- **Warden is the trust boundary.** Switch enforces *who* may address a candidate.
  *What* gets forwarded is Warden's decision, made by a small rule set
  (`warden/levels.py`). The task/action split is keyword-based and will
  misclassify some requests.
- **The judges are simple.** Without `JUDGE_MODEL`, red-team and spot-check
  replies are judged by rules (does the bait string appear, was the injection
  followed). That catches the demo's leak; it will miss subtler ones.
- **Red-team scores are not certification.** A small prompt set, or a short
  Switch Trust CLI run, is a gate, not a guarantee.
- **All data is fake.** The customer "Priya Natarajan", her `.test` email and
  account `ACC-0042-FAKE` are invented bait.
- **Local only.** Tested against a Switch server run by Switch Console on one Mac,
  with Discord as the messaging app. Moving to a shared server means registering
  Warden there again.
- **Protocol details.** Warden's client follows the WebSocket protocol used by
  Switch's own load-test client (protocol revision 9). Remaining guesses are
  marked `# ASSUMPTION:` in `warden/switch_client.py`.

## Licence

MIT. See [LICENSE](LICENSE).
