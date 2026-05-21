# Community Timeline Hub Design

## Goal

Reshape the LvL Community page into a feed hub with three separate timelines while preserving the existing LvL application shell, spacing system, navigation, buttons, and dark blue visual language.

External references such as TikTok and X/Twitter are behavior references only. The implementation must look and feel like the current LvL app.

## Scope

Replace the inner content of `/community`. Do not redesign the global layout.

Keep:

- Existing `templates/layout.html` shell.
- Left rail navigation on desktop and expanded menu states.
- Mobile header and mobile bottom navigation.
- Right `Community Highlights` rail on wide screens.
- Existing LvL colors, border treatments, avatar styling, post button styling, profile block, and logout placement.
- Existing post card interaction model: replies, reposts, likes, media, profile links, post options.

Remove from the Community landing page:

- Short video sections.
- Live/video wording.
- The current static explore layout as the primary page surface.

## User Experience

The Community page becomes a timeline hub with a sticky tab switcher inside the center content area:

- `Followers`: posts from users who follow the viewer.
- `Following`: posts from users the viewer follows. This is the default middle timeline.
- `Community`: posts linked to communities, with joined and active communities prioritized.

The tabs must support tap/click switching. On touch devices, the timelines use horizontal scroll snapping with light JavaScript tab synchronization. Tap remains the reliable fallback, and the tab controls stay visible so the interface is never hidden or confusing.

Each timeline displays regular LvL post/thread cards. If a timeline is empty, it shows a clear empty state and the next useful action, such as following users, creating a post, or joining/creating a community.

## Layout

Desktop and larger tablet:

- Keep the existing three-column LvL shell.
- Render the timeline hub in the existing center `timeline-community` area.
- Keep the right highlights rail visible where it currently fits.
- Keep tab controls sticky near the top of the Community content.
- Avoid introducing a second unrelated navigation system.

Phone portrait:

- Use the current mobile shell and bottom nav.
- Show a compact Community header and sticky three-tab switcher.
- Use single-column post cards with the existing compact mobile post layout.
- Keep the floating/create action consistent with the current LvL post button behavior.

Phone landscape:

- Do not open a large left drawer over the content.
- Use the existing mobile/rail behavior, but make Community content shorter, tighter, and scrollable without overlap.
- Keep tab controls readable and prevent cards, buttons, or navigation labels from colliding.

## Feed Algorithm

Use a lightweight server-side ranking layer that works with the current Flask and Supabase setup.

Shared scoring signals:

- Recency is the strongest base signal.
- Engagement boosts posts with replies, likes, and reposts.
- Viewer relationship boosts posts in the relevant tab.
- Author level adds a small capped boost that cannot overpower fresh posts.

Timeline rules:

- `Followers`: find users where `following_id` is the viewer and rank their recent posts.
- `Following`: reuse and improve the existing followed-user feed, defaulting to this tab.
- `Community`: collect posts from `community_posts`, enrich them with post data, and prioritize posts from communities the viewer has joined before broader active community posts.

If Supabase community tables are unavailable, the page must not crash. It renders the existing community setup message or a clean empty state.

## Data And Routes

Use `/community?tab=following`, `/community?tab=followers`, and `/community?tab=community` as durable URLs.

The route prepares:

- `active_tab`.
- `timeline_posts`.
- `timeline_counts` with inexpensive counts when the data is already available from the feed query.
- `communities` for create/join discovery where useful.
- `highlights` for the existing right rail.

The implementation must prefer existing helpers such as `enrich_posts`, `visible_post_filter`, `get_following_feed_posts`, `get_community_posts`, and `_post_card.html` before adding new abstractions.

## Styling

Add Community-specific CSS only where the existing styles do not cover the new hub.

Design constraints:

- Keep cards at 8px radius unless an existing component already uses another radius.
- Use LvL's dark background and blue accent.
- Avoid a one-off TikTok or X clone visual theme.
- Do not add decorative gradient orbs.
- Keep text readable and contained in buttons/cards at mobile and landscape widths.

## Testing

Add or update focused tests for:

- `/community` defaults to the `Following` tab.
- The template renders all three timeline tab links.
- The Community page no longer renders short-video/live wording.
- Empty states render for timelines with no posts.
- The route tolerates missing community tables without a crash.

Manual verification:

- Desktop Community page.
- Phone portrait viewport.
- Phone landscape viewport.
- Switching all three tabs.
- Existing menu, Post button, profile block, bottom nav, and right highlights remain consistent.
