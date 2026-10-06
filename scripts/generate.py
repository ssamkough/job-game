#!/usr/bin/env python3
"""Build anonymized public JSON from local Notion snapshots. Never writes to Notion."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2026-09-11"
JOB_GAME_ACTIVITY = "3cffada0be4f80f8b3adefa2cc23ac62"
JOB_TAGS = {
    "jobs",
    "interview",
    "recruiter",
    "technical",
    "behavioral",
    "in-person / onsite",
    "talent",
    "founder",
}
PUBLIC_TAGS = JOB_TAGS | {"advice"}


def parse_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def page_id(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"([0-9a-f]{32})", url.replace("-", ""), re.I)
    return match.group(1).lower() if match else None


def load_json(path: Path):
    return json.loads(path.read_text())


def classify_meeting(tags: list[str]) -> str:
    lowered = {t.lower() for t in tags}
    if lowered & {"interview", "technical", "behavioral", "in-person / onsite"}:
        return "interview"
    if lowered & {"recruiter", "talent"}:
        return "recruiter"
    if "jobs" in lowered:
        return "call"
    if "advice" in lowered:
        return "advice"
    return "other"


def iso_date(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace(" ", "T").split("T")[0]


def main() -> None:
    companies_blob = load_json(ROOT / "scripts" / "companies.json")
    companies = companies_blob["results"]
    applications = load_json(ROOT / "scripts" / "applications.json")
    meetings_raw = load_json(ROOT / "scripts" / "meetings.json")

    kept_meetings = []
    for meeting in meetings_raw:
        tags = parse_list(meeting.get("Tags"))
        activities = parse_list(meeting.get("activities <-> meetings"))
        created = meeting.get("Created") or ""
        related = any(JOB_GAME_ACTIVITY in (a or "") for a in activities)
        after_cutoff = created >= f"{CUTOFF}T" or created >= CUTOFF
        jobby = bool(set(tags) & JOB_TAGS)
        if related or (after_cutoff and jobby) or (after_cutoff and related):
            if related or jobby or "advice" in tags or "friends" in tags:
                kept_meetings.append(meeting)

    company_by_id = {}
    for row in companies:
        cid = page_id(row.get("url"))
        if cid:
            company_by_id[cid] = row

    referenced_ids: set[str] = set()
    for app in applications:
        for url in parse_list(app.get("company")):
            cid = page_id(url)
            if cid:
                referenced_ids.add(cid)
    for meeting in kept_meetings:
        for url in parse_list(meeting.get("companies <-> meetings")):
            cid = page_id(url)
            if cid:
                referenced_ids.add(cid)

    table_ids = set()
    for cid, row in company_by_id.items():
        created = row.get("Created") or ""
        if created >= f"{CUTOFF} " or created >= CUTOFF:
            table_ids.add(cid)
    table_ids |= referenced_ids

    # Stable anonymous labels, newest first so early-search companies stay low numbers.
    ordered = sorted(
        table_ids,
        key=lambda cid: (
            company_by_id.get(cid, {}).get("Created") or "9999",
            cid,
        ),
    )
    alias = {cid: f"Company {i:02d}" for i, cid in enumerate(ordered, start=1)}

    def aliases_for(urls) -> list[str]:
        labels = []
        for url in parse_list(urls):
            cid = page_id(url)
            if cid:
                if cid not in alias:
                    alias[cid] = f"Company {len(alias) + 1:02d}"
                    table_ids.add(cid)
                labels.append(alias[cid])
        return labels

    public_meetings = []
    for meeting in kept_meetings:
        tags = [t for t in parse_list(meeting.get("Tags")) if t in PUBLIC_TAGS]
        related = any(
            JOB_GAME_ACTIVITY in (a or "")
            for a in parse_list(meeting.get("activities <-> meetings"))
        )
        public_meetings.append(
            {
                "date": iso_date(meeting.get("date:Date:start")),
                "kind": classify_meeting(parse_list(meeting.get("Tags"))),
                "tags": tags,
                "companies": aliases_for(meeting.get("companies <-> meetings")),
                "linkedToJobGame2026": related,
            }
        )
    public_meetings.sort(key=lambda row: row["date"] or "", reverse=True)

    meeting_counts = Counter()
    for meeting in public_meetings:
        for label in meeting["companies"]:
            meeting_counts[label] += 1

    public_apps = []
    for app in applications:
        labels = aliases_for(app.get("company"))
        public_apps.append(
            {
                "submittedOn": iso_date(app.get("created")),
                "status": app.get("status") or "Unknown",
                "board": app.get("Board") or "Direct / other",
                "companies": labels,
                "referred": bool(parse_list(app.get("referral from colleague"))),
                "linkedCalls": len(parse_list(app.get("meetings list"))),
            }
        )
    public_apps.sort(key=lambda row: row["submittedOn"] or "", reverse=True)

    public_companies = []
    for cid in ordered:
        row = company_by_id.get(cid, {})
        roles = parse_list(row.get("Role"))
        work = parse_list(row.get("Work Type"))
        label = alias[cid]
        public_companies.append(
            {
                "alias": label,
                "status": row.get("Status") or "Unknown",
                "role": roles[0] if roles else None,
                "workType": work[0] if work else None,
                "appliedOn": iso_date(row.get("date:Applied Date:start")),
                "firstInterviewOn": iso_date(row.get("date:1st Interviewed Date:start")),
                "callsThisSearch": meeting_counts.get(label, 0),
                "jobGame2026Tag": row.get("retried 4 job game 2026?") == "__YES__",
            }
        )

    # Full Notion SQL aggregation (not limited to the 100-row snapshot).
    tagged_status = {
        "Interviewed": 51,
        "Potential": 33,
        "Denied": 22,
        "Ended": 20,
        "Finding role...": 15,
        "Re-apply": 14,
        "Unknown": 9,
        "Applied": 8,
        "Archived": 5,
        "Interviewing": 4,
        "Not Started": 3,
    }
    app_status = Counter(row["status"] for row in public_apps)
    app_board = Counter(row["board"] for row in public_apps)
    meeting_kind = Counter(row["kind"] for row in public_meetings)
    live_status = Counter(row["status"] for row in public_companies)

    payload = {
        "generatedOn": date.today().isoformat(),
        "cutoff": CUTOFF,
        "privacy": "Company names, people, recruiters, and URLs are omitted. Companies are shown as numbered aliases.",
        "filters": [
            f"Created on or after {CUTOFF}",
            "Job Game 2026 activity relation",
            "Job Game 2026 Applications database",
            "retried for job game 2026 tag on companies",
        ],
        "totals": {
            "applications": len(public_apps),
            "applicationsSubmitted": app_status.get("Submitted", 0),
            "companiesThisSearch": len(public_companies),
            "companiesTaggedJobGame2026": sum(tagged_status.values()),
            "calls": len(public_meetings),
            "recruiterScreens": meeting_kind.get("recruiter", 0),
            "interviews": meeting_kind.get("interview", 0),
            "referrals": sum(1 for row in public_apps if row["referred"]),
        },
        "applicationStatus": dict(app_status),
        "applicationBoards": dict(app_board),
        "companyStatusThisSearch": dict(live_status),
        "companyStatusTagged": dict(tagged_status),
        "callKinds": dict(meeting_kind),
        "applications": public_apps,
        "companies": public_companies,
        "calls": public_meetings,
    }

    out = ROOT / "data.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {out} companies={len(public_companies)} apps={len(public_apps)} calls={len(public_meetings)}")


if __name__ == "__main__":
    main()
