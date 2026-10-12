---
name: coming-soon
description: Coming Soon mode (pre-launch gate). Use when touching core.middleware.ComingSoonMiddleware, templates/core/coming_soon.html, preview/bypass access, or the COMING_SOON / COMING_SOON_SECRET env vars.
---

# Coming Soon Mode

Controlled by two `.env` variables:

```
COMING_SOON=True          # show coming soon page to all visitors
COMING_SOON_SECRET=xyz    # optional bypass secret
```

`core.middleware.ComingSoonMiddleware` intercepts all requests when `COMING_SOON=True`. Bypass rules, in priority order:

1. `/admin/` URLs always pass through
2. Staff and superusers always see the full site
3. Visiting `/?preview=<COMING_SOON_SECRET>` sets a cookie that grants access for 7 days
4. Everyone else sees `templates/core/coming_soon.html`

To work on the site locally with coming soon enabled, log in via `/admin/` as a superuser.
