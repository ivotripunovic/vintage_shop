# Mobile Navigation Improvements Plan

Reference sites analysed: hm.com, 1stdibs.com, kupujemprodajem.com

## Out of scope
- Cart icon — no cart feature yet, revisit when implemented

---

## Tasks

### Task 1 — Logo: short wordmark on mobile
**File:** `templates/base.html`  
**Change:** Replace `{{ SITE_NAME|slice:":1" }}` (renders single letter "U") with a short two-letter mark (e.g. "UB") styled with the same serif font.  
**Why:** A single letter is not recognisable as a brand. "UB" or a compact serif mark reads as intentional.

---

### Task 2 — Hamburger menu: section organisation
**File:** `templates/base.html` (mobile-menu div)  
**Change:** Add labelled section headers and dividers to group:
1. **Kategorije** — all category links  
2. **Prodavnica** — Shops browse, Sell CTA  
3. **Prodaj** — seller tools (dashboard, products, add, settings) — only if `user.is_seller`  
4. **Nalog** — messages, account settings, logout / login + register  
**Why:** Currently all links run as one flat list making it hard to scan.

---

### Task 3 — Category chips: horizontal scroll row on mobile
**File:** `templates/base.html`  
**Change:** Add a new row inside `<header>`, visible only on mobile (`md:hidden`), below the search row. Renders top-level categories as horizontally scrollable chips with `overflow-x-auto`.  
**Why:** Categories are completely hidden on mobile without opening the hamburger.

---

### Task 4 — Top bar: messages + account icons on mobile
**File:** `templates/base.html`  
**Change:** In the mobile icon group (before the hamburger button), add:
- Chat icon with unread badge (authenticated only) → `chat_inbox`  
- Person icon (authenticated → `account-settings`, anonymous → `login`)  
**Why:** Primary actions require two taps through the hamburger today.  
**Note:** Use new badge IDs `chat-badge-topbar` alongside existing ones so the global poll script updates all three badges.

---

### Task 5 — Top bar: "Prodaj" CTA for non-sellers on mobile
**File:** `templates/base.html`  
**Change:** For authenticated non-sellers and anonymous users, show a small "Prodaj" pill/button in the mobile icon group.  
**Why:** Seller acquisition CTA is invisible on mobile unless user opens hamburger.  
**Seller users:** keep the existing `+` (add product) icon — it already serves this role.

---

### Task 6 — Bottom navigation bar
**File:** `templates/base.html` + `templates/base.html` main padding  
**Change:** Add a fixed bottom bar (`md:hidden`) with 5 tabs:

| Tab | Icon | Link | Badge |
|-----|------|------|-------|
| Početna | home | `home` | — |
| Pretraži | search/grid | `products_browse` | — |
| Prodaj | tag/plus | `product_create` (seller) or `register` | — |
| Poruke | chat bubble | `chat_inbox` | unread count |
| Nalog | person | `account-settings` (auth) or `login` | — |

Active tab highlighted based on `request.resolver_match.url_name`.  
Add `pb-16 md:pb-0` to `<main>` so content is not hidden behind the bar.  
Update global badge poll to also set `chat-badge-bottom` ID.

---

## Implementation order

1. Task 1 — Logo (trivial, standalone)
2. Task 2 — Menu organisation (no dependencies)
3. Task 3 — Category chips (no dependencies)
4. Task 4 — Top bar icons (no dependencies)
5. Task 5 — "Prodaj" CTA (no dependencies)
6. Task 6 — Bottom nav (depends on badge IDs from Task 4 being in place)
