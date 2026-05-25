# Database Files

The active application uses Supabase/PostgreSQL through `app.py`.

- `community_schema.sql` contains the current community-related Supabase tables.
- `migrations/001_product_hardening.sql` adds current production hardening columns, indexes, unique constraints, media support, onboarding fields, and safety-action tables.
- `legacy/mysql_schema.sql` is an archived MySQL/XAMPP schema from the old PHP version. Do not use it for the Flask/Supabase app.

Future database changes should be written as Supabase/PostgreSQL migrations, not MySQL scripts.
