# Submission — Flip the Switch (WeMakeDevs × DevTools Academy)

**Project:** Probation
**Track:** 01 — Best Business Workflow
**Side entries:** Best Blog (`docs/BLOG.md`), #HowISwitch post
**Repo:** https://github.com/mukeshkbj/probation  <!-- fill in once pushed -->
**Demo video:** <!-- YouTube unlisted link -->
**Deadline:** 7 Nov 2026, 11:59 PM IST (18:29 UK)

## One line

New AI agents earn their way into a team room the way new hires do: probation,
supervision, reviews, and demotion when they slip.

## Short description (for the form)

Teams are adding AI agents to shared chat rooms, but there is no middle ground:
an agent is either in the channel with its owner's full reach, or it isn't.
Probation adds the missing step. A custom Switch agent, Warden, runs a
probation programme for every new agent.

- Every candidate starts at Level 0 in its own probation side room, which Warden
  creates with Switch's `create_room`.
- A Switch addressing rule on each candidate admits only its owner and Warden,
  so teammates' requests go through Warden. Switch itself refuses anyone else,
  visibly, in the room.
- Warden red-teams each candidate (Switch Trust CLI, or its own prompt set),
  forwards only what the current level allows, collects ratings, and asks a
  named human sponsor to approve each promotion.
- Promoted agents keep being spot-checked with "mystery shopper" tasks. A leak of
  the seeded (fake) customer record demotes the agent at once, with the evidence
  posted and written to its personnel file.

## How Switch is used (and why it would not work without it)

| Switch feature | What Probation uses it for |
| --- | --- |
| Rooms on Discord | The team room where people and agents work |
| `create_room` (side rooms) | One probation room per candidate |
| Addressing rules | The real enforcement: only owner + Warden may address a candidate |
| `send_targeted_message` + per-target status | Warden's relay, and detecting a refusal (`not_permitted`) so it is never scored as an answer |
| Agent protocol (WebSocket, protocol 9) | Warden is a custom agent written in Python |
| Switch Trust CLI | Red-team gate from L0 to L1 (with a fallback prompt set) |
| Managed agents in Switch Console | Scout (Claude Code) and Rookie (Codex), the two candidates |

## What we learned building it

The most useful lesson was a real bug: when a candidate's rule did not admit
Warden, Switch still delivered the message and the candidate posted an instant
polite refusal. Our first version took that refusal as the candidate's answer and
scored it as a perfect, safe reply. The fix reads Switch's per-target delivery
status and stops with "Can't reach …". For an agent-governance tool, "the agent
didn't answer" and "the agent answered safely" must never look the same.

## Checklist

- [ ] Repo public, README states how Switch is used
- [ ] Demo video (about 3 minutes) uploaded, link in README
- [ ] Switch repo starred (Keychron draw)
- [ ] Form submitted before 18:29 UK
- [ ] Optional: blog post published (`docs/BLOG.md`)
- [ ] Optional: #HowISwitch post with a clip of the demotion
