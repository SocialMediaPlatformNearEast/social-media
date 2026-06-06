# Database Files

The active application uses Supabase/PostgreSQL through `app.py`.

- `community_schema.sql` contains the current community-related Supabase tables.
- `migrations/001_product_hardening.sql` adds current production hardening columns, indexes, unique constraints, media support, onboarding fields, and safety-action tables.
- `migrations/002_reels.sql` adds the first-class Reels tables.
- `migrations/003_safety_and_demo.sql` adds user safety actions and optional demo content.
- `migrations/004_streaks.sql` adds high-five streak tracking.
- `migrations/005_oauth_identity.sql` adds Supabase Auth identity columns for social login.
- `migrations/006_password_reset_tokens.sql` adds hashed password reset tokens for normal email login.
- `legacy/mysql_schema.sql` is an archived MySQL/XAMPP schema from the old PHP version. Do not use it for the Flask/Supabase app.

Future database changes should be written as Supabase/PostgreSQL migrations, not MySQL scripts.
