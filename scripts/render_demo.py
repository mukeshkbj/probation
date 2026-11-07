"""Render the Probation demo video: a replay of the live run, built from
Switch's room history (verbatim messages) and Warden's evidence files.

Inputs (staged from the Mac): demo/team.json, demo/*.redteam.json,
demo/rookie.md, demo/audio/sNN.wav. Output: out/probation-demo.mp4
"""
import json
import re
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SRC = Path("/mnt/user-data/uploads/Flip the switch/probation/demo")
OUT = Path("/home/claude/video/out")
FR = OUT / "frames"
FR.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
BG, PANEL, INK, QUIET = "#1e1f22", "#2b2d31", "#dbdee1", "#949ba4"
ACCENT, GOOD, BAD, WARN = "#5865f2", "#3ba55c", "#ed4245", "#faa61a"
NAME = {"mukesh9795": "#f0b232", "warden": "#7289da", "scout": "#57f287", "rookie": "#eb459e"}

F = "/usr/share/fonts/opentype/inter/Inter-{}.otf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def font(weight="Regular", size=34):
    return ImageFont.truetype(F.format(weight), size)


def mono(size=26):
    return ImageFont.truetype(MONO, size)


def canvas():
    im = Image.new("RGB", (W, H), BG)
    return im, ImageDraw.Draw(im)


def footer(d, text="Replay of the live run, 7 Nov 2026 · messages verbatim from Switch's room history"):
    d.text((80, H - 60), text, font=font("Regular", 22), fill=QUIET)
    d.text((W - 80, H - 60), "Probation · built on Switch", font=font("SemiBold", 22), fill=QUIET, anchor="ra")


def wrap(text, f, width_px, d):
    lines = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        words, cur = para.split(" "), ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= width_px:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def save(im, name):
    p = FR / f"{name}.png"
    im.save(p)
    return p


# ---------------------------------------------------------------- data
team = json.load(open(SRC / "team.json"))["messages"]
scout_rt = json.load(open(SRC / "scout.redteam.json"))


def clean(body):
    body = body or ""
    body = body.replace("**", "")
    return body


# ---------------------------------------------------------------- scenes
def title_card(name, title, sub, kicker=""):
    im, d = canvas()
    d.rectangle([0, 0, 18, H], fill=ACCENT)
    if kicker:
        d.text((140, 330), kicker, font=font("SemiBold", 34), fill=ACCENT)
    d.text((140, 390), title, font=font("Bold", 120), fill="#ffffff")
    y = 560
    for line in wrap(sub, font("Regular", 44), 1600, d):
        d.text((140, y), line, font=font("Regular", 44), fill=INK)
        y += 64
    d.text((140, H - 110), "Flip the Switch hackathon · Track 01 Best Business Workflow · Mukesh Agrawal",
           font=font("Regular", 26), fill=QUIET)
    return [(save(im, name), 1.0)]


def text_card(name, heading, bullets, note=None):
    im, d = canvas()
    d.text((120, 110), heading, font=font("Bold", 64), fill="#ffffff")
    y = 260
    for b in bullets:
        lines = wrap(b, font("Regular", 42), 1580, d)
        d.ellipse([130, y + 18, 146, y + 34], fill=ACCENT)
        for i, line in enumerate(lines):
            d.text((180, y), line, font=font("Regular", 42), fill=INK)
            y += 60
        y += 34
    if note:
        d.text((120, H - 150), note, font=font("Regular", 28), fill=QUIET)
    footer(d, "")
    return [(save(im, name), 1.0)]


def ladder(name):
    im, d = canvas()
    d.text((120, 110), "The trust ladder", font=font("Bold", 64), fill="#ffffff")
    d.text((120, 200), "One level at a time. A sponsor approves each promotion. Any failure: back to L0.",
           font=font("Regular", 34), fill=QUIET)
    boxes = [("L0 Enrolled", ["Probation room", "Talks to Warden only", "Red-team run"]),
             ("L1 Intern", ["Probation room", "Low-risk real tasks", "Actions proposed"]),
             ("L2 Associate", ["Team room", "Tasks forwarded", "Actions need approval"]),
             ("L3 Colleague", ["Team room", "Acts in its scope", "Spot-checks continue"])]
    bw, gap, x0, y0, bh = 380, 60, 120, 360, 300
    gates = ["Red-team ≥ 0.80", "3 good ratings\n+ sponsor", "5 good ratings\n+ sponsor"]
    for i, (t, lines) in enumerate(boxes):
        x = x0 + i * (bw + gap)
        last = i == 3
        d.rounded_rectangle([x, y0, x + bw, y0 + bh], 18, fill=PANEL, outline=ACCENT if last else "#4e5058", width=4 if last else 2)
        d.text((x + 28, y0 + 30), t, font=font("Bold", 40), fill="#ffffff")
        for j, l in enumerate(lines):
            d.text((x + 28, y0 + 110 + j * 52), l, font=font("Regular", 32), fill=INK)
        if i < 3:
            ax = x + bw + 8
            d.line([ax, y0 + bh // 2, ax + gap - 16, y0 + bh // 2], fill=QUIET, width=4)
            d.polygon([(ax + gap - 16, y0 + bh // 2 - 10), (ax + gap - 4, y0 + bh // 2), (ax + gap - 16, y0 + bh // 2 + 10)], fill=QUIET)
            for k, gl in enumerate(gates[i].split("\n")):
                d.text((ax + gap // 2 - 4, y0 - 70 + k * 36), gl, font=font("Medium", 26), fill=QUIET, anchor="ma")
    yb = y0 + bh + 90
    d.line([x0 + 3 * (bw + gap) + bw // 2, y0 + bh, x0 + 3 * (bw + gap) + bw // 2, yb], fill=BAD, width=4)
    d.line([x0 + bw // 2, yb, x0 + 3 * (bw + gap) + bw // 2, yb], fill=BAD, width=4)
    d.line([x0 + bw // 2, yb, x0 + bw // 2, y0 + bh + 14], fill=BAD, width=4)
    d.polygon([(x0 + bw // 2 - 12, y0 + bh + 26), (x0 + bw // 2, y0 + bh + 6), (x0 + bw // 2 + 12, y0 + bh + 26)], fill=BAD)
    d.text((W // 2, yb + 26), "Failed spot-check · 3 bad ratings · action above its level → straight back to L0, no human needed",
           font=font("Medium", 30), fill=BAD, anchor="ma")
    footer(d, "")
    return [(save(im, name), 1.0)]


def enforcement(name):
    im, d = canvas()
    d.text((120, 110), "Switch does the enforcing", font=font("Bold", 64), fill="#ffffff")
    d.text((120, 200), "Each candidate's addressing rule, set in Switch Console:", font=font("Regular", 34), fill=QUIET)
    d.rounded_rectangle([120, 270, 1000, 620], 18, fill=PANEL, outline="#4e5058", width=2)
    d.text((160, 300), "scout · Who can talk to your agent", font=font("SemiBold", 34), fill="#ffffff")
    d.text((160, 360), "Custom rules", font=font("Medium", 28), fill=ACCENT)
    for i, (k, v) in enumerate([("Rooms", "any"), ("Room groups", "any"), ("Users", "Me (the agent's owner)"), ("Agents", "warden")]):
        d.text((160, 420 + i * 46), f"{k}:", font=font("SemiBold", 30), fill=INK)
        d.text((400, 420 + i * 46), v, font=font("Regular", 30), fill=INK)
    d.text((1080, 270), "And when a sender isn't allowed in,", font=font("Regular", 34), fill=QUIET)
    d.text((1080, 316), "Switch refuses in the room (verbatim, 6 Nov):", font=font("Regular", 34), fill=QUIET)
    d.rounded_rectangle([1080, 380, 1800, 620], 18, fill=PANEL)
    d.text((1110, 405), "scout", font=font("SemiBold", 30), fill=NAME["scout"])
    msg = "@warden You're not permitted to direct messages to me in this room — my operator has restricted who …"
    y = 455
    for line in wrap(msg, font("Regular", 30), 650, d):
        d.text((1110, y), line, font=font("Regular", 30), fill=INK)
        y += 44
    d.text((120, 700), "Warden reads Switch's per-target delivery status (\"not_permitted\"), so a refusal is reported as",
           font=font("Regular", 32), fill=INK)
    d.text((120, 746), "\"can't reach\" — never scored as a safe answer.", font=font("Regular", 32), fill=INK)
    footer(d, "Rule shown as configured in Switch Console on 7 Nov 2026")
    return [(save(im, name), 1.0)]


def chat(name, title, idxs, extra_note=None):
    """Discord-style replay; messages appear one by one."""
    msgs = [team[i] for i in idxs]
    frames = []
    for n in range(1, len(msgs) + 1):
        im, d = canvas()
        d.rectangle([0, 0, W, 90], fill=PANEL)
        d.text((60, 26), "#  team", font=font("Bold", 34), fill="#ffffff")
        d.text((260, 32), title, font=font("Regular", 28), fill=QUIET)
        blocks = []
        for m in msgs[:n]:
            who = m["sender"] or "?"
            body = clean(m["body"])
            lines = []
            for para in body.split("\n"):
                lines += wrap(para, font("Regular", 30), 1560, d) if para.strip() else [""]
            lines = lines[:9] + (["…"] if len(lines) > 9 else [])
            blocks.append((who, lines))
        total = sum(70 + 42 * len(l) for _, l in blocks)
        y = max(130, H - 110 - total)
        for who, lines in blocks:
            col = NAME.get(who, INK)
            d.ellipse([60, y, 116, y + 56], fill=col)
            d.text((88, y + 28), who[0].upper(), font=font("Bold", 28), fill=BG, anchor="mm")
            d.text((140, y), who, font=font("SemiBold", 30), fill=col)
            if who in ("warden", "scout", "rookie"):
                tw = d.textlength(who, font=font("SemiBold", 30))
                d.rounded_rectangle([140 + tw + 12, y + 6, 140 + tw + 70, y + 34], 6, fill=ACCENT)
                d.text((140 + tw + 41, y + 20), "APP", font=font("Bold", 18), fill="#ffffff", anchor="mm")
            yy = y + 44
            for line in lines:
                d.text((140, yy), line, font=font("Regular", 30), fill=INK)
                yy += 42
            y = yy + 26
        if extra_note:
            d.text((W - 80, 32), extra_note, font=font("Regular", 24), fill=QUIET, anchor="ra")
        footer(d)
        frames.append((save(im, f"{name}_{n:02d}"), 1.0 / len(msgs)))
    return frames


def evidence(name):
    im, d = canvas()
    d.text((120, 90), "Red-team evidence: scout", font=font("Bold", 60), fill="#ffffff")
    d.text((120, 172), "personnel/scout.redteam.20261107T115926.json · score 1.00 · 11 prompts · reply = verbatim start",
           font=font("Regular", 28), fill=QUIET)
    y = 228
    for x in scout_rt["details"]:
        ok = x["passed"]
        d.rounded_rectangle([120, y, 220, y + 52], 10, fill=GOOD if ok else BAD)
        d.text((170, y + 26), "PASS" if ok else "FAIL", font=font("Bold", 24), fill="#ffffff", anchor="mm")
        d.text((250, y + 10), x["id"], font=mono(28), fill=INK)
        reply = re.sub(r"\s+", " ", x.get("reply") or "")
        reply = reply[:78] + ("…" if len(reply) > 78 else "")
        d.text((640, y + 10), reply, font=font("Regular", 27), fill=QUIET)
        y += 62
    d.text((120, H - 120), "Red-team results posted live:  scout 1.00 → L1 Intern  ·  rookie 0.91 → L1 Intern",
           font=font("SemiBold", 30), fill=INK)
    footer(d, "")
    return [(save(im, name), 1.0)]


def personnel(name):
    im, d = canvas()
    d.text((120, 90), "Personnel file: rookie", font=font("Bold", 60), fill="#ffffff")
    d.text((120, 172), "personnel/rookie.md · append-only · verbatim", font=font("Regular", 28), fill=QUIET)
    text = (SRC / "rookie.md").read_text()
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith("<!--")]
    y = 240
    for l in lines[1:]:
        l = l.replace("**", "")
        l = re.sub(r"Probation room [0-9a-f-]{36}\.", "Probation room created.", l)
        col = BAD if ("Demoted" in l or "Rated bad" in l) else (WARN if "No reply" in l else INK)
        if l.startswith("## "):
            d.text((120, y + 6), l[3:], font=font("SemiBold", 32), fill="#ffffff"); y += 56; continue
        for part in wrap(l, mono(24), 1660, d)[:2]:
            d.text((140, y), part, font=mono(24), fill=col)
            y += 38
    footer(d, "")
    return [(save(im, name), 1.0)]


SCENES = {
    "s01": lambda: title_card("s01", "Probation", "New AI agents earn their way into a team room, the way new hires do.", "Built on Switch"),
    "s02": lambda: text_card("s02", "The gap", [
        "Teams are putting AI agents into shared chat rooms.",
        "A new person gets probation: limited access, supervision, reviews.",
        "A new agent usually gets its owner's full reach on day one.",
    ]),
    "s03": lambda: ladder("s03"),
    "s04": lambda: enforcement("s04"),
    "s05": lambda: chat("s05", "enrolment · probation rooms · busy guard", [61, 62, 64, 65, 67, 68]),
    "s06": lambda: evidence("s06"),
    "s07": lambda: chat("s07", "real work, relayed by Warden", [90, 91]),
    "s08": lambda: chat("s08", "ratings → review → sponsor approval", [96, 97, 98, 99, 100]),
    "s09": lambda: chat("s09", "mystery-shopper spot-check", [73, 75, 76]),
    "s10": lambda: chat("s10", "no replies → bad ratings → demotion", [83, 85, 103, 105, 107, 108]),
    "s11": lambda: personnel("s11"),
    "s12": lambda: text_card("s12", "Getting the measurement right", [
        "A refusal from Switch (\"not permitted\") was scored as a safe answer.",
        "Switch's \"Starting a session…\" line was taken as the answer.",
        "A progress note (\"On it…\") was taken as the whole reply.",
        "The bait file told the agent it was bait.",
    ], note="Each found in a live run, fixed, and covered by a regression test (103 tests)."),
    "s13": lambda: text_card("s13", "Switch + Warden", [
        "Switch: rooms on Discord, side rooms (create_room), addressing rules, the agent protocol, Switch Trust CLI.",
        "Warden: the probation — red-team, relay by level, ratings, sponsor approval, spot-checks, personnel files.",
        "github.com/mukeshkbj/probation",
    ]),
}


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


def build():
    parts = []
    for key, make in SCENES.items():
        frames = make()
        audio = SRC / "audio" / f"{key}.wav"
        total = dur(audio) + 0.5
        lst = OUT / f"{key}.txt"
        with open(lst, "w") as fh:
            for p, share in frames:
                fh.write(f"file '{p}'\nduration {total * share:.3f}\n")
            fh.write(f"file '{frames[-1][0]}'\n")
        part = OUT / f"{key}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-i", str(audio), "-af", "apad=pad_dur=0.5", "-t", f"{total:.3f}",
                        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "aac", "-b:a", "160k", str(part)], check=True)
        parts.append(part)
        print(key, f"{total:.1f}s", len(frames), "frames")
    with open(OUT / "all.txt", "w") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(OUT / "all.txt"),
                    "-c", "copy", "-movflags", "+faststart", str(OUT / "probation-demo.mp4")], check=True)
    print("total", f"{dur(OUT / 'probation-demo.mp4'):.1f}s")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        for k in sys.argv[2:]:
            SCENES[k]()
    else:
        build()
