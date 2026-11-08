"""Style advice: repetition habits in headings and paragraphs. Advisory only: never an error, never a build failure.

Adam's rule (styleguide/voice.md, "Variety"): one catchy headline for the article is good; the same headline device in every
text box and sub-story is a habit and has to stop. Sections and steps should not all follow one approach. This module
reads the story body and says where a device repeats.

Heading devices (what each heading's construction is, not what it says):
    number-led   "1995: the giants still full" starts with a year or number
    label: tail  "APA 2008: a mesh of partners" a short label, a colon, then an image
    question     "Who operates?"
    clipped      "Quicker wells", "Close to home": four words or fewer
    comma twist  "More hits, then a giant": a comma and a turn, eight words or fewer
    plain        anything else: a descriptive sentence or phrase
"""

from __future__ import annotations

import re

HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$", re.M)
STEP = re.compile(r"^:::\s*step\s*(?:\{[^}]*\})?\s*\n(.*?)\n:::\s*$", re.S | re.M)
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
STOP = {"the", "a", "an", "and", "of", "in", "on", "to", "for"}
RUN = 3  # consecutive headings sharing a device
SHARE = 0.6  # share of all headings (when there are at least MIN_FOR_SHARE)
MIN_FOR_SHARE = 6
MAX_PARAGRAPHS = 3
SAME_SHAPE_RUN = 5  # consecutive steps with one paragraph count and similar length
SHAPE_TOLERANCE = 0.35  # word count within this share of the run median
MAX_SUBSECTIONS = 12  # more than this reads as a list, whatever the headings say


def clean(h: str) -> str:
    h = re.sub(r"\{\{.*?\}\}", "N", h)
    return re.sub(r"[*_`]", "", h).strip()


def device(h: str) -> str:
    h = clean(h)
    words = h.split()
    if re.match(r"^\d", h):
        return "number-led"
    if re.match(r"^[^:]{1,28}:\s+\S", h):
        return "label: tail"
    if h.endswith("?"):
        return "question"
    if len(words) <= 4:
        return "clipped"
    if "," in h and len(words) <= 8:
        return "comma twist"
    return "plain"


def headings(body: str) -> list[str]:
    body = FENCE.sub("", body)
    return [clean(m.group(2)) for m in HEADING.finditer(body)]


def paragraphs(md: str) -> int:
    md = FENCE.sub("", md)
    n = 0
    for block in re.split(r"\n\s*\n", md):
        b = block.strip()
        if not b or b.startswith(("#", ":::", "|", "- ", "* ", "1.", ">", "<")):
            continue
        n += 1
    return n


def style_advice(body: str) -> list[str]:
    out: list[str] = []
    hs = headings(body)
    devs = [device(h) for h in hs]
    # 1. the same device in a run of headings
    i = 0
    while i < len(hs):
        j = i
        while j + 1 < len(hs) and devs[j + 1] == devs[i]:
            j += 1
        if devs[i] != "plain" and j - i + 1 >= RUN:
            ex = "; ".join(f"'{h}'" for h in hs[i : min(j + 1, i + 3)])
            out.append(
                f"{j - i + 1} headings in a row use the same device ({devs[i]}): {ex}. "
                "Keep one catchy headline; make the rest plain and different in construction."
            )
        i = j + 1
    # 2. one device dominating the whole piece
    if len(hs) >= MIN_FOR_SHARE:
        for d in sorted(set(devs) - {"plain"}):
            share = devs.count(d) / len(hs)
            if share > SHARE:
                out.append(
                    f"{devs.count(d)} of {len(hs)} headings use the same device ({d}, {share:.0%}). Vary them."
                )
    # 3. the same opening word in a run
    firsts = [h.split()[0].lower().rstrip(":,") if h.split() else "" for h in hs]
    i = 0
    while i < len(hs):
        j = i
        while j + 1 < len(hs) and firsts[j + 1] == firsts[i]:
            j += 1
        need = RUN + 1 if firsts[i] in STOP else RUN
        if j - i + 1 >= need:
            out.append(f"{j - i + 1} headings in a row begin '{firsts[i]}': '{hs[i]}' ... '{hs[j]}'.")
        i = j + 1
    # 4. a long chain of steps with one shape: heading, one paragraph of about the same length, a figure
    shapes = []
    for m in STEP.finditer(body):
        shapes.append((paragraphs(m.group(1)), len(re.sub(r"\s+", " ", FENCE.sub("", m.group(1))).split())))
    i = 0
    while i < len(shapes):
        j = i
        while j + 1 < len(shapes) and shapes[j + 1][0] == shapes[i][0]:
            j += 1
        run = shapes[i : j + 1]
        words = sorted(w for _, w in run)
        med = words[len(words) // 2] or 1
        close = [abs(w - med) / med <= SHAPE_TOLERANCE for _, w in run]
        # longest stretch of similar-length steps inside the run
        best = cur = 0
        for c in close:
            cur = cur + 1 if c else 0
            best = max(best, cur)
        if best >= SAME_SHAPE_RUN:
            out.append(
                f"{best} steps in a row have one shape ({run[0][0]} paragraph(s), about {med} words, then a figure). "
                "Vary it: merge some, let one run longer, let some have no heading of their own."
            )
        i = j + 1
    # 5. too many sub-sections overall
    subs = len(re.findall(r"^### ", FENCE.sub("", body), re.M))
    if subs > MAX_SUBSECTIONS:
        out.append(
            f"{subs} sub-sections (more than {MAX_SUBSECTIONS}): long chains read as a list. Merge, or group under fewer sections."
        )
    # 6. too many paragraphs in one step
    for m in STEP.finditer(body):
        n = paragraphs(m.group(1))
        if n > MAX_PARAGRAPHS:
            h = next(iter(headings(m.group(1))), "(untitled step)")
            out.append(f"step '{h}' has {n} paragraphs (more than {MAX_PARAGRAPHS}): split the idea or cut.")
    return out
