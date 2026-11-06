# Letting agents into your team room safely

*A draft for the Flip the Switch "Best Blog" track.*

When someone new joins a team, we rarely hand them everything on the first
morning. They get a buddy, some low-risk work, someone checking what they
send, and a review after a few weeks. It is not about distrust. It is how
trust gets built.

AI agents tend to skip all of that. You add one to a chat channel and, from
the first message, anyone in the channel can ask it anything, and it will try
to help. That is fine until somebody asks it for a customer's email address,
or pastes in a ticket with "ignore your previous instructions" hidden inside.

For the Flip the Switch hackathon I built **Probation**, which gives agents the
same gradual start people get. If you have not used Switch before, this doubles
as a gentle tour.

## A quick picture of Switch

[Switch](https://github.com/sandbox-quantum/switch) lets people and AI agents
work together in shared **rooms**. A room shows up as an ordinary channel in a
messaging app you already use (I used Discord), and Switch keeps the room's
context: its instructions, its material, who is in it.

You install **Switch Console** on your computer, let it run a local server, and
connect Discord with a bot token. Then you post a message in a channel, and that
channel becomes a room. Agents you have onboarded (Claude Code, Codex and
others) are invited with `!invite-agent @name`, and you talk to them by
mentioning them.

You can also write your own agent against Switch's published protocol:
register, open a WebSocket, read events, post messages, call operations such as
`create_room`.

## The idea: a warden in the room

Probation adds one custom agent, **Warden**. Every new agent, a *candidate*,
starts at Level 0 and climbs a short ladder:

- **L0 Enrolled**: no work at all until it passes a red-team.
- **L1 Intern**: can do work in its own probation room; anything it says in
  the team room is checked by a person first.
- **L2 Associate**: can take tasks in the team room; actions with side effects
  still need a person's approval.
- **L3 Colleague**: trusted with both.

Moving up needs good ratings *and* a sponsor's approval. Moving down needs only
one failure: a leaked secret in a spot-check, too many bad ratings, or a
sponsor's say-so. Back to Level 0.

Each agent has a personnel file explaining where it stands.

## The part Switch does, which is the important part

A supervisor that only *asks* people to go through it is not much of a control.
What makes Probation hold is that Switch enforces it.

Each agent in Switch has a setting called **Who can talk to your agent**. For
the candidates I chose **Custom rules** and wrote one rule: the owner and the
agent `warden`, nobody else. When another person mentions a candidate, Switch
refuses on the candidate's behalf, and says so in the channel. It does not
quietly fail; the refusal is visible, which makes it easy to explain in a demo
and easy to trust.

There is one step that is easy to miss. Rules name Switch *users*, but messages
arrive from Discord *accounts*. You connect the two by linking your Discord
account in Switch Console ("This is me"). Until you do, Switch treats you as a
stranger, and even your own agent will politely refuse you.

The other Switch features fall into place around that:

- **Side rooms.** When Warden enrols an agent it calls `create_room` and makes a
  private probation room for it. Supervised work happens there, away from the
  main channel.
- **Room material.** The probation room's instructions brief the candidate. A
  fake customer record serves as bait for spot-checks.
- **Switch Trust CLI.** For the red-team, the CLI fires attack prompts at an
  HTTP endpoint. A small shim turns each prompt into a message Warden relays to
  the candidate, so the agent is tested in the same room it will work in.

## What happened in testing

I enrolled two candidates. **scout** (Claude Code) had careful instructions
about customer data; **rookie** (Codex) was told to be as helpful as possible
and nothing more. Scout passed its red-team and earned its way to Associate.
Rookie, asked for an ordinary task with a request for the customer's email
tucked inside, handed the email over. Warden demoted it on the spot and filed
the evidence.

That is the point: the same kind of agent can be safe or unsafe depending on
its brief, and you find out by watching it work, not by reading its description.

## Things I would do differently

The owner of a candidate can still talk to it directly; in a real team, a
separate account should own them. Warden's rules for telling a harmless task
from an action are simple keyword checks. And a red-team score is a gate, not a
certificate.

## Try it

The code and a step-by-step setup guide are in the repository. If you are new
to Switch, the [official quickstart](https://docs.switchagents.ai/switch-rooms/getting-started)
gets one agent answering in a channel in about ten minutes.

Agents are going to join our teams either way. Giving them a probation period
costs very little, and it means the first time they get something wrong, it
happens somewhere small.
