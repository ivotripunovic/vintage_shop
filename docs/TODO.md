# TODO

Quick, planned work that is not yet a GitHub issue. Bugs and enhancements go to
GitHub Issues (`gh issue create`), and entries here should link to their issue once
one exists.

Keep entries short. Move an item to `DAILY.md` or close its issue when it is done.

## Next

- [ ] Every user can buy and sell (#89): drop the buyer/seller roles, open a shop at the first listing, remove the welcome-page choice. Full task: [features/everyone-can-sell.md](features/everyone-can-sell.md). PR open.

## Later

- [ ] Chat: load older messages in long threads; the page only shows the latest 100, with a notice since #36 (follow-up from #31).
  Only worth doing if production threads get near 100 messages; check with
  `Conversation.objects.annotate(n=Count("messages")).aggregate(Max("n"))`

## Bugs

- [ ] User dashboard is not present, links lead to non-existent content (from `DAILY.md`, 2026-05-07)
