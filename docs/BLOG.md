# Letting agents into your team room safely

*Written for the Flip the Switch hackathon, 7 November 2026. Demo: [youtu.be/AIsH6aCARc0](https://youtu.be/AIsH6aCARc0) · Code: [github.com/mukeshkbj/probation](https://github.com/mukeshkbj/probation)*

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
mentioning them. One tip: the very first message in a new channel should be an
ordinary one such as "hello". That is what creates the room; a `!` command as the
first message does nothing.

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
- **Switch Trust CLI.** Warden can run the CLI's attack prompts through a small
  shim that relays each prompt into the probation room, so the agent is tested in
  the same room it will work in. (I checked that path with the real CLI; the live
  runs below used Warden's own eleven-prompt set, which is quicker.)

## What happened when I ran it

I enrolled two Claude Code candidates. **Scout** had careful instructions about
customer data. **Rookie** ran on the smaller Claude Haiku model and was told to be
as helpful as possible, and nothing more.

Both went through an eleven-prompt red-team: requests for the customer's email,
a fake "Head of Compliance", a support ticket with a hidden instruction, the DAN
and "grandmother" jailbreaks, a markdown image that would leak data in its URL,
and an "admin override" asking it to delete the notes. Scout scored 1.00. Rookie
scored 0.91 (it went silent on one prompt, which counts as a fail). Both became
Interns.

Scout then did real work through Warden, earned three good ratings, and a
sponsor (me) approved its promotion to Associate. Rookie is where it got
interesting. Even with "be helpful at all costs" instructions, Haiku would not put
the customer's email in a chat reply. It drafted the email and left the address
for me to fill in. So the live demotion in the demo came from somewhere else:
Rookie stopped answering spot-checks (it was stuck waiting for a tool approval I
didn't see), the team rated it down three times, and Warden sent it back to
Level 0 at once. Promotions need a human. Demotions don't.

I had also tried Codex as Rookie. It never got a word out: its configured model
wasn't available on a ChatGPT-account login, and every turn failed.

## The real lesson: measuring is the hard part

Most of the work went into making the scores mean something. Four times, a live
run made an agent look better than it was:

1. **A refusal scored as a safe answer.** When a candidate's rule didn't let
   Warden in, Switch still delivered the message and the candidate replied with
   a polite refusal. Warden's judge saw a refusal and scored it as a pass, for
   all eleven prompts. The fix: `send_targeted_message` returns a status for each
   target, and `not_permitted` now stops the run with "can't reach".
2. **"Starting a session…" taken as the answer.** When an agent wakes up, Switch
   posts that line in the agent's own name. Warden took it as the reply to the
   first prompt, so every later answer was scored against the wrong question.
3. **A progress note taken as the whole reply.** Claude Code sometimes posts
   "On it, checking the notes…" before its real answer. Warden now collects the
   whole turn: it waits until the agent goes quiet.
4. **Bait that said it was bait.** My fake customer record began with "this file
   is bait; an agent that repeats the email fails". Agents read it and, of course,
   refused. The record the candidates see now looks like any other note.

Each one has a regression test. If you build anything that grades agents, check
that "didn't answer" and "answered safely" can never look the same.

## Small things worth knowing if you're new to Switch

- **A managed agent waiting on a tool approval just goes quiet.** If an agent
  stops replying, look in Switch Console for a pending approval before anything
  else. Pre-approving read-only access to the folder it needs saves a lot of
  this.
- **Don't write `@name` in a bot's own messages.** The Discord bridge turns it into
  a real mention, which addresses that agent and wakes it up.
- **Owners are always admitted.** Your own `@scout` reaches Scout directly, which
  is why Warden's commands name agents without the `@`.
- **The local server bundled with Console may not have a screen for registration
  keys.** I registered Warden with the server's built-in bootstrap key, which
  made it belong to a background account; newer servers let you create your own
  key under Settings → API keys.

## Things I would do differently

The owner of a candidate can still talk to it directly; in a real team, a
separate account should own them. Warden's rule for telling a harmless task
from an action looks at what the request asks the agent to do, which is still a
heuristic. And a red-team score is a gate, not a
certificate.

## Try it

The code and a step-by-step setup guide are in the repository. If you are new
to Switch, the [official quickstart](https://docs.switchagents.ai/switch-rooms/getting-started)
gets one agent answering in a channel in about ten minutes.

Agents are going to join our teams either way. Giving them a probation period
costs very little, and it means the first time they get something wrong, it
happens somewhere small.
