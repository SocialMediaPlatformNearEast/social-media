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

## Remaining Improvements

- Add a fuller profile picture flow instead of relying mostly on gender defaults and theme color.
- Add dedicated Following, Followers, and Friends pages if those stats should become clickable.
- Add richer post menu actions such as copy link or report/block after those features exist.
- Consider recent search chips once search history needs a visible UI.

## Security And Quality

- Consider a permanent server-side login throttle table if this app will be deployed beyond local/demo use.

## Product Decisions

- Decide whether gender should remain required and limited to Male/Female, or whether it should be optional/more flexible.
- Decide whether LvL-style branding is final, or whether the app should develop its own identity.
- Decide whether gamification/XP should be a central feature or a light profile detail.
