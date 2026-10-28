# Job Game 2026

Public, anonymized log of this search. Company names, people, recruiters, and URLs stay in Notion. The site shows numbered aliases (`Company 01`, …).

Live: [jbg.sammy.pizza](https://jbg.sammy.pizza) · repo: [ssamkough/job-game](https://github.com/ssamkough/job-game)

## Contents

- [Projects](#projects)
- [Stack](#stack)
- [How it fits together](#how-it-fits-together)
- [What is running](#what-is-running)
- [Local](#local)
- [Secrets and privacy](#secrets-and-privacy)
- [Netlify build settings](#netlify-build-settings)

## Projects

| Project | URL | Role |
| --- | --- | --- |
| Job Game 2026 | [jbg.sammy.pizza](https://jbg.sammy.pizza) | This repo — public search log |
| Clock In With Toons | [clockin.sammy.pizza](https://clockin.sammy.pizza/) | Video rooms with chat and a shared whiteboard |
| Long Island Events | [lievents.sammy.pizza](https://lievents.sammy.pizza/) | Weekly events from nearby village calendars |

## Stack

- Static site: `index.html`, `styles.css`, `app.js`, `data.json`, `/questions`, `/prep`, unlisted `hidden/`
- Python 3 stdlib generator (`scripts/generate.py`) — no pip deps
- Notion API (read-only internal integration)
- GitHub Actions (daily snapshot)
- Netlify (serves `main`, no build)

## How it fits together

1. **Notion** holds Applications, Companies, Meetings, and the **job game 2026 Asked Questions** page. The integration named **job game** has read access only. Nothing in this repo writes back.
2. **`scripts/generate.py`** queries those data sources, applies the public filters, strips private fields, and writes `data.json`. It also writes `hidden/data.json` with real company names for the unlisted alias key. New companies get the next alias; old numbers never reshuffle (`scripts/aliases.json`). Asked questions are anonymized (no company or people names), cleaned, and deduped into `data.json`.
3. **GitHub Action** `.github/workflows/refresh-snapshot.yml` runs that script daily at 09:00 EST (14:00 UTC; 10:00 EDT) and on **Run workflow**. It commits `data.json`, `aliases.json`, and `hidden/data.json` whenever those files change, including a fresh `generatedOn` date on each run. After each successful run, [Textbelt](https://textbelt.com/) texts a summary (applications, meetings, how calls came in, companies, questions) even if the snapshot did not change. The text omits URLs (unverified Textbelt keys cannot send links).
4. **Netlify** is linked to this GitHub repo. A push to `main` publishes the static files. Publish directory is `.`; there is no build command.
5. **The browser** fetches `./data.json` and renders counts (Meetings, Screens, Recruiters; Technicals, Onsites, Behaviorals; Companies, Applications, Referrals), a Highlights list of how public meetings came in (application, recruiter, referral), plus three tabs (Meetings, Applications, Companies). The first visit is a clean URL on Meetings. A tab click, Tab to a tab then Enter/Space, or Left/Right/Home/End on the tab list sets `?tab=meetings`, `?tab=applications`, or `?tab=companies`. Each table shows 10 rows, then loads 10 more as you scroll that table. The footer is the filtered total. **How I built this** describes the stack and snapshot rules in Sammy's voice. Last is **Projects I've built while job searching**: Job Game 2026, Clock In With Toons (`clockin.png`), and Long Island Events (`lievents.png`). **Questions** (`/questions`) lists technical prompts first (each in its own disclosure), then anonymized behavioral questions. **Prep** (`/prep`) links to system design and technical knowledge. Unlisted `/hidden` loads `hidden/data.json` and lists alias → name plus related applications and meetings. It is not linked from the homepage.

Inclusion rules for the public snapshot:

- Meetings: **fin | job game 2026** view (date before today, `jobs` tag, linked to Job Game 2026). Kind is onsite, technical, intro, recruiter, behavioral, or other. The `jobs` tag is the view filter, not a public label. Screens are meetings tagged recruiter or intro, or with recruiter/intro/screen in the title. Technicals, onsites, and behaviorals count those tags. Highlights count those meetings with `app <-> meeting`, `recruiters <-> meetings`, or `colleagues <-> meetings` filled. Recruiter sub-counts use List of Recruiters: `firm` filled means third-party; `inbound?` is inbound vs outreach / existing connection. Recruiter total is List of Recruiters rows with `currently?` checked.
- Applications: Job Game 2026 Applications **Submitted** view (status group Complete: Submitted and Archived). Referral counts are whether that relation column is filled.
- Companies (table): last edited on or after **2026-09-11**, and status is one of Finding role..., Applied, Interviewing, Take-Home, Negotating/Negotiating, Interviewed
- Questions: **job game 2026 Asked Questions** page, Behavioral and Technical only. Company names and people are stripped. Notes after those headings count even if they are not nested under the heading. Technical round notes without a code/readme toggle become one disclosure, titled with a short summary of the prompt. Solutions/code toggles are omitted. Duplicates are dropped.

## What is running

| Piece | Status |
| --- | --- |
| Site | Live at https://jbg.sammy.pizza |
| Netlify | `job-game-2026`, deploys from `main` |
| Daily refresh | GitHub Action **Refresh snapshot**, 09:00 EST (14:00 UTC) |
| SMS | Textbelt after every successful refresh |
| Notion | Read-only integration; token is repo secret `NOTION_TOKEN` |

Nothing else is a long-running server.

## Local

```bash
python3 -m http.server 4173
```

Open http://localhost:4173. Questions is http://localhost:4173/questions. Prep is http://localhost:4173/prep. The unlisted alias key is http://localhost:4173/hidden. Browsers block `fetch` on raw `file://` pages.

Without `NOTION_TOKEN`, the generator uses gitignored snapshots in `scripts/` (`applications.json`, `companies.json`, `meetings.json`). With the token:

```bash
NOTION_TOKEN=… python3 scripts/generate.py
```

## Secrets and privacy

- **`NOTION_TOKEN`** — GitHub Actions secret. Read content only. Never expose it to the browser or commit it.
- **`TEXTBELT_KEY`** — Textbelt key (`textbelt` for 1 free SMS/day, or a paid key).
- **`SMS_TO`** — Phone number to text. SMS is skipped if either secret is missing.
- Public `data.json` has no Notion URLs, names, or people. `aliases.json` maps page ids → numbers only.
- Unlisted `/hidden` (`hidden/data.json`) includes real company names. The repo and Netlify site are public, so this is not a secret — only unlinked. `robots.txt` disallows `/hidden`.
- Raw Notion dumps and local `.env` stay gitignored.

## Netlify build settings

Branch `main`. Base directory empty. Build command empty. Publish directory `.`. No functions.
