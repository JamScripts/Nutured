# Milestone 1 repository audit and implementation plan

Audited 2026-09-19 against `JamScripts/Nutured`, commit `f6afb7e`.
Local branch: `codex/milestone-1-revamp`. This records the initial audit; implementation and verification are covered in `milestone-1-handoff.md`.

## Existing application

- Python Flask application, with the page embedded in `app.py` as `PAGE_TEMPLATE` and rendered using `render_template_string`. Flask/Jinja macros, templates, CSS, and modest JavaScript can deliver the requested reusable interface without a framework migration.
- Dependencies: `flask`, `gunicorn`, `openai`; unpinned `requirements.txt`, no lockfile or frontend build tooling. No existing automated tests, lint configuration, or type checker configuration found.
- Railway uses RAILPACK and `gunicorn app:app --bind 0.0.0.0:$PORT`; `/` is the healthcheck. `Procfile` agrees. Keep this deployment configuration.
- Existing routes: `/` GET/POST (advisor), `/event` POST (local event logging), `/go` GET (validated Amazon redirect and logging), and `/guides/<slug>` GET (five editorial guides).
- Environment-variable names read by source: `OPENAI_API_KEY`, `AMAZON_ID`, `PORT`. No secret values were inspected. Production configuration was not inspected and cannot be inferred from source.
- Existing server-side OpenAI integration generates shopping recommendations and activity missions. `trusted_catalog.py` contains toy/product records, not the structured activity catalog required by this milestone. `milestones.py` contains milestone context. Preserve these modules; do not use their marketing/safety claims as approval of new activity fixtures.
- No authentication provider, session implementation, account registration, database client, or authorized profile persistence found. There is no evidence of existing server-side accounts in this checkout. Production data was not accessed.
- Current preference fields use browser localStorage under `nurture_profile_...`; lead and event submissions append to ignored `nurture_leads.jsonl` and `nurture_events.jsonl`. Preserve existing stores without importing private fields into public search URLs, fixtures, or new personalization claims. These files are not an account/profile service.
- Existing report-copy, affiliate redirect, guide, advisor, and event flows need regression checks when routing changes. No live model calls or external submissions were performed during this audit.
- Branding discrepancy: repository name is `Nutured`, README says `NUTUREAI`, the current UI says `Nurture`, and the static `index.html` says `SteppingStone AI`. The current mark is a CSS-rendered letter N, not an image asset. Retain the original source/mark; use the requested Nurtured product name in the new public experience and flag this historical inconsistency.
- No local photos, font files, or standalone logo assets found. Current UI loads Google-hosted Inter and Quicksand. No contact/privacy/terms destinations found; do not invent them.
- `AGENTS.md` describes an older commerce/advisor product. The supplied milestone explicitly controls conflicting product scope, including honest kits/AI previews and no new commerce implementation.

## Baseline verification

- Git checkout clean before audit; branch created from the current remote main.
- `python -m compileall -q app.py milestones.py trusted_catalog.py`: passed.
- Runtime import probe: blocked because the available Python environment lacks Flask (`ModuleNotFoundError`). No dependency installation attempted yet. This is an environment blocker, not evidence of an application regression.
- No repository-provided build/lint/test commands found. HTTP, browser, model-provider, production, and visual checks have not been run.

## Required input

Resolved: the user subsequently supplied `codex-clipboard-df6fae42-da28-41f7-9b43-203631e2e51a.png`. Its central website design was inspected before implementation. The original attachment contained only milestone text and its `/workspace/scratch/...` path referred to another environment. The screenshot's phone and messaging UI, surrounding carousel, and banana icon are excluded.

## Implementation plan after reference inspection

1. Install existing dependencies into a local virtual environment and record repeatable baseline route checks with the model client disabled and log writes isolated to temporary paths. Preserve Railway configuration. Keep the existing advisor implementation accessible through an explicitly legacy route while replacing the public homepage; preserve existing guide, redirect, logging, and root POST compatibility without wiring the new discovery form to them.
2. Extract shared Jinja layout/macros, design tokens, and static styles/scripts. Preserve the original brand mark source. Match the reference's composition with rights-cleared local imagery and responsive layouts.
3. Build the homepage sections in the requested order. Define centralized taxonomies and typed Python contracts for activities, preferences, child-profile context, kit previews, recommendation results, and actual feature availability. Use a catalog adapter with at least 12 clearly labeled development fixtures because no suitable activity source exists.
4. Implement pure deterministic filtering and URL parsing/serialization. Prefer a standard GET discovery form so reload and browser history work naturally. Combine groups with AND, interests with OR, use age overlap, and treat time/cost as maximums. Render count, removable chips, reset, empty state, all-results access, and shared activity cards/details.
5. Wire category actions; add three honest kit concepts and an accessible informational agent launcher. Keep AI and commerce disabled in the new milestone experience.
6. Add `/login` and `/get-started` unavailable-state views and a provider boundary. Do not collect passwords or invent sessions. Deny public `/dashboard` access server-side; show the reusable dashboard/setup layout only through an explicit development-only preview, using fixtures and no save claims.
7. Add focused filtering, query-state, and dashboard-boundary tests. Exercise preserved legacy routes without paid model calls. Verify keyboard/focus/overlay behavior, image loading, console errors, contrast, and 360/390/768/1024/1440px overflow. Capture desktop/mobile screenshots and compare against the supplied image.
8. Deliver changed files, screenshots, checks, fixture/live status, and limitations. Do not deploy to production or change data stores as part of this milestone without separately authorized deployment scope.

## Deferred dependencies

Account provider configuration, authorized profile persistence, production activity review, approved kit templates, AI safety/cost controls, consent/deletion work, and commerce remain outside this implementation. No live account system can be claimed from UI completion alone.
