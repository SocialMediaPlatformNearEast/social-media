# LvL Social OAuth Setup

App-side OAuth is wired for the built-in Supabase social providers:

- Google
- Facebook
- Apple
- Azure / Microsoft
- X / Twitter
- GitHub
- GitLab
- Bitbucket
- Discord
- Figma
- Kakao
- Keycloak
- LinkedIn
- Notion
- Slack
- Spotify
- Twitch
- WorkOS
- Zoom

## Required Supabase Setup

1. Run `database/migrations/005_oauth_identity.sql` in the Supabase SQL editor.
2. In Supabase Dashboard, open `Authentication > URL Configuration`.
3. Add the app callback URL to allowed redirects:
   - Local: `http://127.0.0.1:5051/auth/oauth/callback`
   - Production: `https://<your-production-domain>/auth/oauth/callback`
4. In `Authentication > Providers`, enable each provider and enter its Client ID and Client Secret.
5. In each provider developer console, use the callback URI shown by Supabase for that provider. It usually looks like:
   - `https://<project-ref>.supabase.co/auth/v1/callback`

## App Flow

- `/auth/oauth/<provider>` starts Supabase OAuth.
- `/auth/oauth/callback` exchanges the returned code and connects the Supabase Auth user to `public.users`.
- Existing LvL accounts are matched by `supabase_auth_user_id`, provider subject, then email.
- New social users finish `/auth/oauth/onboarding` before the app creates a `public.users` row.
- The onboarding form keeps LvL rules for nickname, gender, and birthday, including the 14+ age limit.

Do not store provider access tokens in `public.users`. Supabase returns provider tokens during the OAuth session, but LvL only stores identity-linking fields.
