# SteppingStone AI: Operation Manual

## Mission
- Trusted parent commerce advisor where developmental progress, safety, and shopping meet.
- Developmental scout for "Clean Swap" non-toxic and wooden toys.
- User: Parents of children from 0 to 3 years old.

## Product North Star
- Help parents choose toys and activities through CDC-informed developmental fit, material safety, and trustworthy commerce guidance.
- Treat product trust, parent memory, safety scoring, clean-swap verdicts, verified product data, affiliate transparency, and distribution loops as core product surfaces.
- The app should feel like an advisor, not a generic AI toy search box.

## Tech Stack
- Logic: OpenAI SDK with `gpt-4o`.
- UI: Flask-rendered HTML/CSS served by Gunicorn.
- Deployment: Railway.app with `web: gunicorn app:app`.

## Guardrails
- Always use tracking tag `{{AMAZON_ID}}` for links.
- Priority brands: Lovevery, Hape, PlanToys, Melissa & Doug.
- Never suggest plastic junk or unverified safety brands.
- Show why a recommendation is safer: age fit, material quality, small-parts/choking concern, brand trust, developmental match, and overstimulation risk.
- Keep affiliate disclosure visible and plain.
- Secrets must never be committed to GitHub. Use Railway environment variables for production and local environment variables only for testing.

## Codex Workflow
- Do not ask the user whether to continue after routine implementation steps.
- After code changes, compile and run the relevant checks until everything succeeds.
- Only interrupt the user when a run fails or a blocker appears.
- When a run fails, investigate the likely break point, fix it if possible, and rerun verification before reporting back.
- Before pushing deployment changes, verify locally first and keep unrelated local files out of the commit.
- Do not add Streamlit imports, Streamlit commands, or Streamlit secrets for this project.
