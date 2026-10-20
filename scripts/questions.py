"""Read, anonymize, clean, and dedupe asked-questions from the Notion page."""

from __future__ import annotations

import json
import re
from pathlib import Path

QUESTIONS_PAGE = "3f7fada0-be4f-80d5-8ca2-d3e841e0f01f"
QUESTIONS_SNAPSHOT = Path(__file__).resolve().parents[1] / "scripts" / "questions.json"
SKIP_TOGGLE_TITLES = {"code", "solution", "answer", "resources"}
PROMPT_TOGGLE_TITLES = {"readme", "prompt", "question"}
SECTION_HEADINGS = {
    "behavioral": "behavioral",
    "technical": "technical",
}

TYPOS = (
    (r"\bhhad\b", "had"),
    (r"\bthorugh\b", "through"),
    (r"\bthruogh\b", "through"),
    (r"\byouve\b", "you've"),
    (r"\byoure\b", "you're"),
    (r"\byour're\b", "you're"),
    (r"\bive\b", "I've"),
    (r"\bim\b", "I'm"),
    (r"\bur\b", "you're"),
    (r"\bwont\b", "won't"),
    (r"\bdont\b", "don't"),
    (r"\bcant\b", "can't"),
    (r"\bwhats\b", "what's"),
    (r"\bthats\b", "that's"),
    (r"\brealtime\b", "real-time"),
    (r"\bfull stack\b", "full-stack"),
    (r"\bjson\b", "JSON"),
    (r"\bui\b", "UI"),
    (r"\bai\b", "AI"),
    (r"\breact\b", "React"),
    (r"\btypescript\b", "TypeScript"),
    (r"\bphia\b", "Phia"),
    (r"\btemelio\b", "Temelio"),
)

PHRASES = (
    (r"^what tech stacks \(pre-AI\)\??$", "What tech stacks have you used (pre-AI)?"),
    (r"^where I see myself in a couple years\??$", "Where do you see yourself in a couple of years?"),
    (r"^where my experience lies\??$", "Where does your experience lie?"),
    (r"^what about technical tradeoffs in the product\??$", "What technical tradeoffs did you make in the product?"),
    (r"^provide example when faced a deadline with a project\??$", "Provide an example of when you faced a deadline with a project."),
    (r"^for my next role what am I looking for\.?$", "What are you looking for in your next role?"),
    (r"^do I have experience in mentorship\??$", "Do you have experience in mentorship?"),
    (r"^problem I'm happy with that I worked on\.?$", "What's a problem you're happy with that you worked on?"),
    (r"^biggest change I've made in myself based on feedback I've received\.?$", "What's the biggest change you've made in yourself based on feedback you've received?"),
    (r"^at Temelio product roadmap with feature\? or is there more problems\??$", "At Temelio, was the product roadmap about features, or are there more problems?"),
    (r"^walk her through tech stack I worked with previously\. and preferences with split\??$", "Walk through the tech stack you worked with previously, and your preferences for the split."),
    (r"^walk through a complex project that I've owned that was full-stack\??$", "Walk through a complex full-stack project that you've owned."),
    (r"tell (him|her) what exactly", "explain what"),
    (r"tell (him|her) ", ""),
    (r"walk (him|her) through", "walk through"),
    (r"^any time you had a disagreement that you had with a colleague\??$", "Was there a time you had a disagreement with a colleague?"),
    (r"^built from scratch or leveled up\. What did it look like before and what I did to make it better\.?$", "Did you build it from scratch or level it up? What did it look like before, and what did you do to make it better?"),
    (r"^how do I orient myself\? How do I show progress\? How do you communicate to stakeholders\?$", "How do you orient yourself? How do you show progress? How do you communicate to stakeholders?"),
    (r"how I do show", "how do I show"),
    (r"where did the app came from", "where did the app come from"),
    (r"is it just on browser", "is it just on the browser"),
    (r", explain Phia\??", "."),
    (r"what exactly Phia does", "what Phia does"),
    (r"^tell me about how AI has changed my daily workflow\??$", "Tell me about how AI has changed your daily workflow."),
    (r"what were the challenges, where did the app come from", "what were the challenges, and where did the app come from"),
)

TITLE_PHRASES = (
    (r"^given an input json, print its schema\.?$", "Print a JSON schema"),
)
GENERIC_TITLE_LINES = PROMPT_TOGGLE_TITLES | SKIP_TOGGLE_TITLES | {
    "question",
    "problem",
    "task",
    "prompt",
}
TITLE_KEEP_WORDS = {"JSON", "UI", "AI", "API", "SQL", "HTTP", "CSS", "HTML", "URL"}

ASKED_ME = re.compile(r"^asked me\s+", re.I)
ASKED_ABOUT = re.compile(r"^asked about\s+", re.I)
FOLLOW_UP = re.compile(r"^follow-?up:\s*", re.I)
ROUND_TITLE = re.compile(
    r"(?i)^(?:from\s+(?:head of eng\s+|recruiter\s+)?)?(.+?)(?:\s+(?:call|intro|technical round)(?:\s+with\s+.+)?|\s+technical round)?$"
)
QUESTION_START = re.compile(
    r"^(what|what's|when|where|why|who|how|do|did|does|is|are|have|has|can|could|would|will|tell|walk|provide|explain|describe|take)\b",
    re.I,
)


def block_text(block: dict) -> str:
    kind = block.get("type") or ""
    body = block.get(kind) or {}
    texts = body.get("rich_text") or body.get("title") or []
    return "".join(item.get("plain_text") or "" for item in texts).strip()


def list_children(notion_request, block_id: str) -> list[dict]:
    rows: list[dict] = []
    cursor = None
    dashed = block_id.replace("-", "")
    dashed = f"{dashed[:8]}-{dashed[8:12]}-{dashed[12:16]}-{dashed[16:20]}-{dashed[20:]}"
    while True:
        path = f"/blocks/{dashed}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        payload = notion_request("GET", path)
        rows.extend(payload.get("results") or [])
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
    return rows


def load_tree(notion_request, block_id: str) -> list[dict]:
    nodes = []
    for block in list_children(notion_request, block_id):
        node = dict(block)
        if block.get("has_children") and block.get("type") != "code":
            node["children"] = load_tree(notion_request, block["id"])
        else:
            node["children"] = []
        nodes.append(node)
    return nodes


def names_from_title(title: str) -> set[str]:
    text = re.sub(r"\s+", " ", title).strip(" -")
    if not text:
        return set()
    lowered = text.lower()
    if lowered in SKIP_TOGGLE_TITLES | PROMPT_TOGGLE_TITLES:
        return set()
    names = set()
    cleaned = re.sub(r"(?i)\b(from|call|intro|technical round|head of eng|recruiter|with)\b", " ", text)
    cleaned = re.sub(r"\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    if len(cleaned) >= 3:
        names.add(cleaned)
        for part in re.split(r"\s+and\s+|,", cleaned):
            part = part.strip()
            if len(part) >= 3:
                names.add(part)
    match = ROUND_TITLE.match(text)
    if match:
        blob = match.group(1).strip()
        if blob:
            names.add(blob)
    return {item for item in names if item.lower() not in {"from", "call", "intro"}}


def redact(text: str, names: list[str]) -> str:
    redacted = text
    for name in names:
        if not name or len(name) < 3:
            continue
        redacted = re.sub(rf"\b{re.escape(name)}\b", "", redacted, flags=re.I)
    return re.sub(r"[^\S\n]{2,}", " ", redacted).strip(" -,")


def apply_typos(text: str) -> str:
    def repl(pattern: str, replacement: str, blob: str) -> str:
        def swap(match: re.Match) -> str:
            token = match.group(0)
            if token.isupper():
                return replacement.upper()
            if token[0].isupper():
                return replacement[0].upper() + replacement[1:]
            return replacement

        return re.sub(pattern, swap, blob, flags=re.I)

    updated = text
    for pattern, replacement in TYPOS:
        updated = repl(pattern, replacement, updated)
    updated = re.sub(r"\bi\b", "I", updated)
    return updated


def sentence_case(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    pieces = re.split(r"([.?!]\s+)", text)
    out = []
    cap_next = True
    for piece in pieces:
        if not piece:
            continue
        if cap_next and piece[0].isalpha():
            piece = piece[0].upper() + piece[1:]
        out.append(piece)
        cap_next = bool(re.match(r"[.?!]\s+$", piece))
    return "".join(out)


def looks_like_question(text: str) -> bool:
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    return bool(QUESTION_START.match(stripped))


def clean_sentence(text: str, names: list[str]) -> str | None:
    blob = redact(text, names)
    blob = FOLLOW_UP.sub("", blob)
    blob = blob.replace(" / ", " / ")
    blob = re.sub(r"\s+", " ", blob).strip(" -•\t")
    blob = blob.strip("\"'`")
    if blob.endswith(" and"):
        blob = blob[: -len(" and")].rstrip()
    if not blob or blob.lower() in SKIP_TOGGLE_TITLES | PROMPT_TOGGLE_TITLES:
        return None
    if ASKED_ME.match(blob):
        blob = ASKED_ME.sub("", blob)
    elif ASKED_ABOUT.match(blob):
        rest = ASKED_ABOUT.sub("", blob)
        blob = rest if QUESTION_START.match(rest) else f"What about {rest}"
    blob = apply_typos(blob)
    for _ in range(2):
        blob = sentence_case(blob)
        for pattern, replacement in PHRASES:
            blob = re.sub(pattern, replacement, blob, flags=re.I)
        blob = re.sub(r"\s{2,}", " ", blob).strip()
    blob = sentence_case(blob)
    if not blob:
        return None
    if blob[-1] not in ".?!":
        blob += "?" if looks_like_question(blob) else "."
    return blob


def fingerprint(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def dedupe(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique = []
    for item in items:
        key = fingerprint(item.get("title") or "") + " " + fingerprint(item.get("prompt") or "")
        key = key.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def collect_names(nodes: list[dict], into: set[str]) -> None:
    for node in nodes:
        kind = node.get("type")
        title = block_text(node)
        lowered = title.lower().strip()
        if kind == "toggle" and lowered not in SKIP_TOGGLE_TITLES | PROMPT_TOGGLE_TITLES:
            into |= names_from_title(title)
        collect_names(node.get("children") or [], into)


def strip_comment_prefix(line: str) -> str:
    cleaned = line
    while True:
        nxt = re.sub(r"^(\s*)//+\s?", r"\1", cleaned)
        nxt = re.sub(r"^(\s*)#+\s?", r"\1", nxt)
        if nxt == cleaned:
            return cleaned
        cleaned = nxt


def code_prompt(block: dict) -> str:
    body = block.get("code") or {}
    source = "".join(item.get("plain_text") or "" for item in body.get("rich_text") or [])
    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if re.match(r"^(async\s+)?function\s+\w+", stripped) or re.match(r"^class\s+\w+", stripped):
            break
        if stripped and not stripped.startswith(("//", "#", "*", "/*")):
            break
        lines.append(strip_comment_prefix(line).rstrip())
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("` \n")


def prompt_from_nodes(nodes: list[dict]) -> str:
    chunks: list[str] = []
    for node in nodes:
        kind = node.get("type")
        if kind == "code":
            extracted = code_prompt(node)
            if extracted:
                chunks.append(extracted)
            continue
        if kind in SKIP_TOGGLE_TITLES:
            continue
        title = block_text(node)
        if title.lower() in SKIP_TOGGLE_TITLES:
            continue
        if kind in {"heading_1", "heading_2", "heading_3", "paragraph", "quote", "callout", "bulleted_list_item", "numbered_list_item"}:
            if title:
                chunks.append(title)
        children = node.get("children") or []
        if children:
            nested = prompt_from_nodes(children)
            if nested:
                chunks.append(nested)
    return "\n\n".join(chunk for chunk in chunks if chunk).strip()


def display_title(text: str) -> str:
    blob = apply_typos(re.sub(r"\s+", " ", text).strip(" #/.-"))
    if blob.endswith(".") and not blob.endswith("..."):
        blob = blob[:-1]
    words = blob.split()
    if not words:
        return "Technical prompt"
    titled = [words[0][:1].upper() + words[0][1:]]
    for word in words[1:]:
        if word.upper() in TITLE_KEEP_WORDS:
            titled.append(word.upper())
        elif word[:1].isupper() and word.isalpha() and word.lower() in {"react", "typescript"}:
            titled.append(word)
        else:
            titled.append(word.lower())
    return " ".join(titled)


def technical_title(prompt: str) -> str:
    for line in prompt.splitlines():
        stripped = strip_comment_prefix(line).strip().strip("`").lstrip("#").strip()
        lowered = stripped.lower().rstrip(":")
        if not stripped or lowered in GENERIC_TITLE_LINES:
            continue
        if stripped in {"---", "```"} or lowered.startswith(("assume", "example", "expected", "rules")):
            continue
        for pattern, replacement in TITLE_PHRASES:
            if re.match(pattern, stripped, flags=re.I):
                return replacement
        building = re.match(r"(?i)^you'?re building an?\s+(.+?)\s+for\b", stripped)
        if building:
            return display_title(building.group(1))
        given = re.match(r"(?i)^given\b[^,.?!]+,\s*(.+)$", stripped)
        if given:
            return display_title(given.group(1))
        if len(stripped) <= 48 or len(stripped.split()) <= 6:
            return display_title(stripped)
        return display_title(stripped.split(".")[0])
    return "Technical prompt"


def heading_section(title: str, current: str | None) -> str | None:
    lowered = title.lower().strip()
    if "resource" in lowered:
        return None
    for key, label in SECTION_HEADINGS.items():
        if key in lowered:
            return label
    return current


def has_technical_prompt_bits(title: str, children: list[dict]) -> bool:
    lowered = title.lower().strip()
    if lowered in PROMPT_TOGGLE_TITLES:
        return True
    return any(
        block_text(child).lower() in PROMPT_TOGGLE_TITLES | SKIP_TOGGLE_TITLES
        or child.get("type") == "code"
        for child in children
    )


def append_technical_prompt(children: list[dict], names: list[str], buckets: dict[str, list[dict]]) -> None:
    raw = prompt_from_nodes(children)
    if not raw:
        return
    prompt = apply_typos(redact(raw, names))
    if not prompt:
        return
    buckets["technical"].append({"title": technical_title(raw), "prompt": prompt})


def walk(nodes: list[dict], section: str | None, names: list[str], buckets: dict[str, list[dict]]) -> None:
    current = section
    for node in nodes:
        kind = node.get("type")
        title = block_text(node)
        children = node.get("children") or []
        if kind in {"heading_1", "heading_2", "heading_3"}:
            current = heading_section(title, current)
            walk(children, current, names, buckets)
            continue
        if current is None:
            continue
        if kind in {"column_list", "column", "synced_block"}:
            walk(children, current, names, buckets)
            continue
        if kind == "toggle":
            lowered = title.lower().strip()
            if lowered in SKIP_TOGGLE_TITLES:
                continue
            if current == "technical":
                if has_technical_prompt_bits(title, children):
                    preferred = [
                        child
                        for child in children
                        if child.get("type") == "toggle"
                        and block_text(child).lower() in PROMPT_TOGGLE_TITLES
                    ]
                    usable = preferred or [
                        child
                        for child in children
                        if not (
                            child.get("type") == "toggle"
                            and block_text(child).lower() in SKIP_TOGGLE_TITLES
                        )
                    ]
                    append_technical_prompt(usable, names, buckets)
                else:
                    append_technical_prompt(children, names, buckets)
                continue
            walk(children, current, names, buckets)
            continue
        if kind == "code" and current == "technical":
            raw = code_prompt(node)
            prompt = apply_typos(redact(raw, names))
            if prompt:
                buckets["technical"].append(
                    {"title": technical_title(raw), "prompt": prompt}
                )
            continue
        if kind in {"bulleted_list_item", "numbered_list_item", "paragraph", "quote", "to_do"}:
            cleaned = clean_sentence(title, names)
            if cleaned:
                buckets[current].append({"title": cleaned, "prompt": ""})
            walk(children, current, names, buckets)


def previous_questions(data_path: Path) -> dict:
    if not data_path.exists():
        return {"behavioral": [], "technical": []}
    blob = json.loads(data_path.read_text())
    questions = blob.get("questions") or {}
    return {
        "behavioral": list(questions.get("behavioral") or []),
        "technical": list(questions.get("technical") or []),
    }


def as_public(buckets: dict[str, list[dict]]) -> dict:
    behavioral = []
    for item in dedupe(buckets.get("behavioral") or []):
        text = item.get("prompt") or item.get("title") or ""
        if text:
            behavioral.append(text)
    technical = []
    for item in dedupe(buckets.get("technical") or []):
        title = item.get("title") or "Technical prompt"
        prompt = item.get("prompt") or ""
        if not prompt:
            continue
        technical.append({"title": title, "prompt": prompt})
    return {"behavioral": behavioral, "technical": technical}


def question_keys(questions: dict) -> set[str]:
    keys = {fingerprint(item) for item in questions.get("behavioral") or []}
    for item in questions.get("technical") or []:
        if isinstance(item, dict):
            keys.add(fingerprint(item.get("title") or "") + " " + fingerprint((item.get("prompt") or "")[:180]))
        else:
            keys.add(fingerprint(str(item)))
    return {key for key in keys if key}


def load_questions_from_notion(notion_request) -> dict:
    tree = load_tree(notion_request, QUESTIONS_PAGE)
    found: set[str] = set()
    collect_names(tree, found)
    names = sorted(found, key=len, reverse=True)
    buckets: dict[str, list[dict]] = {"behavioral": [], "technical": []}
    walk(tree, None, names, buckets)
    public = as_public(buckets)
    QUESTIONS_SNAPSHOT.write_text(json.dumps(public, indent=2) + "\n")
    return public


def load_questions_from_snapshot(data_path: Path) -> dict:
    if QUESTIONS_SNAPSHOT.exists():
        return json.loads(QUESTIONS_SNAPSHOT.read_text())
    return previous_questions(data_path)
