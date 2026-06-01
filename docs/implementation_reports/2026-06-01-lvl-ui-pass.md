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

## Checkpoints

- [x] Baseline recorded.
- [x] Failing contract tests added.
- [x] Top bar and icon navigation implemented.
- [x] Post actions and relative time implemented.
- [x] Profile cleanup and high-five action implemented.
- [ ] LvL Guide and settings mobile polish implemented.
- [ ] Tests passed.
- [ ] Rendered browser sanity check completed.
- [ ] Final commit created.

## Notes

- High-five uses the existing interaction streak table for this pass so it does not introduce a new database table.
- If a later review finds that message streaks and profile high-fives need separate streak histories, split them into separate tables in a follow-up migration.
