#!/usr/bin/env python3
"""Build anonymized public JSON. Reads Notion when NOTION_TOKEN is set; never writes to Notion."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2026-09-11"
JOB_GAME_ACTIVITY = "3cffada0be4f80f8b3adefa2cc23ac62"
NOTION_VERSION = "2022-06-28"
APPLICATIONS_DB = "3ddfada0-be4f-8039-99fd-000b79c75747"
COMPANIES_DB = "5d6b384e-4857-4483-a48c-2c1d0d291a2c"
MEETINGS_DB = "f77ebcc7-8983-4b6c-b9d9-f79bddb851f0"
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
ALIAS_PATH = ROOT / "scripts" / "aliases.json"


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
    match = re.search(r"([0-9a-f]{32})", str(url).replace("-", ""), re.I)
    return match.group(1).lower() if match else None


def dashed_id(cid: str) -> str:
    raw = cid.replace("-", "")
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


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


def notion_request(method: str, path: str, body: dict | None = None, attempt: int = 0):
    token = os.environ["NOTION_TOKEN"]
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        if error.code == 429 and attempt < 6:
            wait = int(error.headers.get("Retry-After") or "1") + attempt
            time.sleep(wait)
            return notion_request(method, path, body, attempt + 1)
        detail = error.read().decode()[:800]
        raise RuntimeError(f"Notion {method} {path} failed {error.code}: {detail}") from error


def query_database(database_id: str, filter_obj: dict | None = None) -> list[dict]:
    rows: list[dict] = []
    cursor = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        if filter_obj:
            body["filter"] = filter_obj
        payload = notion_request("POST", f"/databases/{database_id}/query", body)
        rows.extend(payload.get("results") or [])
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
        time.sleep(0.2)
    return rows


def unwrap(prop: dict | None):
    if not prop:
        return None
    kind = prop.get("type")
    value = prop.get(kind)
    if value is None:
        return None
    if kind in {"select", "status"}:
        return value.get("name")
    if kind == "multi_select":
        return [item["name"] for item in value]
    if kind == "checkbox":
        return "__YES__" if value else "__NO__"
    if kind == "date":
        return value.get("start")
    if kind == "relation":
        return [item["id"] for item in value]
    if kind == "rich_text" or kind == "title":
        return "".join(item.get("plain_text") or "" for item in value) or None
    if kind == "people":
        return [item.get("id") for item in value]
    return None


def properties(page: dict) -> dict:
    return page.get("properties") or {}


def created_stamp(page: dict) -> str:
    return page.get("created_time") or ""


def as_json_list(value) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def normalize_company(page: dict) -> dict:
    props = properties(page)
    return {
        "url": page.get("url") or page.get("id"),
        "Status": unwrap(props.get("Status")),
        "Role": as_json_list(unwrap(props.get("Role"))),
        "Work Type": as_json_list(unwrap(props.get("Work Type"))),
        "Created": created_stamp(page),
        "retried 4 job game 2026?": unwrap(props.get("retried 4 job game 2026?")),
        "meetings <-> companies": as_json_list(unwrap(props.get("meetings <-> companies"))),
        "activities <-> companies": as_json_list(unwrap(props.get("activities <-> companies"))),
        "date:Applied Date:start": unwrap(props.get("Applied Date")),
        "date:1st Interviewed Date:start": unwrap(props.get("1st Interviewed Date")),
        "date:Ended Date:start": unwrap(props.get("Ended Date")),
    }


def normalize_application(page: dict) -> dict:
    props = properties(page)
    return {
        "url": page.get("url") or page.get("id"),
        "status": unwrap(props.get("status")) or unwrap(props.get("Status")),
        "Board": unwrap(props.get("Board")),
        "created": created_stamp(page),
        "company": as_json_list(unwrap(props.get("company"))),
        "meetings list": as_json_list(unwrap(props.get("meetings list"))),
        "referral from colleague": as_json_list(unwrap(props.get("referral from colleague"))),
    }


def normalize_meeting(page: dict) -> dict:
    props = properties(page)
    tags = unwrap(props.get("Tags")) or []
    return {
        "url": page.get("url") or page.get("id"),
        "Created": created_stamp(page),
        "date:Date:start": unwrap(props.get("Date")),
        "Tags": as_json_list(tags),
        "companies <-> meetings": as_json_list(unwrap(props.get("companies <-> meetings"))),
        "activities <-> meetings": as_json_list(unwrap(props.get("activities <-> meetings"))),
    }


def load_from_notion() -> tuple[list[dict], list[dict], list[dict]]:
    companies = [normalize_company(page) for page in query_database(COMPANIES_DB)]
    applications = [normalize_application(page) for page in query_database(APPLICATIONS_DB)]
    activity = dashed_id(JOB_GAME_ACTIVITY)
    try:
        meetings_pages = query_database(
            MEETINGS_DB,
            {
                "or": [
                    {
                        "timestamp": "created_time",
                        "created_time": {"on_or_after": CUTOFF},
                    },
                    {
                        "property": "activities <-> meetings",
                        "relation": {"contains": activity},
                    },
                ]
            },
        )
    except RuntimeError:
        recent = query_database(
            MEETINGS_DB,
            {"timestamp": "created_time", "created_time": {"on_or_after": CUTOFF}},
        )
        related = query_database(
            MEETINGS_DB,
            {"property": "activities <-> meetings", "relation": {"contains": activity}},
        )
        by_id = {page["id"]: page for page in recent + related}
        meetings_pages = list(by_id.values())
    meetings = [normalize_meeting(page) for page in meetings_pages]
    if not applications or not companies:
        raise SystemExit("Notion returned no applications or companies; refusing to publish")
    return companies, applications, meetings


def load_from_snapshots() -> tuple[list[dict], list[dict], list[dict]]:
    companies_blob = load_json(ROOT / "scripts" / "companies.json")
    companies = companies_blob["results"] if isinstance(companies_blob, dict) else companies_blob
    applications = load_json(ROOT / "scripts" / "applications.json")
    meetings = load_json(ROOT / "scripts" / "meetings.json")
    return companies, applications, meetings


def load_aliases() -> dict[str, int]:
    if not ALIAS_PATH.exists():
        return {}
    raw = load_json(ALIAS_PATH)
    return {str(key): int(value) for key, value in raw.items()}


def bind_aliases(cids: list[str], created_by_id: dict[str, str], existing: dict[str, int]) -> dict[str, int]:
    next_n = max(existing.values(), default=0) + 1
    newcomers = [cid for cid in cids if cid not in existing]
    newcomers.sort(key=lambda cid: (created_by_id.get(cid) or "9999", cid))
    for cid in newcomers:
        existing[cid] = next_n
        next_n += 1
    ALIAS_PATH.write_text(json.dumps(dict(sorted(existing.items(), key=lambda item: item[1])), indent=2) + "\n")
    return existing


def keep_meeting(meeting: dict) -> bool:
    tags = parse_list(meeting.get("Tags"))
    activities = parse_list(meeting.get("activities <-> meetings"))
    created = meeting.get("Created") or ""
    related = any(JOB_GAME_ACTIVITY in (a or "").replace("-", "") for a in activities)
    after_cutoff = created >= f"{CUTOFF}T" or created >= CUTOFF
    jobby = bool(set(tags) & JOB_TAGS)
    if not (related or (after_cutoff and jobby)):
        return False
    return related or jobby or "advice" in tags or "friends" in tags


def previous_tagged_status() -> dict[str, int] | None:
    path = ROOT / "data.json"
    if not path.exists():
        return None
    previous = load_json(path)
    tagged = previous.get("companyStatusTagged")
    return dict(tagged) if tagged else None


def main() -> None:
    using_notion = bool(os.environ.get("NOTION_TOKEN"))
    if using_notion:
        companies, applications, meetings_raw = load_from_notion()
        source = "notion"
    else:
        companies, applications, meetings_raw = load_from_snapshots()
        source = "snapshots"

    kept_meetings = [meeting for meeting in meetings_raw if keep_meeting(meeting)]

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
        if created >= f"{CUTOFF} " or created >= f"{CUTOFF}T" or created >= CUTOFF:
            table_ids.add(cid)
    table_ids |= referenced_ids

    created_by_id = {cid: (company_by_id.get(cid) or {}).get("Created") or "9999" for cid in table_ids}
    existing = load_aliases()
    if not existing:
        ordered_seed = sorted(table_ids, key=lambda cid: (created_by_id.get(cid) or "9999", cid))
        existing = {cid: index for index, cid in enumerate(ordered_seed, start=1)}
    alias_numbers = bind_aliases(sorted(table_ids), created_by_id, existing)
    alias = {cid: f"Company {alias_numbers[cid]:02d}" for cid in table_ids}

    def aliases_for(urls) -> list[str]:
        labels = []
        for url in parse_list(urls):
            cid = page_id(url)
            if not cid:
                continue
            if cid not in alias_numbers:
                bind_aliases([cid], created_by_id, alias_numbers)
            if cid not in alias:
                alias[cid] = f"Company {alias_numbers[cid]:02d}"
                table_ids.add(cid)
            labels.append(alias[cid])
        return labels

    public_meetings = []
    for meeting in kept_meetings:
        tags = [t for t in parse_list(meeting.get("Tags")) if t in PUBLIC_TAGS]
        related = any(
            JOB_GAME_ACTIVITY in (a or "").replace("-", "")
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

    visible_ids = [cid for cid in table_ids if cid in alias]
    visible_ids.sort(key=lambda cid: alias_numbers[cid])
    public_companies = []
    for cid in visible_ids:
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

    if source == "notion":
        tagged_status = Counter(
            (row.get("Status") or "Unknown")
            for row in companies
            if row.get("retried 4 job game 2026?") == "__YES__"
        )
        tagged_status = dict(tagged_status)
    else:
        tagged_status = previous_tagged_status() or dict(
            Counter(
                (row.get("Status") or "Unknown")
                for row in companies
                if row.get("retried 4 job game 2026?") == "__YES__"
            )
        )

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
    if out.exists():
        previous = load_json(out)
        previous.pop("generatedOn", None)
        comparable = dict(payload)
        comparable.pop("generatedOn", None)
        if previous == comparable:
            print(f"unchanged source={source} companies={len(public_companies)} apps={len(public_apps)} calls={len(public_meetings)}")
            return

    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {out} source={source} companies={len(public_companies)} apps={len(public_apps)} calls={len(public_meetings)}")


if __name__ == "__main__":
    main()
