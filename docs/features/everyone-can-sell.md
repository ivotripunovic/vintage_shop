# Task: Every User Can Buy and Sell

Status: **done in #89** (2026-11-23), with the decisions below as proposed;
stores later limited to the paid tiers (see "Change" below).
Written 2026-11-20 at the end of the allauth work (#73–#88).

Beyond the plan: shop slugs skip the paths under `/seller/` (`dashboard`,
`settings`, ...), Serbian `đ` becomes `dj` in slugs, and the shop setup form now
accepts a shop's own slug when editing (it used to reject it as taken).

Code review of PR #90, fixed on the branch: a typed slug is validated in the
form it is saved in; `open_for` retries only slug collisions; the seller
product page is a 404 for users without a shop; shops added in the admin get a
slug and a subscription; migration `sellers/0006` starts a subscription for
shops that had none. Accepted as is:

- Confirming the email on another device loses `next=/products/create/` (allauth
  logs in on confirmation only in the same session); the user logs in and
  lands on `/`, where "Dodaj oglas" is in the nav.
- Seeded shops get the free Garažna subscription (0 RSD), not the 999 the old
  seed set; that matches their tier.

## Change: stores only for paid tiers (2026-11-24)

Decided after review: a free user does not need a store. Only the paid
tiers, Održivo and Premijum (`sellers.models.STORE_TIERS`), come with a store:
a shop name, a page at `/seller/<slug>/` and a place in the shops list.

- The first "Dodaj oglas" opens the listing form straight away. Saving the
  listing quietly makes a hidden `Seller` row with `Seller.open_for(user)`
  (named "Prodavnica", slug `prodavnica-N`, a free Garažna subscription), because
  products, chat, sales, ratings, favourites and billing all point to `Seller`.
- `Seller.has_store` is true for the paid tiers. `Seller.display_name` is
  what buyers see: the shop name with a store, otherwise the user's full
  name, or "Prodavac" if the user has no name.
- A free seller's shop page is a 404 and the seller is not in the shops
  list. Product pages, chat, ratings and favourites show the full name with
  no shop link. Seller settings hide the shop name, description and image.
- Shop setup is only for sellers with a store. When an admin moves a seller
  up to a paid tier, the dashboard shows "Podesi prodavnicu" until the store
  has a name (`Seller.needs_store_setup`).
- Seeded shops get mixed tiers (premijum, odrzivo, garazna).
- Existing Garažna shops lose their public page. Their name and slug are
  kept, and the page comes back if they move up a tier. No migration.

Code review of this change, fixed on the branch:

- Viewing the listing form no longer opens a seller; saving the first
  listing, or uploading its first photo, does.
- Users without a store (buyers and free sellers) keep the profile form in
  account settings, which now also edits first and last name. The listing
  form asks for a name when the seller would show as "Prodavac".
- After an upgrade, an empty URL field in shop setup is made from the new
  store name instead of keeping `prodavnica-N`; "Prodavnica" itself is
  refused as a store name, so the setup banner can't get stuck.
- `free_shop_slug` reads the taken slugs in one query.
- Views that show `display_name` load `seller__user` with the seller.

Accepted as is: existing Garažna shops losing their page (decided above);
`next` lost when the email is confirmed in another browser (see the first
review); free sellers shown by full name (the decision for this change).

## Goal

Drop the buyer/seller roles. Every account can buy. Anyone can list products;
the first listing creates their shop. "Seller" stops being a role you pick and
becomes "a user who has a shop" (a `sellers.models.Seller` row).

What users will notice:

- After signing up, there is no "Kupujem / Prodajem" question.
- Every signed-in user sees "Dodaj oglas". Their first click opens shop setup,
  then the product form.
- The seller menu (dashboard, my products, shop settings) appears once they
  have a shop.

## Decisions (confirmed 2026-11-23)

1. **Create the shop at the first listing, not at signup.** The alternative is
   giving every account a `Seller` row (and a subscription row and a public shop
   URL) at signup, even accounts that never sell.
2. **Remove the welcome page** (`/auth/social/welcome/`). After signup or email
   confirmation, users go to `next`, or to `/` with a "Dobrodošli!" flash
   message.
3. **Drop `User.is_buyer`.** It gates nothing; it is only the "Kupac" label in
   account settings and an admin filter.
4. **Make `User.is_seller` a read-only property** meaning "has a `Seller` row",
   and drop the column. The ~30 places that read it stay unchanged.
5. **The shop slug defaults to the shop name, not the email local part.** Today
   a new shop's public URL (`/seller/<slug>/`) shows the owner's email name
   (`ana.petrovic@…` becomes `/seller/ana-petrovic/`) until they change the
   slug. That is a privacy leak.

## Verified Facts (as of 2026-11-20, `main` at 312b9ed)

- **Shop data already lives on `Seller`:** name, slug (`unique=True`),
  description, location, image, tier, status, subscriptions and bank details.
  It is OneToOne with `User` (`user.seller_profile`).
- **One account can already be both sides.** `orders.Sale`, `ratings.Rating`
  and `chat.Conversation` keep the buyer and the seller separately.
- **Empty shops are already hidden.** `sellers/views.py`
  `shops_browse_view` lists only `status="active"` shops with a published,
  non-deleted product.
- **There is no billing risk.** New shops get the free Garažna tier
  (`DEFAULT_TIER_SETTINGS`: 10 listings, 0 RSD, 30-day expiry), and
  `Seller.create_initial_subscription()` makes a 0-amount subscription row. No
  job creates invoices from subscriptions; an invoice comes only from
  `Seller.change_tier()` to a paid tier.

### Where a `Seller` is created today (all of these must change)

- `sellers/signals.py`: a `post_save` signal on `User` creates a `Seller` and a
  subscription when a user is created with `is_seller=True`. The slug comes
  from the email local part.
- `users/views.py` `social_become_seller_view`: a POST from the welcome page
  sets `is_seller`, creates `Seller` + subscription (slug from the email),
  and redirects to `seller_shop_setup`.
- `sellers/views.py`: `get_or_create(user=...)` with email-based defaults in
  `seller_shop_setup_view` (line ~53), `seller_dashboard_view` (~121),
  `seller_settings_view` (~170) and `seller_products_list_view` (~212).
  Some of them also call `create_initial_subscription()`.
- `products/management/commands/seed_products.py`: `"is_seller": True`.

### Where `is_seller` is read (keeps working through the property)

- `templates/base.html` lines ~220, 348, 355, 504: the seller menu and the
  "Počni da prodaješ" links.
- `products/views.py` `_get_seller_or_403` (line ~66). Its callers redirect
  non-sellers to `seller_register` (lines ~134, ~283).
- `sellers/views.py` lines ~37, 49, 78, 116, 165, 207.
- `ratings/views.py` line ~42, `users/views.py` line ~21,
  `users/models.py` `has_complete_seller_profile`.
- `users/admin.py`: `list_display`, `list_filter` and fieldsets (filter on
  "has a shop" instead).
- `chat/views.py` `is_seller_side` is computed from the conversation, not the
  flag. Nothing to change there.

### Welcome page and entry points

- `templates/users/social_signup_complete.html`, plus
  `users/views.py` `social_signup_complete_view` and URL name
  `social-signup-complete`.
- `users/adapters.py` `AccountAdapter.get_signup_redirect_url` returns
  `social-signup-complete`.
- `sellers/views.py` `seller_register_view` (`/seller/register/`, the
  "Počni da prodaješ" links in `templates/base.html` and
  `templates/core/home.html`). It currently sends visitors to signup with
  `next=<welcome>`, and signed-in non-sellers to the welcome page.
- `templates/users/account_settings.html`: the "Tip naloga" box (Kupac and
  Prodavac labels).

## Plan

One GitHub issue and one PR (`enhancement/<n>-everyone-can-sell`, per AGENTS.md
"Working on Issues").

1. **One way to open a shop.** Add `Seller.open_for(user, shop_name=None)` (or
   similar). It creates the `Seller` with the slug from the shop name (unique,
   with a numeric suffix on collision) plus the initial subscription. It is
   idempotent and atomic. Use it everywhere a `Seller` is created now. Delete
   the `post_save` signal and `social_become_seller_view`.
2. **Lazy shop on the first listing.**
   - "Dodaj oglas" (`product_create`) for a signed-in user without a shop goes
     to shop setup first.
   - Shop setup for a user without a shop shows the form; saving it calls
     `Seller.open_for` and continues to `next` (the product form).
   - `seller_register_view` becomes: visitor → signup with
     `next=/products/create/`; signed-in user → `product_create`; shop owner →
     dashboard.
   - The redirects to `seller_register` in `products/views.py` and
     `sellers/views.py` lead into the same path.
   - Remove the `get_or_create` fallbacks in the dashboard, settings and
     products-list views. A user without a shop is redirected to shop setup
     instead of having one made up on the spot.
3. **Roles.** `User.is_seller` becomes a property (`hasattr(self,
   "seller_profile")`; watch the reverse-relation caching). Drop the `is_buyer`
   and `is_seller` columns in a migration. Existing shops are unaffected,
   because they already have `Seller` rows. Before dropping `is_seller`, check
   in the migration that every `is_seller=True` user has a `Seller`, and list
   any who do not.
4. **Welcome page.** Delete the template, the view and the URL. Change
   `get_signup_redirect_url` to `/` and add a "Dobrodošli!" message, keeping
   `next` (allauth already preserves it through email verification). Keep
   `/auth/social/welcome/` as a redirect to `/` for old links. Remove the
   `social/become-seller/` URL.
5. **Nav and settings.** In `templates/base.html`, signed-in users see
   "Dodaj oglas" instead of "Počni da prodaješ", and the seller menu shows when
   `user.is_seller`. In account settings, replace "Tip naloga" with a
   "Prodavnica" box: a dashboard link for shop owners, "Otvori prodavnicu"
   (shop setup) for everyone else.
6. **Admin.** Filter users by "has a shop" (a custom `SimpleListFilter` on
   `seller_profile__isnull`). Remove the role fields from the fieldsets.
7. **Seed command.** Create shops with `Seller.open_for`.
8. **Docs.** Update AGENTS.md:
   - "users/": the role flags and the welcome page;
   - "sellers/": the post-save signal;
   - "Key Patterns": "Signal-driven seller creation".

   Also add a note to `docs/features/auth-allauth-migration.md` (Decisions say
   "Users become sellers through `/seller/register/` or the social 'become
   seller' step") pointing at this task.

## Tests

- 24 test files create users with `is_seller=True` and rely on the signal to
  get a `Seller`. Find them with
  `grep -rln "is_seller=True\|is_seller\": True" --include=*.py .`
  Replace this with one helper, for example
  `make_seller(email=..., shop_name=...)` in a shared test module or
  `conftest.py`, that calls `Seller.open_for`. Do not keep a hidden signal just
  for tests.
- New tests:
  - `Seller.open_for` is idempotent, takes the slug from the shop name, adds a
    suffix on collision, and never uses the email local part.
  - A signed-in user without a shop who clicks "Dodaj oglas" goes to shop
    setup, saves it, reaches the product form, and their first listing works.
  - The dashboard, settings and products list for a user without a shop
    redirect to shop setup and do not create a shop.
  - `/seller/register/` for a visitor, a user without a shop, and a shop owner.
  - The full path for a new visitor: "Počni da prodaješ" → signup → email
    confirmation → shop setup → product form.
  - Signup lands on `next` or `/` with the welcome message. The old welcome URL
    redirects.
  - The migration lists any `is_seller=True` user without a `Seller`.
- Update `users/test_auth_flows.py`. Several tests assert
  `social-signup-complete` (signup confirmation, social signup, "start
  selling").

## Out of Scope

- Changing tiers, listing limits or billing.
- Hiding "Dodaj oglas" from anyone. Every signed-in user can list.

## How to Work It (repo conventions)

- Read `AGENTS.md`. Branch from an up-to-date `main`, put `Refs #<n>` in every
  commit and `Closes #<n>` in the PR body, and push to `origin` only.
- The user runs `/code-review` on each PR and has the findings fixed on the
  same branch before merging. Expect it, and verify review claims against the
  code before acting (reviews have repeated outdated premises before).
- Tests: `pytest` (parallel). Write tests that fail on the old code; that was
  checked for every PR in #81–#88.
- The browser extension may not be connected. Check pages with the Django test
  client when it is not.
