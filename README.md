# Job Game 2026

Public, anonymized log of this job search. Notion stays private and is only read.

## Local

```bash
python3 -m http.server 4173
```

Then visit `http://localhost:4173`.

Regenerate from local snapshots (no Notion token):

```bash
python3 scripts/generate.py
```

## Daily refresh

A GitHub Action runs every day at 12:00 UTC (`workflow_dispatch` also works). It reads Applications, Companies, and Meetings through a Notion internal integration, writes anonymized `data.json`, and commits if anything besides the date changed.

1. Create a [Notion integration](https://www.notion.so/profile/integrations) with **Read content** only.
2. Share the Applications, Companies, and Meetings databases with that integration.
3. Add the token as the `NOTION_TOKEN` repository secret.
4. Optional: add `NETLIFY_AUTH_TOKEN` so the same workflow can deploy. Otherwise connect the GitHub repo in the Netlify UI.
