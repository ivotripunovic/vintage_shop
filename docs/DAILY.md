# 2026-11-03
- Deployed the one-page listing form (#44) to production
- HEAD responses without a body (#64, PR #65): since gunicorn 26, every HEAD request logged `WSGI app sent body bytes on a no-body response`, every 5 minutes for UptimeRobot's `HEAD /health/`. A middleware that runs first now empties HEAD bodies, keeps the GET's `Content-Length`, leaves 1xx/204/304 alone, and works under WSGI and ASGI

# 2026-11-02
- Add-item fixes from the HCI review: editing a draft no longer 404s (#40, PR #47); the product form's status dropdown is replaced by Sačuvaj / Sačuvaj i objavi, so publishing always needs a photo and can't bypass mark-sold (#41, PR #48); the photo page shows the real size limits, checks them before nginx returns 413, and leads on to publishing (#42, PR #49)
- Cover photo and photo order (#43, PR #52): make any photo the cover, move photos up/down; works without JavaScript
- Smarter product form defaults (#45, PR #55): one item in stock, whole-dinar prices with thousands separators, category and condition required. Remembered last category/condition and autosave of unsaved typing (#46, PR #56); the duplicate-listing action was dropped
- Front-end bugs: Tailwind config now loads after the CDN script, so the custom fonts apply (#50, PR #51); the desktop category bar no longer flickers after scrolling (#53, PR #54)
- Deleting a listing soft-deletes it (#57, PR #58): sales and chats keep their product, and the monthly listing slot stays used
- One-page listing form with photos first (#44, PRs #59, #60, #61):
  - Photos are processed on upload: rotated upright, metadata (incl. GPS in EXIF/XMP) stripped, capped at 2000px, colour profile kept, 600px thumbnails for grids
  - Booking.com-style quality tips: score on the seller's product page and live tips on the form (too few photos, small, dark/bright, blurry, cover cropped by the square grid, short or ALL CAPS title, thin description, no measurements)
  - Photos are resized in the browser and uploaded one by one before the listing exists (`PhotoUpload`), so validation errors keep them; reorder with ★/arrows/drag; up to 12 per listing; works without JavaScript
  - Step bar (Fotografije · Detalji · Pregled), live buyer-card preview, and publishing straight from the new-listing form
  - Each PR got a code review; fixes covered photo files shared or lost on double submit or during the purge, reorder races and an off-by-100× price preview
  - To deploy: run `backfill_photos` (optionally `--all --rewrite-originals` after backing up `media/`) and install `deploy/purge-photo-uploads.cron` by hand
- Deployment docs (PR #63): `docs/ops/deployment.md` has a new "One-time steps after a deploy" section with the #44 photo backfill and purge cron

# 2026-10-31
- Chat fixes (#31, PR #32): live view no longer drops or duplicates messages when both sides send at once; email cooldown is per recipient, so a quick reply still notifies the first sender; threads show the latest 100 messages; inbox no longer runs 2 queries per conversation; polling backs off 3s → 30s when quiet and pauses in hidden tabs
- Chat privacy and safety (#33, PR #34): chat shows shop names and buyer first names ("Kupac" if unset), never emails; per-user limits of 20 messages/min and 20 new conversations/hour; send errors shown under the form; notification emails sent in a background thread after commit (`CHAT_EMAIL_ASYNC`). Deployed and checked in production
- Chat truncation notice (#36, PR #37): threads over 100 messages show "Prikazano je poslednjih 100 poruka." at the top, so older messages don't look lost. Paging in older messages stays in TODO until production shows threads that long. Deployed and checked in production
- Dependency updates (PR #39): patch/minor bumps, plus Pillow 13 and isort 9. Pillow 13 requires Python 3.11+, so the documented minimum moved from 3.9 to 3.11

# 2026-10-27
- Item popularity (#8, PR #20): unique view count per user/session, wishlist save count and "viewed in last 15 min" on the product page; views and saves in the seller's product list. Owner, bots, HEAD and prefetch requests are not counted
- Buyer/seller ratings (#9, PR #22): sellers mark a product sold to a buyer from chat (new `orders.Sale`); both sides then rate within 14 days (overall 1–5, optional aspects, text). Ratings stay hidden until both rate or the window closes. The rated person can reply once or report to admin. New Moje ocene page, and Poruke/Ocene entries with badges in the user menu
- Trader confirmation (#3, PR #24): sellers tick a "trgovac" statement in shop settings; the time and exact statement text are stored, a Trgovac badge shows on the shop page and the status on the dashboard. Admin can see and clear it but not set it. Wording is a draft pending legal sign-off; changing `TRADER_STATEMENT` asks sellers to re-confirm. Follow-up bug #25 (settings form saves email with `commit=False`)

# 2026-05-07
- Fixed certificate for domain and www.domain, nginx could not restart because of its runaway processes 
- Seed groups on the production
- Translate create product page completly
- Add links to facebook/instagram
- User dashboard is not present, links lead to not existent content
