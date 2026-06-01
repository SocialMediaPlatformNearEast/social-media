# LvL UI Pass Report

Baseline reference: `c1a3a2b` (`Clean LvL CSS structure and dead code`)

## Scope

This pass keeps desktop Home/Reels structure intact and focuses on the approved UI contract:

- Top-middle search bar.
- Top-right chat and alert icon buttons.
- Icon-only navigation and post action controls where icons are clear.
- More visual LvL Guide.
- LvL-native scrollable discovery/community surfaces without copying another app outright.
- Larger profile image.
- Remove repeated profile stat/name boxes.
- Profile high-five action in the top profile area.
- Profile info order: posts, following, followers, friends.
- Mobile edit profile aspect-ratio and spacing cleanup.
- Web back button.
- Relative post time labels.
- LvL-native community shortcuts for history, community, trends, and news.

## Checkpoints

- [x] Baseline recorded.
- [x] Failing contract tests added.
- [x] Top bar and icon navigation implemented.
- [x] Post actions and relative time implemented.
- [x] Profile cleanup and high-five action implemented.
- [x] LvL Guide and settings mobile polish implemented.
- [x] Community shortcut strip implemented.
- [x] Tests passed.
- [x] Rendered browser sanity check completed.
- [x] Final commit created.

## Notes

- High-five uses the existing interaction streak table for this pass so it does not introduce a new database table.
- If a later review finds that message streaks and profile high-fives need separate streak histories, split them into separate tables in a follow-up migration.
- The community shortcut strip uses real existing routes instead of placeholder panels: profile history, community timeline, top search trends, and the LvL guide.
- Static assets were bumped to `v32` after CSS and JS updates so local service-worker/browser cache does not keep stale styling.
- Rendered checks covered mobile `390x844`, landscape `844x390`, and desktop `1280x800`; no horizontal page overflow was detected in those checks.

## Second Checkpoint

Reference after the first checkpoint: `14f080d` (`Complete LvL UI polish checkpoint`)

- [x] Added an Activity page for posts, comments, likes, reposts, and reels history.
- [x] Added Activity to the icon-only hamburger/sidebar navigation.
- [x] Grouped stackable alerts and removed post-content previews from alert rows.
- [x] Marked alerts as read when the Alerts page is viewed so the red badge clears until new alerts arrive.
- [x] Tightened Messages layout and converted message delete to an icon control.
- [x] Kept Reels sound preference for the current browser session.
- [x] Removed the extra sticky mobile Reels upload pill; mobile upload stays on the bottom `+` action.
- [x] Tightened Reels frame sizing so landscape and phone views keep a clean vertical aspect.
- [x] Added edge swipe-back behavior for mobile browsers.
- [x] Static assets were bumped to `v33`.
- [x] Focused tests passed.
- [x] Full test suite passed: 57 tests, 1 expected skip.
- [x] Rendered browser checks passed on mobile `390x844`, landscape `844x390`, and desktop `1280x800`.
