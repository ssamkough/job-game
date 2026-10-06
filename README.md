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

## Stack

- Static site: `index.html`, `styles.css`, `app.js`, `data.json`
- Python 3 stdlib generator (`scripts/generate.py`) — no pip deps
- Notion API (read-only internal integration)
- GitHub Actions (daily snapshot)
- Netlify (serves `main`, no build)

## How it fits together

1. **Notion** holds Applications, Companies, and Meetings. The integration named **job game** has read access only. Nothing in this repo writes back.
2. **`scripts/generate.py`** queries those data sources, applies the public filters, strips private fields, and writes `data.json`. New companies get the next alias; old numbers never reshuffle (`scripts/aliases.json`).
3. **GitHub Action** `.github/workflows/refresh-snapshot.yml` runs that script daily at 12:00 UTC (and on **Run workflow**). If the snapshot changed, it commits `data.json` + `aliases.json`.
4. **Netlify** is linked to this GitHub repo. A push to `main` publishes the static files. Publish directory is `.`; there is no build command.
5. **The browser** fetches `./data.json` and renders counts plus three tabs (Meetings, Applications, Companies). Each table shows 10 rows, then loads 10 more as you scroll that table. The footer is the filtered total.

Inclusion rules for the public snapshot:

- Meetings: created on or after **2026-09-11**, or linked to the Job Game 2026 activity
- Applications: every row in the Job Game 2026 Applications table
- Companies (table): last edited on or after **2026-09-11**, and status is one of Finding role..., Applied, Interviewing, Take-Home, Negotating/Negotiating, Interviewed

## What is running

| Piece | Status |
| --- | --- |
| Site | Live at https://jbg.sammy.pizza |
| Netlify | `job-game-2026`, deploys from `main` |
| Daily refresh | GitHub Action **Refresh snapshot**, 12:00 UTC |
| Notion | Read-only integration; token is repo secret `NOTION_TOKEN` |

Nothing else is a long-running server.

## Local

```bash
python3 -m http.server 4173
```

Open http://localhost:4173. Browsers block `fetch` on raw `file://` pages.

Without `NOTION_TOKEN`, the generator uses gitignored snapshots in `scripts/` (`applications.json`, `companies.json`, `meetings.json`). With the token:

```bash
NOTION_TOKEN=… python3 scripts/generate.py
```

## Secrets and privacy

- **`NOTION_TOKEN`** — GitHub Actions secret. Read content only. Never expose it to the browser or commit it.
- Public JSON has no Notion URLs, names, or people. `aliases.json` maps page ids → numbers only.
- Raw Notion dumps stay gitignored.

## Netlify build settings

Branch `main`. Base directory empty. Build command empty. Publish directory `.`. No functions.
