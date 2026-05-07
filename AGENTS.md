# SteppingStone AI: Operation Manual

## Mission
- Developmental scout for "Clean Swap" non-toxic and wooden toys.
- User: Parents of children from 0 to 3 years old.

## Tech Stack
- Logic: Google GenAI SDK.
- UI: Streamlit, run with `streamlit run app.py`.
- Deployment: Railway.app.

## Guardrails
- Always use tracking tag `{{AMAZON_ID}}` for links.
- Priority brands: Lovevery, Hape, PlanToys, Melissa & Doug.
- Never suggest plastic junk or unverified safety brands.
- Secrets must never be committed to GitHub. Use Railway environment variables for production and local secrets only for testing.

## Codex Workflow
- Do not ask the user whether to continue after routine implementation steps.
- After code changes, compile and run the relevant checks until everything succeeds.
- Only interrupt the user when a run fails or a blocker appears.
- When a run fails, investigate the likely break point, fix it if possible, and rerun verification before reporting back.
- Before pushing deployment changes, verify locally first and keep unrelated local files out of the commit.
