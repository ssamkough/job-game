#!/usr/bin/env python3
"""Build anonymized public JSON. Reads Notion when NOTION_TOKEN is set; never writes to Notion."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2026-09-11"
JOB_GAME_ACTIVITY = "3cffada0be4f80f8b3adefa2cc23ac62"
NOTION_VERSION = "2025-09-03"
APPLICATIONS_DB = "3ddfada0-be4f-8039-99fd-000b79c75747"
COMPANIES_DB = "5d6b384e-4857-4483-a48c-2c1d0d291a2c"
MEETINGS_DB = "f77ebcc7-8983-4b6c-b9d9-f79bddb851f0"
# Submitted view: status group Complete (Submitted + Archived).
APPLICATION_VIEW_STATUSES = {"Submitted", "Archived"}
# Kind labels for the public table. The jobs tag selects the view, but is never shown.
MEETING_KIND_TAGS = (
    ("onsite", "in-person / onsite"),
    ("technical", "technical"),
    ("intro", "intro"),
    ("recruiter", "recruiter"),
)
ALIAS_PATH = ROOT / "scripts" / "aliases.json"
COMPANY_TABLE_STATUSES = {
    "Finding role...",
    "Applied",
    "Interviewing",
    "Take-Home",
    "Negotating",
    "Negotiating",
    "Interviewed",
}


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
    for kind, tag in MEETING_KIND_TAGS:
        if tag in lowered:
            return kind
    return "other"


def public_meeting_tags(tags: list[str]) -> list[str]:
    lowered = {t.lower() for t in tags}
    return [kind for kind, tag in MEETING_KIND_TAGS if tag in lowered]


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
        payload = notion_request("POST", f"/data_sources/{database_id}/query", body)
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
        ids = []
        for item in value or []:
            if isinstance(item, str):
                ids.append(item)
            elif isinstance(item, dict):
                ids.append(item.get("id") or item.get("page_id") or "")
        return [item for item in ids if item]
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
        "Name": unwrap(props.get("Name")),
        "Status": unwrap(props.get("Status")),
        "Role": as_json_list(unwrap(props.get("Role"))),
        "Work Type": as_json_list(unwrap(props.get("Work Type"))),
        "Created": created_stamp(page),
        "Last edited": page.get("last_edited_time") or "",
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
        "Name": unwrap(props.get("Name")),
        "status": unwrap(props.get("status")) or unwrap(props.get("Status")),
        "Board": unwrap(props.get("Board")),
        "created": created_stamp(page),
        "company": as_json_list(unwrap(props.get("company"))),
        "meetings list": as_json_list(unwrap(props.get("meetings list"))),
        "recruiter": as_json_list(unwrap(props.get("recruiter"))),
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
    meetings_pages = query_database(
        MEETINGS_DB,
        {"property": "Tags", "multi_select": {"contains": "jobs"}},
    )
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


def after_cutoff(value: str | None) -> bool:
    stamp = value or ""
    return stamp >= f"{CUTOFF}T" or stamp >= f"{CUTOFF} " or stamp >= CUTOFF


def keep_application(app: dict) -> bool:
    return (app.get("status") or "") in APPLICATION_VIEW_STATUSES


def company_in_table(row: dict) -> bool:
    if (row.get("Status") or "") not in COMPANY_TABLE_STATUSES:
        return False
    return after_cutoff(row.get("Last edited") or row.get("Created"))


def keep_meeting(meeting: dict) -> bool:
    tags = {t.lower() for t in parse_list(meeting.get("Tags"))}
    if "jobs" not in tags:
        return False
    meeting_date = iso_date(meeting.get("date:Date:start"))
    if not meeting_date or meeting_date >= date.today().isoformat():
        return False
    activities = parse_list(meeting.get("activities <-> meetings"))
    related = any(JOB_GAME_ACTIVITY in (a or "").replace("-", "") for a in activities)
    return related or after_cutoff(meeting_date)


def previous_tagged_status() -> dict[str, int] | None:
    path = ROOT / "data.json"
    if not path.exists():
        return None
    previous = load_json(path)
    tagged = previous.get("companyStatusTagged")
    return dict(tagged) if tagged else None


def main() -> None:
    using_notion = bool(os.environ.get("NOTION_TOKEN"))
    if os.environ.get("CI") and not using_notion:
        raise SystemExit("NOTION_TOKEN is missing. Add it as a repository secret named NOTION_TOKEN.")
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

    kept_apps = [app for app in applications if keep_application(app)]

    referenced_ids: set[str] = set()
    for app in kept_apps:
        for url in parse_list(app.get("company")):
            cid = page_id(url)
            if cid:
                referenced_ids.add(cid)
    for meeting in kept_meetings:
        for url in parse_list(meeting.get("companies <-> meetings")):
            cid = page_id(url)
            if cid:
                referenced_ids.add(cid)

    table_ids = {cid for cid, row in company_by_id.items() if company_in_table(row)}
    alias_ids = set(table_ids) | referenced_ids

    created_by_id = {cid: (company_by_id.get(cid) or {}).get("Created") or "9999" for cid in alias_ids}
    existing = load_aliases()
    if not existing:
        ordered_seed = sorted(alias_ids, key=lambda cid: (created_by_id.get(cid) or "9999", cid))
        existing = {cid: index for index, cid in enumerate(ordered_seed, start=1)}
    alias_numbers = bind_aliases(sorted(alias_ids), created_by_id, existing)
    alias = {cid: f"Company {alias_numbers[cid]:02d}" for cid in alias_ids}

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
                alias_ids.add(cid)
            labels.append(alias[cid])
        return labels

    hidden_meetings: dict[str, list[dict]] = defaultdict(list)
    public_meetings = []
    for meeting in kept_meetings:
        raw_tags = parse_list(meeting.get("Tags"))
        related = any(
            JOB_GAME_ACTIVITY in (a or "").replace("-", "")
            for a in parse_list(meeting.get("activities <-> meetings"))
        )
        labels = aliases_for(meeting.get("companies <-> meetings"))
        row = {
            "date": iso_date(meeting.get("date:Date:start")),
            "kind": classify_meeting(raw_tags),
            "tags": public_meeting_tags(raw_tags),
            "companies": labels,
            "linkedToJobGame2026": related,
        }
        public_meetings.append(row)
        hidden_row = {"date": row["date"], "kind": row["kind"]}
        for label in labels:
            hidden_meetings[label].append(hidden_row)
    public_meetings.sort(key=lambda row: row["date"] or "", reverse=True)

    meeting_counts = Counter()
    for meeting in public_meetings:
        for label in meeting["companies"]:
            meeting_counts[label] += 1

    hidden_apps: dict[str, list[dict]] = defaultdict(list)
    public_apps = []
    for app in kept_apps:
        labels = aliases_for(app.get("company"))
        row = {
            "submittedOn": iso_date(app.get("created")),
            "status": app.get("status") or "Unknown",
            "board": app.get("Board") or "Direct / other",
            "companies": labels,
            "recruiter": bool(parse_list(app.get("recruiter"))),
            "referred": bool(parse_list(app.get("referral from colleague"))),
            "linkedMeetings": len(parse_list(app.get("meetings list"))),
        }
        public_apps.append(row)
        hidden_row = {
            "submittedOn": row["submittedOn"],
            "status": row["status"],
            "board": row["board"],
            "role": app.get("Name"),
            "recruiter": row["recruiter"],
            "referred": row["referred"],
        }
        for label in labels:
            hidden_apps[label].append(hidden_row)
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
                "meetingsThisSearch": meeting_counts.get(label, 0),
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
            "Meetings fin | job game 2026 view (date before today, jobs tag, Job Game 2026 activity)",
            "Job Game 2026 Applications Submitted view (status Complete: Submitted, Archived)",
            "retried for job game 2026 tag on companies",
            "Company table: Finding role..., Applied, Interviewing, Take-Home, Negotating/Negotiating, Interviewed",
            f"Company table: last edited on or after {CUTOFF}",
        ],
        "totals": {
            "applications": len(public_apps),
            "applicationsSubmitted": app_status.get("Submitted", 0),
            "companiesThisSearch": len(public_companies),
            "companiesTaggedJobGame2026": sum(tagged_status.values()),
            "meetings": len(public_meetings),
            "recruiterScreens": sum(1 for row in public_meetings if "recruiter" in row["tags"]),
            "recruiters": sum(1 for row in public_apps if row["recruiter"]),
            "interviews": meeting_kind.get("technical", 0),
            "referrals": sum(1 for row in public_apps if row["referred"]),
        },
        "applicationStatus": dict(app_status),
        "applicationBoards": dict(app_board),
        "companyStatusThisSearch": dict(live_status),
        "companyStatusTagged": dict(tagged_status),
        "meetingKinds": dict(meeting_kind),
        "applications": public_apps,
        "companies": public_companies,
        "meetings": public_meetings,
    }

    label_to_cid = {alias[cid]: cid for cid in alias if cid in alias_numbers}
    shown_labels = {row["alias"] for row in public_companies} | set(hidden_apps) | set(hidden_meetings)
    hidden_companies = []
    for label in sorted(shown_labels, key=lambda item: alias_numbers[label_to_cid[item]]):
        cid = label_to_cid[label]
        row = company_by_id.get(cid, {})
        hidden_companies.append(
            {
                "alias": label,
                "name": row.get("Name"),
                "status": row.get("Status") or "Unknown",
                "applications": hidden_apps.get(label, []),
                "meetings": hidden_meetings.get(label, []),
            }
        )
    hidden_payload = {
        "generatedOn": date.today().isoformat(),
        "companies": hidden_companies,
    }

    def write_json(path: Path, blob: dict) -> bool:
        text = json.dumps(blob, indent=2) + "\n"
        if path.exists() and path.read_text() == text:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return True

    public_path = ROOT / "data.json"
    hidden_path = ROOT / "hidden" / "data.json"
    wrote_public = write_json(public_path, payload)
    wrote_hidden = write_json(hidden_path, hidden_payload)
    if not wrote_public and not wrote_hidden:
        print(f"unchanged source={source} companies={len(public_companies)} apps={len(public_apps)} meetings={len(public_meetings)}")
        return
    print(
        f"wrote source={source} companies={len(public_companies)} apps={len(public_apps)} "
        f"meetings={len(public_meetings)} hidden={len(hidden_companies)} "
        f"public={wrote_public} names={wrote_hidden}"
    )


if __name__ == "__main__":
    main()
