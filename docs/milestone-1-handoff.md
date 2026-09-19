# Nurtured — Milestone 1 handoff

Implemented on `codex/milestone-1-revamp` in the existing Flask application.
Production and Railway configuration have not been changed or deployed.

## Delivered

- Reference-led cream/forest/sage homepage with editorial serif hero, handwritten
  emphasis, rounded photography/badges, white discovery panel, six pastel categories,
  four-card desktop activity row, three-card kits band, compact benefits, closing
  account invitation, and footer. Mobile reflows into two-column categories and
  single-column activity/kit cards; intermediate widths use two activity columns.
- Functional guest discovery over 12 explicitly identified development fixtures:
  keyword, age overlap, kind, OR interests, maximum time/cost, setting, and category
  tags combine deterministically. Counts, chips, removal, reset, empty states,
  complete results, reload, browser history, and accessible activity-detail pages work.
- Guest/editorial and submitted-preference copy are distinct. Public browsing
  never reads existing private browser profiles, calls a model, or writes event logs.
- All category tiles have actions. Gift Finder explains that shopping is coming
  later and opens the kits preview. Kits use illustrative photos and have no price,
  customization, cart, checkout, testing claims, or shipping promises.
- Small informational agent dialog with example prompts, explicit Coming soon
  status, focus containment, Escape, and focus return. No Send control or simulated reply.
- Shared Flask templates/macros and CSS tokens support the public and dashboard
  layouts. SVG icons and local, responsive 600/1200px photos avoid remote assets/fonts.
  Hero loads eagerly; below-the-fold images load lazily with explicit dimensions/crops.
- Public login/Get Started screens state that accounts are unavailable and link to
  working discovery. `/dashboard` is rejected server-side with 401. The development
  dashboard includes account navigation, welcome, disabled preference-setup example,
  and shared cards; `/dev/dashboard` returns 404 unless debug AND explicit preview
  configuration are enabled. No password or session is fabricated, and no profile
  information is saved.
- Existing advisor source, milestones, product catalog, browser storage conventions,
  lead/event stores, guide routes, outbound redirects, and root POST compatibility are
  preserved. The legacy advisor GET is now `/legacy/advisor`; new public UI does not
  expose its unscoped commerce/developmental features.

## Files

| Area | Changed / added files |
| --- | --- |
| Integration | `app.py` (blueprint and legacy GET route), `public_site.py` |
| Contracts / logic | `discovery.py`, `activity_catalog.py`, `accounts.py` |
| Components / pages | `templates/base.html`, `components.html`, `home.html`, `explore.html`, `activity_detail.html`, `auth.html`, `dashboard.html`, `error.html` |
| Visual system | `static/site.css`, `static/site.js`, `static/favicon.svg`, `static/images/*` |
| Verification / preview | `tests/test_milestone.py`, `tests/browser_check.py`, `preview.py` |
| Documentation | `README.md`, this handoff, `milestone-1-audit.md`, `image-credits.md`, `screenshots/*` |

## Verification

- Baseline: Python compilation passed. Initial dependency absence was resolved in
  a local virtual environment. Before route changes, GET `/`, empty POST `/`, a
  known guide, unknown-guide redirect, and invalid affiliate redirect all passed.
- 21 focused unittest checks pass: group combinations, OR interests, inclusive age
  overlap, time/budget maximums, case-insensitive keyword matching, empty states,
  query roundtrip, option sanitization, escaping, private-field exclusion from
  generated URLs, details/images, auth unavailability, forged-auth rejection,
  development-preview gating, and preserved legacy routes with isolated log files.
- Python compilation and JavaScript syntax validation pass. No build/lint/type
  configuration existed in the repository; no frontend build step was introduced.
- Automated Chromium/Edge browser checks pass at 360, 390, 768, 1024, and 1440px
  with no horizontal page overflow or broken images. All six categories, filter
  combinations, reload, Back/Forward, chips, reset, full results, and detail return
  are exercised. Mobile navigation, keyboard skip link, dialog Tab containment,
  Escape/focus return, and reduced motion are exercised. Navigation/discovery/detail
  fallback is exercised with JavaScript disabled.
- Normal public pages have no new console errors. The intentional 401 dashboard
  and 404 development-boundary probes produce expected HTTP console messages.
- Checked text/action contrast pairs exceed 4.5:1: body 12.00, muted copy 5.45,
  action button 9.21, sage copy 5.42, category copy 6.22. These checks are not a claim
  of a full assistive-technology or cross-browser certification.
- Final browser results are recorded in `screenshots/verification.json`.

## Screenshots and reference comparison

- [Desktop 1440](screenshots/home-1440.png)
- [Mobile 390 full page](screenshots/home-390.png) / [first screen](screenshots/home-390-first-screen.png)
- [360](screenshots/home-360.png), [768](screenshots/home-768.png), [1024](screenshots/home-1024.png)
- [Filtered results](screenshots/filtered-1440.png), [empty state](screenshots/empty-state-1440.png), [activity detail](screenshots/activity-detail-1440.png)
- [Agent](screenshots/agent-390.png), [login](screenshots/login-390.png), [Get Started](screenshots/get-started-390.png)
- [Public dashboard denial](screenshots/dashboard-unavailable-390.png), [development dashboard desktop](screenshots/dashboard-dev-1440.png), [development dashboard mobile](screenshots/dashboard-dev-390.png)

The supplied central design was inspected before implementation. Desktop retains
its left-copy/right-photo composition, green script emphasis, rounded photography,
discovery → six categories → four cards → sage kits order, benefit strip, banner,
and understated footer. Mobile retains the same treatments with stacked sections
and readable form controls. The implementation is taller than the compressed
reference because filters, cost meanings, preview disclosures, and touch targets
are real readable controls. The hero uses a similar licensed stock photograph;
it is not an exact match. Kit photographs show inspiration rather than specific
finished products. Original brand spelling differences are retained in legacy
source and documented; the new public product is Nurtured. Phone/message chrome,
carousel edges, and the floating banana are excluded.

## Live, fixtures, and remaining dependencies

**Working application behavior:** public navigation, deterministic local discovery,
URL state, detail views, category links, preview/info panels, and server-side denial
of unavailable account routes. This describes locally verified code, not a production
deployment. No real account system is working in this milestone.

**Fixture-backed:** all 12 activities, estimated USD costs, three kit concepts, and
development dashboard/setup examples. Activities are not professionally reviewed.
Outing admission is for one adult and one child; it is an illustrative estimate,
not a live price, booking, event listing, or location lookup.

**Missing:** an actual account provider and authorized profile service. Production
environment values and existing production records were not accessed. Login/signup
success, verification, password recovery, logout, and account-owned persistence
cannot be exercised without that integration. No paid provider was selected.

**Deferred:** activity review/publication workflow, privacy/terms/contact destinations
(none existed, so none were invented), consent/deletion implementation, AI safety
and cost controls, approved kit options, commerce, memberships, and the full dashboard.
Legacy paid model behavior was not called; baseline/regression checks use no live
model and temporary event/lead paths. Safari/Firefox and a dedicated screen-reader
audit were not run.
