# Nurtured

Flask public activity discovery and the preserved legacy parent advisor.

## Local preview

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe preview.py
```

Open `http://127.0.0.1:8080`. Public browsing requires no API key or account.
To view the clearly labeled development dashboard, run `preview.py --dashboard-fixtures`
and open `/dev/dashboard`. The preview binds to loopback, disables the debugger,
and does not change production availability. `/dashboard` always returns 401 until
a real account provider is integrated; login/signup currently explain unavailability.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app.py public_site.py discovery.py accounts.py activity_catalog.py
node --check static/site.js
```

Optional browser verification uses Playwright and installed Microsoft Edge:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe tests/browser_check.py
```

It starts a temporary loopback server and writes screenshots/results to
`docs/screenshots`. Playwright is only a development tool, not an application dependency.

## Boundaries

- `public_site.py`, `templates/`, and `static/`: responsive public experience.
- `discovery.py`: typed contracts, centralized taxonomies, URL state, and pure filtering.
- `activity_catalog.py`: 12 development fixtures and three illustrative kit concepts.
- `accounts.py`: explicitly unavailable provider and feature-availability boundary.
- `app.py`: Flask entry point and preserved legacy advisor at `/legacy/advisor`;
  existing root POST, guide, event, and affiliate redirect routes remain available.
- Railway/Gunicorn configuration is unchanged. No deployment, database changes,
  provider selection, or model integration is part of Milestone 1.

The old README called this `NUTUREAI`; the repository and legacy UI have historical
spelling differences documented in the audit. The public product name is Nurtured.

See [handoff and limitations](docs/milestone-1-handoff.md),
[repository audit](docs/milestone-1-audit.md), and [image credits](docs/image-credits.md).

## Optional accounts and personalization

The next logic layer adds Supabase email/password accounts, one child-preference
profile per account, and deterministic dashboard recommendations. Public discovery
still works without account configuration. Follow
[the account setup guide](docs/account-setup.md) and run
`migrations/001_child_profiles.sql` before enabling the three Railway variables.
