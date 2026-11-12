"""Build full-factorial demographic variants of every base resume.

For each base resume cv/<tier>/NN_resume_<tier>.md and each race x gender x age
cell, writes cv/<tier>/race-<r>_gender-<g>_age-<band>/NN_resume_<tier>.md.

Job content (titles, bullets, years of experience, degrees) is never changed.
Only these slots carry demographic cues, all taken from demographic_cues.json:
  - name and pronouns in the heading; email and LinkedIn derived from the name
  - home city/state and employer cities
  - university and college names
  - degree years (age), plus an "Earlier Career" line when the gap between the
    B.S. and the first listed role is large
  - a closing "Community and Interests" section (race line, gender line, interests)

Writes cv/variants_manifest.json describing every variant. Re-running deletes and
rebuilds all variant folders.
"""

import json
import re
import shutil
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CV = ROOT / "cv"
CUES = json.loads((ROOT / "demographic_cues.json").read_text())
REF = CUES["reference_year"]
TIERS = ["high", "medium", "low"]

DEGREE_KIND = [
    (re.compile(r"Ph\.D\.|Doctor", re.I), "phd"),
    (re.compile(r"MBA|Master of Business", re.I), "mba"),
    (re.compile(r"\bM\.S\.|Master of Science", re.I), "ms"),
    (re.compile(r"\bB\.S\.|\bB\.A\.|Bachelor", re.I), "bs"),
    (re.compile(r"A\.A\.S\.|Associate", re.I), "aas"),
]
DEGREE_OFFSET = {"bs": 0, "ms": 2, "mba": 5, "phd": 6, "aas": -2}
YEAR_SLOT = re.compile(r"<(?:year|Year|graduation_year|grad_year_ms|grad_year_bs)>")
UNIV_SLOT = re.compile(r"<(?:university(?:_(\d+|ms|bs))?|University)>")


def slug(s):
    return s.lower().replace(" ", "_")


def degree_kind(line):
    for pat, kind in DEGREE_KIND:
        if pat.search(line):
            return kind
    return None


def is_degree_line(line):
    s = line.strip()
    return (s.startswith("- **") or s.startswith("**")) and degree_kind(s) is not None and (
        YEAR_SLOT.search(s) or UNIV_SLOT.search(s) or "<college" in s)


def choose_age(band, career_years):
    a = CUES["ages"][band]
    age = a["rep"]
    if band == "37-40":
        age = max(a["rep"], min(a["max"], career_years + 22))
    bs_age = 22 if age - career_years >= 22 else 21
    flag = age - career_years < 21
    return age, bs_age, flag


def build(text, key, idx, race, gender, band):
    rc, gc = CUES["races"][race], CUES["genders"][gender]
    y = CUES["career_years"][key]
    age, bs_age, infeasible = choose_age(band, y)
    bs_year = REF - age + bs_age
    career_start = REF - y
    overrides = CUES["degree_year_overrides"].get(key, {})

    first = rc["first_names"][gender][band][idx % 3]
    last = rc["surnames"][idx % len(rc["surnames"])]
    full = f"{first} {last}"
    email = f"{first.lower()}.{last.lower()}@example.com"

    lines = text.splitlines()
    out, degree_years, univ_seq = [], [], 0
    in_edu = False
    for line in lines:
        if line.startswith("## "):
            in_edu = line.lower().startswith("## education")
        if re.match(r"^# <[Nn]ame>\s*$", line):
            line = f"# {full} ({gc['pronouns']})"
        if "<email>" in line and "<city>" in line:  # header contact line
            line = line.replace("<city>", rc["home"][0], 1).replace("<state>", rc["home"][1], 1)
        line = (line.replace("<email>", email).replace("<phone>", CUES["phone"])
                .replace("<linkedin_url>", f"linkedin.com/in/{first.lower()}-{last.lower()}"))

        m = re.match(r"^\*\*<(company|organization)_(\d+)>\*\*", line)
        if m:
            c, s = rc["employer_cities"][(int(m.group(2)) - 1) % len(rc["employer_cities"])]
            if "<city>" in line:
                line = line.replace("<city>", c, 1).replace("<state>", s, 1)
            elif " | " in line:
                line = line.replace(" | ", f", {c}, {s} | ", 1)

        if in_edu and is_degree_line(line):
            kind = degree_kind(line)
            yr = REF - overrides[kind] if kind in overrides else bs_year + DEGREE_OFFSET[kind]
            degree_years.append(yr)
            line = YEAR_SLOT.sub(str(yr), line, count=1)
            if "<college_1>" in line:
                line = line.replace("<college_1>", rc["college"])
        if "<college_1>" in line:
            line = line.replace("<college_1>", rc["college"])

        def univ(mm):
            nonlocal univ_seq
            tag = mm.group(1)
            if tag and tag.isdigit():
                i = int(tag) - 1
            elif tag == "ms":
                i = 0
            elif tag == "bs":
                i = 1
            else:  # unnumbered: assign in order of appearance
                i = univ_seq
                univ_seq += 1
            return rc["universities"][i % len(rc["universities"])]
        line = UNIV_SLOT.sub(univ, line)
        line = line.replace("<city>", rc["home"][0]).replace("<state>", rc["home"][1])
        out.append(line)

    # Earlier Career line: covers the gap between schooling and the first listed role.
    pre = [d for d in degree_years if d <= career_start] or [bs_year]
    gap_start = max(pre) + 1
    earlier = None
    if career_start - gap_start >= CUES["earlier_career_threshold_years"]:
        earlier = (gap_start, career_start - 1)
        block = ["### Earlier Career", "",
                 f"{earlier[0]}–{earlier[1]}: {CUES['earlier_career_text']}", ""]
        edu = next(i for i, l in enumerate(out) if l.lower().startswith("## education"))
        j = edu
        while j > 0 and out[j - 1].strip() in ("", "---"):
            j -= 1
        out[j:j] = [""] + block[:-1]

    tail = ["", "## Community and Interests", "",
            f"- {rc['community_line']}", f"- {gc['community_line']}",
            f"- Interests: {rc['interests']}"]
    body = "\n".join(out).rstrip() + "\n" + "\n".join(tail) + "\n"
    meta = {"name": full, "pronouns": gc["pronouns"], "age": age, "bs_year": bs_year,
            "degree_years": degree_years, "career_years": y, "earlier_career": earlier,
            "home": ", ".join(rc["home"]), "age_infeasible": infeasible}
    return body, meta


def main():
    manifest = []
    for tier in TIERS:
        for d in (CV / tier).glob("race-*"):
            shutil.rmtree(d)
        bases = sorted((CV / tier).glob("*.md"))
        for idx, base in enumerate(bases):
            key = f"{tier}/{base.name[:2]}"
            text = base.read_text()
            for race, gender, band in product(CUES["races"], CUES["genders"], CUES["ages"]):
                cell = f"race-{slug(race)}_gender-{slug(gender)}_age-{band}"
                body, meta = build(text, key, idx, race, gender, band)
                dest = CV / tier / cell / base.name
                dest.parent.mkdir(exist_ok=True)
                dest.write_text(body)
                manifest.append({"file": str(dest.relative_to(ROOT)), "base": str(base.relative_to(ROOT)),
                                 "tier": tier, "race": race, "gender": gender, "age_band": band, **meta})
    (CV / "variants_manifest.json").write_text(json.dumps(manifest, indent=2))
    bad = [m["file"] for m in manifest if m["age_infeasible"]]
    print(f"wrote {len(manifest)} variants; age-infeasible: {len(bad)}")
    for b in bad:
        print("  ", b)


if __name__ == "__main__":
    main()
