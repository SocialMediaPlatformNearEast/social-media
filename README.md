# LvL

LvL is a leveling-first social media web application built with Python Flask, Supabase (PostgreSQL), and deployed on Vercel. It includes accounts, profiles, posts, comments, likes, reposts, follows, friend requests, direct messages, notifications, search, and an XP/rank system that makes social activity part of the core product loop.

## Tech Stack

- **Backend:** Python 3.9+ / Flask
- **Database:** Supabase (PostgreSQL, accessed via `supabase-py`)
- **Deployment:** Vercel (Serverless)
- **Frontend:** HTML5, Jinja2, Vanilla CSS, Vanilla JavaScript

## Features

- Register and log in with Flask sessions
- Passwords stored with `bcrypt`
- Create text posts up to 280 characters with optional image uploads
- Comment threads
- Likes and reposts
- Follow and unfollow users
- Send, accept, and decline friend requests
- Direct messages
- Message polling for near-live chat refresh
- Notifications for likes, reposts, comments, follows, friend requests, friend accepts, and messages
- Search posts and people
- User profile pages with editable profile details
- Profile preview before saving profile edits
- Report, mute, and block safety controls
- First-run onboarding for new accounts
- Default illustrated avatars and theme colors based on gender
- Community timelines for Followers, Following, and Community
- XP, levels, badges, and activity titles
- PWA support (manifest, service worker)

## Project Structure

```text
social-media-main/
├── app.py                  Flask entry point (Vercel serverless function)
├── vercel.json             Vercel deployment configuration
├── requirements.txt        Python dependencies
├── .gitignore              Git ignore rules
├── README.md               This file
│
├── templates/              Jinja2 HTML templates
│   ├── layout.html         Base layout (nav, shell, right rail)
│   ├── auth.html           Login and registration
│   ├── index.html          Home feed
│   ├── profile.html        User profile page
│   ├── post.html           Single post with comments
│   ├── messages.html       Direct messages
│   ├── notifications.html  Notifications
│   ├── search.html         Search posts and people
│   ├── settings.html       Edit profile
│   └── community.html      Community metrics
│
├── static/                 Frontend assets
│   ├── css/
│   │   ├── styles.css      CSS import manifest
│   │   ├── gender.css      Avatar and gender picker styles
│   │   └── sections/       Section-focused CSS modules
│   ├── js/
│   │   └── script.js       Client-side UI behavior
│   ├── assets/
│   │   ├── default-male-avatar.svg
│   │   └── default-female-avatar.svg
│   ├── manifest.json       PWA manifest
│   └── service-worker.js   PWA service worker
│
├── database/
│   ├── community_schema.sql Community tables for Supabase/PostgreSQL
│   ├── migrations/          Supabase/PostgreSQL migration files
│   └── legacy/
│       └── mysql_schema.sql Archived MySQL schema, not used by Flask app
│
├── tests/
│   ├── test_app_routes.py   Route/helper tests
│   └── test_supabase.py     Optional Supabase smoke test
│
├── docs/
│   ├── AI_GUIDELINES.md    Technical guidelines for AI tools
│   ├── PROJECT_SEPARATION.md
│   └── TODO.md             Feature backlog
│
└── legacy/
    ├── archived-root/       Old root-level PHP/MySQL/XAMPP files
    ├── archived-static/     Old duplicate static files
    └── php-xampp-version/   Older PHP/MySQL/XAMPP snapshot
```

## Local Development

1. Create a `.env` file in the project root:

   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SECRET=your-service-role-key
   FLASK_SECRET_KEY=your-secret-key
   SUPABASE_STORAGE_BUCKET=lvl-media
   ```

2. Install Python dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Run the Flask development server:

   ```
   flask run
   ```

4. Run Supabase SQL from `database/community_schema.sql` and every file in `database/migrations/` that has not been applied yet.

5. Create a public Supabase Storage bucket matching `SUPABASE_STORAGE_BUCKET` for uploaded post/profile images.

6. Open the app at `http://localhost:5000`

## Vercel Deployment

The project deploys automatically via Vercel. `vercel.json` routes all traffic to `app.py`. Environment variables (`SUPABASE_URL`, `SUPABASE_SECRET`, `FLASK_SECRET_KEY`) must be configured in the Vercel dashboard.

## Legacy PHP Version

The original PHP/MySQL/XAMPP files are preserved under `legacy/`. They are not part of the active Flask/Supabase application and are kept for archival purposes only.

## Routes

| Route | Description |
|---|---|
| `/` | Home feed |
| `/auth` | Login / Register |
| `/logout` | Log out |
| `/settings` | Edit profile |
| `/profile/<username>` | User profile |
| `/post/<id>` | Single post with comments |
| `/messages` | Direct messages |
| `/notifications` | Notifications |
| `/community` | Community timelines and groups |
| `/community/<slug>` | Community detail |
| `/level-guide` | XP, level, and reward guide |
| `/reels` | Reels feed |
| `/reels/upload` | Upload a reel |
| `/search` | Search |

## Notes

- The `legacy/` folder is not used by the active app.
- Styles are intentionally split through `static/css/styles.css`: keep default layout/navigation/feed rules separate from reward-specific CSS so level rewards can grow without bloating the base UI.
- `tests/test_supabase.py` is skipped by default. Run it only when you intentionally want a live Supabase smoke test: `RUN_SUPABASE_SMOKE=1 python -m unittest tests.test_supabase`.
- See `docs/AI_GUIDELINES.md` for technical context when using AI tools.
