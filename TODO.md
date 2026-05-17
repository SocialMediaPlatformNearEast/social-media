# LvL TODO

Created: 2026-05-04

## Completed

- Updated `README.md` so it matches the current app.
- Rewrote the FAQ/chatbot content so it only mentions features that actually exist.
- Implemented a real post three-dots menu.
- Added friend request accept/decline handling in Notifications.
- Made Search more useful with Top scoring, Latest ordering, discovery users, and recent posts.
- Removed unused image URL handling from post creation.
- Added nav badges for unread notifications and messages.
- Replaced dead profile stats links with non-clickable stats.
- Made the Messages "new message" action jump to the recipient picker.
- Added basic login rate limiting for repeated failed login attempts.
- Hardened session cookie settings with `HttpOnly`, `SameSite=Lax`, and `Secure` when HTTPS is used.
- Replaced direct `HTTP_REFERER` redirects with a small internal-only redirect helper.
- Replaced raw database error messages shown to users with generic messages and server-side logging.
- Sanitized form redirect targets before using them after message send failures or success.
- Added dynamic profile banners by level.
- Added birthday validation during registration and profile editing.
- Added profile photo removal alongside the existing upload flow.
- Added Followers, Following, and Friends pages.
- Upgraded shared post menus with copy link, report, mute, block, and delete-own-post actions.
- Extracted shared app utility helpers and shared post-card markup.
- Added focused tests for birthday validation, profile banner tiers, post menus, and new routes.
- Added first-class PWA install prompt support with iOS Add to Home Screen guidance.

## Remaining Improvements

- Consider richer avatar controls such as crop/position controls if uploaded images need fine tuning.
- Consider recent search chips once search history needs a visible UI.

## Security And Quality

- Consider a permanent server-side login throttle table if this app will be deployed beyond local/demo use.

## Product Decisions

- Decide whether gender should remain required and limited to Male/Female, or whether it should be optional/more flexible.
- Keep leveling/XP as the central product identity and make sure new features reward meaningful social activity.
