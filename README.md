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

## Stack

- Static site: `index.html`, `styles.css`, `app.js`, `data.json`, unlisted `hidden/`
- Python 3 stdlib generator (`scripts/generate.py`) — no pip deps
- Notion API (read-only internal integration)
- GitHub Actions (daily snapshot)
- Netlify (serves `main`, no build)

## How it fits together

1. **Notion** holds Applications, Companies, and Meetings. The integration named **job game** has read access only. Nothing in this repo writes back.
2. **`scripts/generate.py`** queries those data sources, applies the public filters, strips private fields, and writes `data.json`. It also writes `hidden/data.json` with real company names for the unlisted alias key. New companies get the next alias; old numbers never reshuffle (`scripts/aliases.json`).
3. **GitHub Action** `.github/workflows/refresh-snapshot.yml` runs that script daily at 09:00 EST (14:00 UTC; 10:00 EDT) and on **Run workflow**. It commits `data.json`, `aliases.json`, and `hidden/data.json` whenever those files change, including a fresh `generatedOn` date on each run. After a push, [Textbelt](https://textbelt.com/) sends an SMS if the snapshot content changed (not a date-only stamp).
4. **Netlify** is linked to this GitHub repo. A push to `main` publishes the static files. Publish directory is `.`; there is no build command.
5. **The browser** fetches `./data.json` and renders counts plus three tabs (Meetings, Applications, Companies). The first visit is a clean URL on Meetings. A tab click, Tab to a tab then Enter/Space, or Left/Right/Home/End on the tab list sets `?tab=meetings`, `?tab=applications`, or `?tab=companies`. Each table shows 10 rows, then loads 10 more as you scroll that table. The footer is the filtered total. **How I built this** describes the stack and snapshot rules in Sammy's voice. Last is **Projects I've built while job searching**, with Clock In With Toons (`clockin.png`). Unlisted `/hidden` loads `hidden/data.json` and lists alias → name plus related applications and meetings. It is not linked from the homepage.

Inclusion rules for the public snapshot:

- Meetings: **fin | job game 2026** view (date before today, `jobs` tag, linked to Job Game 2026). Kind is onsite, technical, intro, recruiter, or other. The `jobs` tag is the view filter, not a public label.
- Applications: Job Game 2026 Applications **Submitted** view (status group Complete: Submitted and Archived). Recruiter and referral counts are whether those relation columns are filled.
- Companies (table): last edited on or after **2026-09-11**, and status is one of Finding role..., Applied, Interviewing, Take-Home, Negotating/Negotiating, Interviewed

## What is running

| Piece | Status |
| --- | --- |
| Site | Live at https://jbg.sammy.pizza |
| Netlify | `job-game-2026`, deploys from `main` |
| Daily refresh | GitHub Action **Refresh snapshot**, 09:00 EST (14:00 UTC) |
| SMS | Textbelt on content change (not `generatedOn`-only) |
| Notion | Read-only integration; token is repo secret `NOTION_TOKEN` |

Nothing else is a long-running server.

## Local

```bash
python3 -m http.server 4173
```

Open http://localhost:4173. The unlisted alias key is http://localhost:4173/hidden. Browsers block `fetch` on raw `file://` pages.

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
