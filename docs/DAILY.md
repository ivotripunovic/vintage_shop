# 2026-10-31
- Chat fixes (#31, PR #32): live view no longer drops or duplicates messages when both sides send at once; email cooldown is per recipient, so a quick reply still notifies the first sender; threads show the latest 100 messages; inbox no longer runs 2 queries per conversation; polling backs off 3s → 30s when quiet and pauses in hidden tabs
- Chat privacy and safety (#33, PR #34): chat shows shop names and buyer first names ("Kupac" if unset), never emails; per-user limits of 20 messages/min and 20 new conversations/hour; send errors shown under the form; notification emails sent in a background thread after commit (`CHAT_EMAIL_ASYNC`). Deployed and checked in production

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
