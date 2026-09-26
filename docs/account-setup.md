# Account and child-profile setup

This milestone uses Supabase Auth and one `child_profiles` row per account. Public
activity discovery continues to work when account configuration is absent.

## 1. Create the data boundary

1. Create a Supabase project.
2. Open its SQL editor.
3. Run `migrations/001_child_profiles.sql` once.
4. In Authentication → URL Configuration, set the Site URL to the deployed Nurtured URL.
5. Keep email confirmation enabled for production.

The migration enables row-level security. The browser-visible anon key cannot read
or change another account's profile because every policy compares `auth.uid()` with
`owner_id`.

## 2. Configure Railway

Add these service variables. Never commit their values:

- `SUPABASE_URL`: Project Settings → API → Project URL
- `SUPABASE_ANON_KEY`: Project Settings → API → anon/public key
- `FLASK_SECRET_KEY`: a stable random secret, at least 32 bytes

Generate the Flask key locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not use the Supabase service-role key. The server intentionally makes profile
requests with each user's access token so row-level security remains the authorization
boundary.

## 3. Verify before production use

1. Create an account with a real email.
2. Confirm the email and sign in.
3. Save a child age band and optional nickname/interests/setting.
4. Confirm the dashboard shows matching catalog activities.
5. Sign out, then verify `/dashboard` redirects to `/login`.
6. Sign into a second account and confirm it cannot see the first profile.

Authentication is enabled only when all three environment variables exist. Without
them, the previous honest “Accounts are coming soon” experience remains active.
