"""Reads what a job actually asks for: level, experience, degree, graduation window, year of study,
GPA, citizenship or clearance, visa sponsorship, and timing. Every finding keeps the sentence it came from."""
from __future__ import annotations

import re
from typing import Any

WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
# Internship terms span months (a Winter term is the January-April co-op term); a graduation "season" is the month degrees are usually conferred.
TERM_MONTHS = {"winter": (1, 4), "spring": (1, 5), "summer": (5, 8), "fall": (8, 12), "autumn": (8, 12)}
GRAD_SEASON = {"winter": 12, "spring": 5, "summer": 8, "fall": 12, "autumn": 12}

PREFERRED_WORDS = re.compile(r"(?i)\b(preferred|nice to have|nice-to-have|bonus|a plus|is a plus|plus if|ideally|desirable|advantageous|an advantage|not required|optional)\b")
PREFERRED_HEADING = re.compile(r"(?i)^(preferred|bonus|nice to have|nice-to-have|additional|desired|good to have|pluses|extra credit)\b[^.]*$")
REQUIRED_HEADING = re.compile(r"(?i)^(minimum|basic|required|requirements|what (you('ll)?|we) (need|bring|require)|qualifications|who you are|you have|must have|what we('re)? look(ing)? for|about you)\b[^.]*$")

SENIOR_TITLE = re.compile(r"(?i)\b(senior|sr\.?|staff|principal|lead|manager|director|head of|architect|vp|vice president|distinguished|fellow)\b")
MID_TITLE = re.compile(r"(?i)\b(engineer|developer|scientist|analyst)\s+(ii|iii|iv|2|3|4)\b|\bmid[- ]level\b")
INTERN_TITLE = re.compile(r"(?i)\b(intern|interns|internship|internships|co-?op|trainee|working student|werkstudent|praktikum|stage|apprentice(ship)?|placement|summer (analyst|associate)|year at \w+)\b")
NEW_GRAD_TITLE = re.compile(r"(?i)\b(new grad(uate)?s?|graduate (program|programme|scheme|engineer|trainee|developer)|entry[- ]level|early career|university grad(uate)?|campus hire|fresher)\b")
JUNIOR_TITLE = re.compile(r"(?i)\b(junior|jr\.?|associate)\b")
# "Early Careers & Interns Specialist" hires interns; it is not an internship.
INTERN_STAFF_TITLE = re.compile(r"(?i)\b(interns?|internships?|early careers?|university|campus)\b[\w\s&,/-]{0,20}\b(specialist|recruiter|recruiting|coordinator|program manager|manager|partner|lead|director)\b")

NUM = r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)"
EXPERIENCE = re.compile(rf"(?i)\b{NUM}\s*\+?\s*(?:(?:-|–|to)\s*{NUM}\s*\+?\s*)?(?:years?|yrs?)(?:'|’)?\s+(?:of\s+)?(?:[\w/+-]+\s+){{0,4}}?(?:experience|exp\b)")
EXPERIENCE_AFTER = re.compile(rf"(?i)\bexperience\b[^.;]{{0,40}}?\b(?:between\s+)?{NUM}\s*\+?\s*(?:(?:-|–|to|and)\s*{NUM}\s*)?(?:years?|yrs?)\b")
NO_EXPERIENCE = re.compile(r"(?i)\b(no (prior |previous |professional |work |industry )?experience (is )?(required|needed|necessary)|experience (is )?not (required|necessary)|no experience needed|(without|with little or no) (prior )?(work |professional )?experience)\b")
PRIOR_INTERNSHIP = re.compile(r"(?i)\b(prior|previous|at least one|one or more)\s+(software |engineering |relevant |technical )?(internships?|co-?ops?)\b(?! (is|are) (a plus|preferred|nice))")

DEGREE_WORDS = {
    "PHD": re.compile(r"(?i)\b(ph\.?\s?d|doctoral|doctorate)\b"),
    "MASTER": re.compile(r"(?i)\b(master'?s?|m\.\s?s\.?|m\.?sc|m\.?\s?tech|mba|graduate (degree|student|program))\b"),
    "BACHELOR": re.compile(r"(?i)\b(bachelor'?s?|b\.\s?s\.?|b\.?s\.?c|ba/bs|bs/ms|b\.?\s?tech|b\.\s?e\.?|undergraduate|undergrad|college student|university student)\b"),
}
ENROLLED = re.compile(r"(?i)\b(currently (enrolled|pursuing|attending|studying|a student)|must be (a |an )?(current |full[- ]time )?(student|enrolled)|enrolled (full[- ]time )?in (a|an|your)|(enrolled|matriculated) (student|full[- ]time)|returning to (school|university|college)|actively (enrolled|pursuing)|(you're|you are) (currently )?(pursuing|enrolled)|pursuing an? (undergraduate|graduate|bachelor|master|degree|b\.|ba/bs))")
REMAINING = re.compile(r"(?i)\b(at least|minimum of)? ?(one|1|a) (semester|quarter|term|year) (of (study|school) )?(remaining|left)\b|return(ing)? to (school|university|college|your studies) (after|following) the internship|for at least another \d+ months")
GRAD_WORD = re.compile(r"(?i)\b(graduating|graduation|graduates?(?= (in|by|before|between|after|no later|no earlier|during|on|from|prior))|class of|degree completion|completion date|complete your degree)\b")
DATE_TOKEN = re.compile(r"(?i)\b(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+|(winter|spring|summer|fall|autumn)\s+|(\d{1,2})\s*/\s*)?(20\d{2})\b")
GRAD_BEFORE = re.compile(r"(?i)\b(before|by|no later than|prior to|on or before)\s*$")
GRAD_AFTER = re.compile(r"(?i)\b(after|no earlier than|from|on or after)\s*$")
OR_LATER = re.compile(r"(?i)^\s*(or later|or after|and later|and beyond|onwards|or beyond)")
OR_EARLIER = re.compile(r"(?i)^\s*(or earlier|or before|and earlier)")
ALTERNATIVE_ROUTES = re.compile(r"(?i)\b(coursework|course work|projects?|academic|school|university|classes|personal work|hackathons?|open[- ]source|or other|clubs?)\b")
YEAR_WORDS = {"first": 1, "1st": 1, "freshman": 1, "second": 2, "2nd": 2, "sophomore": 2, "third": 3, "3rd": 3, "junior": 3, "fourth": 4, "4th": 4, "senior": 4, "fifth": 5, "5th": 5}
YEAR_OF_STUDY = re.compile(r"(?i)\b(penultimate|pre-?final|final|first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)[- ]year (student|of (study|your|a|the|undergraduate|university|college|degree)|undergrad\w*|university|college|bachelor)|\b(completed|finished) (at least )?(the |your )?(first|second|third|1st|2nd|3rd) year\b|\brising (sophomore|junior|senior)s?\b|\b(sophomore|junior|senior) (standing|year|status)\b|\b(sophomores?|juniors?|seniors?) (in|at) (college|university)\b")
GPA = re.compile(r"(?i)(?:c?gpa|grade point average)\s*(?:of\s*)?(?:a\s+)?(?:at least\s*)?(?:a\s+)?(\d{1,2}(?:\.\d{1,2})?)(?:\s*(?:/|out of|on a)\s*(\d{1,2}(?:\.\d)?))?|(\d(?:\.\d{1,2})?)\s*\+?\s*(?:/\s*(\d{1,2}(?:\.\d)?)\s*)?(?:c?gpa|cumulative gpa|grade point average)")
COUNTRY_WORDS = r"(u\.s\.|u\.s|us|usa|united states|american|uk|u\.k\.|british|canadian|canada|indian|india|singapore(?:an)?|australian|australia|german|eu|european union|israeli|israel)"
COUNTRY_CODES = {"u.s.": "US", "u.s": "US", "us": "US", "usa": "US", "united states": "US", "american": "US", "uk": "GB", "u.k.": "GB", "british": "GB",
                 "canadian": "CA", "canada": "CA", "indian": "IN", "india": "IN", "singapore": "SG", "singaporean": "SG", "australian": "AU", "australia": "AU",
                 "german": "DE", "eu": "EU", "european union": "EU", "israeli": "IL", "israel": "IL"}
CITIZEN_REQUIRED = re.compile(rf"(?i)\b(?:must be|only|open to|restricted to|limited to|require[sd]?|requires being)\b[^.;]{{0,25}}?\b{COUNTRY_WORDS}[\s-]+(citizens?|nationals?|persons?)\b|\b{COUNTRY_WORDS}[\s-]+(citizenship|nationality) (is |are )?(required|mandatory|needed)|\b{COUNTRY_WORDS}[\s-]+(citizens?|nationals?) only\b")
CLEARANCE = re.compile(r"(?i)\b(active|current|obtain|maintain|hold|eligib\w*|require[sd]?|must|possess)\b[^.;]{0,60}\b(security clearance|clearance|poly(graph)?)\b|\b(ts/sci|top secret|secret|full scope poly|security)[^.;]{0,20}clearance\b[^.;]{0,40}\b(required|must)\b")
EXPORT_CONTROL = re.compile(r"(?i)\b(itar|export control\w*|ear)\b[^.;]{0,120}\b(u\.?s\.? persons?|citizens?|must|required|are subject)\b|\bu\.?s\.? persons?\b[^.;]{0,40}\b(itar|export)\b")
SPONSOR_YES = re.compile(r"(?i)\b(we|will|can|able to|happy to|open to)\s+(offer|provide|sponsor|support)(ing)?\s+(visa |work permit |immigration |h-?1b )?(sponsorship|visas?|relocation and visa)|\b(visa )?sponsorship (is )?(available|offered|provided)\b|\bopen to (international|foreign) (students|candidates|applicants)\b|\bwe sponsor\b")
SPONSOR_NO = re.compile(r"(?i)\b(no|not|unable to|cannot|can't|won't|will not|does not|do not|isn't|is not)\b[\w\s,-]{0,40}\bsponsor|\bsponsorship\b[\w\s,-]{0,40}\b(unavailable|not (be )?(available|offered|provided|possible))\b|\bwithout (the need for |requiring |needing )?(current or future |now or in the future )?(visa |employer |employment |company )?sponsorship\b|\bmust (already )?(have|hold|possess) (the |a )?(current )?(right|authori[sz]ation|permission) to work\b|\b(not|unable)\b[^.;]{0,160}\b(support|provide|offer)\s+(future\s+)?(h-?1b\s+|visa\s+|immigration\s+)?sponsorship")
TERM = re.compile(r"(?i)\b(winter|spring|summer|fall|autumn)\s*(?:'|’)?(20\d{2}|\d{2})\b")
DURATION = re.compile(r"(?i)\b(\d{1,2})\s*[- ]?\s*(weeks?|months?)\b(?:\s*(?:long|duration|internship|program|programme|placement|co-?op))")
START = re.compile(r"(?i)\b(?:start(?:ing|s)?|begin(?:ning|s)?|commenc\w+)\s+(?:date\s*)?(?:in|on|from|:)?\s*((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)\.?,?\s+(20\d{2})")
NOISE = re.compile(r"(?i)regardless of|equal (employment )?opportunit|without regard to|protected (by law|characteristic|veteran)")


def _sentences(text: str) -> list[tuple[str, bool]]:
    """(sentence, in_preferred_section). Bullets under a 'Preferred qualifications' heading count as preferred;
    lines broken mid-sentence are joined back together."""
    lines: list[str] = []
    # "U.S." and "e.g." are not sentence ends.
    text = re.sub(r"\b([Uu])\.([SsKk])\.|\b([Ee])\.([Gg])\.|\b([Ii])\.([Ee])\.", lambda m: "".join(g for g in m.groups() if g), text or "")
    for raw in re.split(r"\n+", text):
        line = raw.strip(" •-*·\t|")
        if not line:
            continue
        if lines and line[:1].islower() and not re.search(r"[.!?:;]$", lines[-1]):
            lines[-1] += " " + line
        else:
            lines.append(line)
    out: list[tuple[str, bool]] = []
    preferred = False
    for line in lines:
        if len(line) < 70 and PREFERRED_HEADING.match(line):
            preferred = True
            continue
        if len(line) < 70 and REQUIRED_HEADING.match(line):
            preferred = False
            continue
        for sentence in re.split(r"(?<=[.!?;])\s+", line):
            if sentence.strip() and not NOISE.search(sentence):
                out.append((sentence.strip(), preferred))
    return out


def _evidence(sentence: str) -> str:
    text = re.sub(r"\s+", " ", sentence).strip()
    return text if len(text) <= 240 else text[:237].rstrip() + "…"


def _number(token: str | None) -> float | None:
    if not token:
        return None
    token = token.lower()
    return float(WORD_NUMBERS[token]) if token in WORD_NUMBERS else float(token)


def _year(token: str) -> int:
    value = int(token)
    return value + 2000 if value < 100 else value


def seniority(title: str) -> str:
    """INTERN, NEW_GRAD, JUNIOR, MID, SENIOR or UNKNOWN, from the job title alone."""
    if INTERN_TITLE.search(title or "") and not INTERN_STAFF_TITLE.search(title or ""):
        return "INTERN"
    if SENIOR_TITLE.search(title or ""):
        return "SENIOR"
    if NEW_GRAD_TITLE.search(title or ""):
        return "NEW_GRAD"
    if MID_TITLE.search(title or ""):
        return "MID"
    if JUNIOR_TITLE.search(title or ""):
        return "JUNIOR"
    return "UNKNOWN"


def _graduation(sentences: list[tuple[str, bool]], title: str) -> dict[str, Any] | None:
    for sentence, _ in sentences:
        grad = GRAD_WORD.search(sentence)
        if not grad or re.search(r"(?i)\b(after|upon|post[- ]?)\s*graduat", sentence):
            continue
        window = sentence[grad.start(): grad.end() + 110]
        tokens = []
        for match in DATE_TOKEN.finditer(window):
            month_name, season, number, year = match.groups()
            year_value = int(year)
            if month_name:
                month = MONTHS[month_name[:3].lower()]
                early, late = month, month
            elif season:
                early = late = GRAD_SEASON[season.lower()]
            elif number and 1 <= int(number) <= 12:
                early = late = int(number)
            else:
                early, late = 1, 12
            tokens.append((match.start(), year_value, early, late))
        if not tokens:
            continue
        if len(tokens) >= 2:
            first = min(tokens, key=lambda t: (t[1], t[2]))
            last = max(tokens, key=lambda t: (t[1], t[3]))
            return {"earliest": f"{first[1]:04d}-{first[2]:02d}", "latest": f"{last[1]:04d}-{last[3]:02d}", "evidence": _evidence(sentence)}
        start, year, early, late = tokens[0]
        before = window[:start]
        after = window[start:].split(str(year), 1)[-1]
        if OR_LATER.search(after):
            return {"earliest": f"{year:04d}-{early:02d}", "latest": None, "evidence": _evidence(sentence)}
        if OR_EARLIER.search(after):
            return {"earliest": None, "latest": f"{year:04d}-{late:02d}", "evidence": _evidence(sentence)}
        if GRAD_BEFORE.search(before):
            return {"earliest": None, "latest": f"{year:04d}-{late:02d}", "evidence": _evidence(sentence)}
        if GRAD_AFTER.search(before):
            return {"earliest": f"{year:04d}-{early:02d}", "latest": None, "evidence": _evidence(sentence)}
        return {"earliest": f"{year:04d}-{early:02d}", "latest": f"{year:04d}-{late:02d}", "evidence": _evidence(sentence)}
    match = re.search(r"(?i)\b(?:class of|new grad(?:uate)?s?)\s*(?:of\s*)?(20\d{2})\b", title or "")
    if match:
        year = int(match.group(1))
        return {"earliest": f"{year}-01", "latest": f"{year}-12", "evidence": f"From the title: {title}"}
    return None


def _year_of_study(sentences: list[tuple[str, bool]]) -> dict[str, Any] | None:
    for sentence, in_preferred in sentences:
        if in_preferred or PREFERRED_WORDS.search(sentence):
            continue
        if re.search(r"(?i)freshm[ae]n", sentence) and re.search(r"(?i)seniors?", sentence):
            return {"open_to_all": True, "evidence": _evidence(sentence)}
        match = YEAR_OF_STUDY.search(sentence)
        if not match:
            continue
        text = match.group(0).lower()
        if "penultimate" in text or "pre-final" in text or "prefinal" in text:
            return {"kind": "PENULTIMATE", "evidence": _evidence(sentence)}
        if text.startswith("final"):
            return {"kind": "FINAL", "evidence": _evidence(sentence)}
        word = next((w for w in re.findall(r"[a-z0-9]+", text) if w.rstrip("s") in YEAR_WORDS), None)
        if word is None:
            continue
        year = YEAR_WORDS[word.rstrip("s")]
        if text.startswith(("completed", "finished")):
            return {"kind": "AT_LEAST", "years": [year + 1], "evidence": _evidence(sentence)}
        if text.startswith("rising"):
            return {"kind": "EXACT", "years": [year - 1], "rising": True, "evidence": _evidence(sentence)}
        if re.search(r"(?i)\b(minimum|at least|or (above|higher|later))\b", sentence[max(0, match.start() - 25): match.end() + 15]):
            return {"kind": "AT_LEAST", "years": [year], "evidence": _evidence(sentence)}
        # "2nd or 3rd year student" accepts both years.
        lead = sentence[max(0, match.start() - 30): match.start()]
        years = sorted({YEAR_WORDS[w] for w in re.findall(r"[a-z0-9]+", lead.lower()) if w in YEAR_WORDS} | {year})
        return {"kind": "EXACT", "years": years, "evidence": _evidence(sentence)}
    return None


def _citizenship(sentences: list[tuple[str, bool]], listing: dict[str, Any]) -> dict[str, Any] | None:
    countries: set[str] = set()
    clearance = export = permanent_residents = False
    evidence = None
    for sentence, _ in sentences:
        if re.match(r"(?i)(experience|familiarity|knowledge|understanding)\b", sentence) or re.search(r"(?i)\bmay (require|be required)\b|some of these roles", sentence):
            continue
        hit = False
        for match in CITIZEN_REQUIRED.finditer(sentence):
            word = next(g for g in (match.group(1), match.group(3), match.group(6)) if g)
            countries.add(COUNTRY_CODES.get(word.lower().rstrip("."), COUNTRY_CODES.get(word.lower(), word.upper())))
            hit = True
        if CLEARANCE.search(sentence) and re.search(r"(?i)clearance|poly", sentence):
            clearance = hit = True
            place = re.search(rf"(?i)\b{COUNTRY_WORDS}\b", sentence)
            if place:
                countries.add(COUNTRY_CODES.get(place.group(1).lower(), place.group(1).upper()))
        if EXPORT_CONTROL.search(sentence):
            export = hit = True
            countries.add("US")
        if hit:
            permanent_residents = permanent_residents or bool(re.search(r"(?i)permanent residen|green card|lawful(ly)? permanent", sentence))
            evidence = evidence or _evidence(sentence)
    if listing.get("sponsorship") == "U.S. Citizenship is Required":
        countries.add("US")
        evidence = evidence or "The job board lists: U.S. citizenship is required."
    if not countries and not clearance:
        return None
    return {"countries": sorted(countries), "clearance": clearance, "export_control": export, "permanent_residents_ok": permanent_residents, "evidence": evidence}


def extract(title: str, description: str, listing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Structured requirements. `listing` carries structured hints from job boards (terms, degrees, sponsorship)."""
    listing = listing or {}
    found: dict[str, Any] = {"seniority": seniority(title)}
    sentences = _sentences(description)

    # Experience: the largest required minimum; preferred mentions are recorded as not required.
    required_years: list[tuple[float, str]] = []
    preferred_years: list[tuple[float, str]] = []
    for sentence, in_preferred in sentences:
        for pattern in (EXPERIENCE, EXPERIENCE_AFTER):
            for match in pattern.finditer(sentence):
                low = _number(match.group(1))
                if re.search(r"(?i)\b(less than|fewer than|no more than|under|up to|maximum of|at most)\s*$", sentence[:match.start()]):
                    continue  # an upper limit ("less than 2 years"), which a student always meets
                if low is None or low > 25 or re.search(r"(?i)\b(weeks?|months?) (of )?experience", match.group(0)):
                    continue
                if ALTERNATIVE_ROUTES.search(sentence) and re.search(r"(?i)\b(through|via|from|including|or)\b", sentence):
                    preferred_years.append((low, _evidence(sentence)))
                    continue
                (preferred_years if in_preferred or PREFERRED_WORDS.search(sentence) else required_years).append((low, _evidence(sentence)))
    if required_years:
        years, evidence = max(required_years, key=lambda x: x[0])
        found["experience"] = {"min_years": years, "required": True, "evidence": evidence}
    elif preferred_years:
        years, evidence = max(preferred_years, key=lambda x: x[0])
        found["experience"] = {"min_years": years, "required": False, "evidence": evidence}
    no_exp = next((s for s, _ in sentences if NO_EXPERIENCE.search(s)), None)
    if no_exp and not required_years:
        found["experience"] = {"min_years": 0, "required": False, "none_needed": True, "evidence": _evidence(no_exp)}
    prior = next((s for s, pref in sentences if PRIOR_INTERNSHIP.search(s) and not pref and not PREFERRED_WORDS.search(s) and not ALTERNATIVE_ROUTES.search(s)), None)
    if prior:
        found["prior_internship"] = {"required": True, "evidence": _evidence(prior)}

    # Degree level: every level the required sentences accept, plus structured hints from the board.
    levels: set[str] = set()
    degree_evidence = None
    for sentence, in_preferred in sentences:
        if in_preferred or PREFERRED_WORDS.search(sentence):
            continue
        if not re.search(r"(?i)degree|pursuing|enrolled|student|bachelor|master|ph\.?\s?d|undergrad|b\.s|m\.s", sentence) or re.search(r"(?i)\$|/\s?h(ou)?r|per hour|salary|compensation|stipend", sentence):
            continue
        hit = {name for name, pattern in DEGREE_WORDS.items() if pattern.search(sentence)}
        if hit:
            levels |= hit
            degree_evidence = degree_evidence or _evidence(sentence)
    board_degrees = [str(d) for d in listing.get("degrees") or []]
    for degree in board_degrees:
        text = degree.lower()
        levels |= {"PHD"} if "phd" in text else {"MASTER"} if "master" in text else {"BACHELOR"} if "bachelor" in text else set()
    if levels:
        order = ["BACHELOR", "MASTER", "PHD"]
        accepted = [lvl for lvl in order if lvl in levels]
        found["degree"] = {"accepted": accepted, "min": accepted[0], "evidence": degree_evidence or "Listed degree levels: " + ", ".join(board_degrees)}

    enrolled = next((s for s, _ in sentences if ENROLLED.search(s)), None)
    if enrolled:
        found["enrollment"] = {"required": True, "evidence": _evidence(enrolled)}
    remaining = next((s for s, _ in sentences if REMAINING.search(s)), None)
    if remaining:
        found["returning_after"] = {"required": True, "evidence": _evidence(remaining)}

    graduation = _graduation(sentences, title)
    if graduation:
        found["graduation"] = graduation
    year_of_study = _year_of_study(sentences)
    if year_of_study:
        found["year_of_study"] = year_of_study

    for sentence, in_preferred in sentences:
        match = GPA.search(sentence)
        if match:
            value = float(match.group(1) or match.group(3))
            scale = match.group(2) or match.group(4)
            scale_value = float(scale) if scale else (4.0 if value <= 4 else 5.0 if value <= 5 else 10.0 if value <= 10 else 100.0)
            if 0 < value <= scale_value:
                found["gpa"] = {"min": value, "scale": scale_value, "required": not (in_preferred or PREFERRED_WORDS.search(sentence)), "evidence": _evidence(sentence)}
                break

    citizenship = _citizenship(sentences, listing)
    if citizenship:
        found["citizenship"] = citizenship

    statements = [(s, p) for s, p in sentences if "?" not in s]  # "Is sponsorship available?" is a form question, not an answer
    sponsor_no = next((s for s, _ in statements if SPONSOR_NO.search(s) and re.search(r"(?i)sponsor|authori[sz]|right to work|visa", s) and not re.search(r"(?i)sponsor(ing|ed|s)? (events?|partners?|conferences?)|capability sponsor|programme sponsor|program sponsor", s)), None)
    sponsor_yes = next((s for s, _ in statements if SPONSOR_YES.search(s)), None)
    if listing.get("sponsorship") == "Offers Sponsorship":
        found["sponsorship"] = {"offered": True, "evidence": "The job board lists: offers visa sponsorship."}
    elif listing.get("sponsorship") in {"Does Not Offer Sponsorship", "U.S. Citizenship is Required"}:
        found["sponsorship"] = {"offered": False, "evidence": "The job board lists: " + ("U.S. citizenship is required." if listing["sponsorship"] == "U.S. Citizenship is Required" else "does not offer visa sponsorship.")}
    elif sponsor_no:
        found["sponsorship"] = {"offered": False, "evidence": _evidence(sponsor_no)}
    elif sponsor_yes:
        found["sponsorship"] = {"offered": True, "evidence": _evidence(sponsor_yes)}

    terms = [str(t) for t in listing.get("terms") or [] if TERM.search(str(t))]
    if not terms:
        terms = [f"{m.group(1)} {m.group(2)}" for m in TERM.finditer(title or "")] or \
                [f"{m.group(1)} {m.group(2)}" for m in TERM.finditer((description or "")[:3000]) if not GRAD_WORD.search((description or "")[max(0, m.start() - 80): m.start()])][:2]
    windows = []
    for term in dict.fromkeys(terms):
        m = TERM.search(term)
        season, year = m.group(1).lower(), _year(m.group(2))
        first, last = TERM_MONTHS[season]
        label = f"{'Fall' if season == 'autumn' else season.title()} {year}"
        if label not in {w["label"] for w in windows}:
            windows.append({"label": label, "start": f"{year:04d}-{first:02d}", "end": f"{year:04d}-{last:02d}"})
    if windows:
        found["term"] = {"windows": windows, "evidence": ", ".join(w["label"] for w in windows)}
    duration = next((m for m in (DURATION.search(s) for s, _ in sentences) if m), None)
    if duration:
        n = int(duration.group(1))
        found["duration_months"] = round(n / 4.33, 1) if duration.group(2).lower().startswith("week") else float(n)
    start = next((m for m in (START.search(s) for s, _ in sentences) if m), None)
    if start:
        found["start"] = f"{int(start.group(2)):04d}-{MONTHS[start.group(1)[:3].lower()]:02d}"
    return found


def is_student_friendly(found: dict[str, Any]) -> bool:
    """True when nothing in the posting asks for more than a student can have."""
    exp = found.get("experience") or {}
    return found.get("seniority") in {"INTERN", "NEW_GRAD", "UNKNOWN", "JUNIOR"} and not (exp.get("required") and exp.get("min_years", 0) >= 1)


VERSION = 2  # bump when extraction improves; stored requirements are then recomputed once


def tags(found: dict[str, Any]) -> list[dict[str, str]]:
    """Short plain-word chips for job cards: [{label, tone}] with tone good / warn / bad."""
    out: list[dict[str, str]] = []
    level = found.get("seniority")
    if level == "NEW_GRAD":
        out.append({"label": "New grad", "tone": "warn"})
    elif level in {"SENIOR", "MID"}:
        out.append({"label": "Senior role", "tone": "bad"})
    exp = found.get("experience") or {}
    if exp.get("none_needed"):
        out.append({"label": "No experience needed", "tone": "good"})
    elif exp.get("required") and exp.get("min_years"):
        out.append({"label": f"{exp['min_years']:g}+ yrs experience", "tone": "bad"})
    sponsor = found.get("sponsorship") or {}
    if sponsor.get("offered") is True:
        out.append({"label": "Sponsors visas", "tone": "good"})
    elif sponsor.get("offered") is False:
        out.append({"label": "No visa sponsorship", "tone": "bad"})
    citizen = found.get("citizenship") or {}
    if citizen:
        out.append({"label": "Security clearance" if citizen.get("clearance") else f"{'/'.join(citizen.get('countries') or [])} citizens only", "tone": "bad"})
    degree = found.get("degree") or {}
    if degree and degree.get("min") != "BACHELOR":
        out.append({"label": {"MASTER": "Master's+", "PHD": "PhD only"}[degree["min"]], "tone": "bad"})
    grad = found.get("graduation") or {}
    if grad:
        years = sorted({g[:4] for g in (grad.get("earliest"), grad.get("latest")) if g})
        out.append({"label": "Grad " + "–".join(years), "tone": "warn"})
    for window in (found.get("term") or {}).get("windows", [])[:2]:
        out.append({"label": window["label"], "tone": "neutral"})
    return out
