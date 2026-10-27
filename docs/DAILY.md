# 2026-10-27
- Item popularity (#8, PR #20): unique view count per user/session, wishlist save count and "viewed in last 15 min" on the product page; views and saves in the seller's product list. Owner, bots, HEAD and prefetch requests are not counted
- Buyer/seller ratings (#9, PR #22): sellers mark a product sold to a buyer from chat (new `orders.Sale`); both sides then rate within 14 days (overall 1–5, optional aspects, text). Ratings stay hidden until both rate or the window closes. The rated person can reply once or report to admin. New Moje ocene page, and Poruke/Ocene entries with badges in the user menu

# 2026-05-07
- Fixed certificate for domain and www.domain, nginx could not restart because of its runaway processes 
- Seed groups on the production
- Translate create product page completly
- Add links to facebook/instagram
- User dashboard is not present, links lead to not existent content
