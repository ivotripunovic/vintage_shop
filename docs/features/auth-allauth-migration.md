# Authentication — Move Email Auth onto allauth

Status: **done**. Option B was decided on 2026-11-19, and all four steps were finished on 2026-11-20 (#76–#79).

Email/password auth (register, login, verification, password reset) was built
first as custom code in `users/`. django-allauth was added later for Google,
Facebook and Apple logins. The two now run side by side and disagree with each
other. This page records what is wrong, the options, and the recommended plan.

## Decisions (2026-11-19)

- **Option B:** all auth moves onto allauth.
- **Google login creates accounts from the login page too.** The rule that
  social signup is allowed only from the register page goes away.
- **Email signup sets no roles.** A new email account is neither marked as a
  seller nor explicitly as a buyer. `UserRegistrationForm.save` no longer sets
  `is_buyer = True` / `is_seller = True`, and the `post_save` signal therefore no
  longer creates a `Seller` profile for every signup. Users become sellers
  through `/seller/register/` or the social "become seller" step. Existing
  users keep their flags. *Superseded by #89
  ([everyone-can-sell.md](everyone-can-sell.md)): the roles, the signal and the
  "become seller" step are gone; the first listing opens the shop.*
- **Sign-in by email code:** not decided; can be added after the move.
- **Outstanding links:** no count needed. Custom tokens expire after 24 h
  (verification) and 1 h (reset), so the old-URL redirects only need to cover
  the day after cutover.

---

## Current State

| Concern | Custom code (`users/`) | allauth |
|---|---|---|
| Register | `register_view`, `UserRegistrationForm` | `/auth/accounts/signup/` (live, unused) |
| Login | `login_view`, `UserLoginForm` | `/auth/accounts/login/` (live, unused) |
| Email verified? | `User.email_verified` + `VerificationToken` | `allauth.account.models.EmailAddress.verified` |
| Verification email | `send_verification_email()`, Serbian, plain text | allauth templates, English |
| Password reset | `password_reset_*_view`, `VerificationToken` | `/auth/accounts/password/reset/` (live, unused) |
| Social login | — | Google / Facebook / Apple, `users/adapters.py` |
| Linking social → existing account | `SocialAccountAdapter.pre_social_login` (PR #72) | built-in setting exists, not enabled |

`allauth.account.urls` is mounted at `/auth/accounts/` because allauth's social
flow calls `reverse()` on account URL names. Mounting it also exposes allauth's
whole email-auth system.

---

## Problems Found

All verified on 2026-11-19 against the code and the dev database.

1. **Two records of email verification.**
   - In the dev database, all 14 users have `User.email_verified=True`.
   - 12 of those users have no `EmailAddress` row, and 1 row is unverified.
   - When allauth decides a login needs verification
     (`ACCOUNT_EMAIL_VERIFICATION = "mandatory"`), it ignores
     `User.email_verified`. It sends its own English email and redirects to
     `/auth/accounts/confirm-email/`.
2. **allauth's second auth system is live.**
   - A POST to `/auth/accounts/signup/` creates a real account.
   - That account skips `UserRegistrationForm`: `is_seller` ends up False,
     while the custom form sets it to True.
   - The user gets the English email "[example.com] Please Confirm Your Email
     Address".
3. **Open redirect on login.** `login_view` passes `?next=` straight to
   `redirect()`. A test confirmed that
   `/auth/login/?next=https://evil.example/` redirects to that site after login.
4. **Email enumeration.** Password reset and resend-verification both say
   "Nije pronađen nalog sa ovom e-adresom" for unknown emails, so anyone can
   test whether an email is registered.
5. **No rate limits** on login, password reset or resend-verification. That
   allows password brute force, and mailbox flooding paid for through SendGrid.
6. **Case-sensitive duplicate check.** `clean_email` uses `email=`, so
   `Foo@x.com` and `foo@x.com` can both register. The PR #72 adapter has to work
   around this (`_pick_user`).
7. **allauth pages are English.** `USE_I18N = False`, so allauth's msgids are
   shown as-is. Page styling was fixed in #73 / PR #74, but the text was not.

---

## Options

### A. Keep the custom auth, use allauth only for social login

- Unmount allauth's account pages, or redirect them to the custom ones.
- Keep `EmailAddress` in sync with `User.email_verified` from code (signals or
  the verify view).
- Fix problems 3–6 by hand: safe `next`, generic reset/resend messages, rate
  limits, case-insensitive lookups.

The work is small, but the code keeps two systems in sync forever, and every
allauth upgrade can bring the conflict back.

### B. Move everything onto allauth (recommended)

allauth handles register, login, verification, reset, password change and social
login. The project keeps its templates and Serbian text by overriding allauth's
templates.

What allauth provides for free:

- **One verification record:** `EmailAddress`.
- **Rate limits:** `ACCOUNT_RATE_LIMITS` covers login failures, reset and
  confirmation emails.
- **No enumeration:** `ACCOUNT_PREVENT_ENUMERATION`, on by default.
- **Safe `next` handling.**
- **Signed keys for links,** replacing the `VerificationToken` table.
- **Social linking:** `SOCIALACCOUNT_EMAIL_AUTHENTICATION` and
  `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT` cover most of
  `pre_social_login`. (Not used in the end: our checks are stricter. See
  step 3.)
- **Optional later:** email change with re-verification, sign-in by email code
  (`ACCOUNT_LOGIN_BY_CODE_ENABLED`), re-authentication, MFA.

Costs and risks:

- About 1,000 lines of auth tests to rewrite (`users/test_views.py`,
  `users/test_tokens.py`).
- Verification and reset links in emails sent before the cutover stop working.
  Old URLs should redirect to "request a new link".
- One behaviour change: logging in with an unverified email sends a fresh
  verification email, instead of sending the user to the resend page.

---

## Recommended Plan (B)

Each step gets its own issue, branch and PR.

1. **Copy verification state into allauth** (#76). *Done.*
   - Migration `users/0004` gives every user a primary `EmailAddress` for
     their current email. It is stored lowercased, as allauth looks
     addresses up, and is verified if either side was.
   - Until step 4, `users/email_sync.py` and `users/signals.py` kept the
     two in step (both removed in #79):
     - Saving a User raises allauth's `verified`, but never quietly lowers
       it, so a stale instance cannot undo a confirmation.
     - allauth's `email_confirmed` sets `User.email_verified`.
     - Changing the email (seller settings, admin, shell) makes the new
       address unverified, voids links sent to the old address, and removes
       only the previous address. A provider's extra emails are kept.
     - Another account's verified address is never deleted; it blocks
       verification of the same address for this user instead.
     - allauth's own signups are skipped (our adapters mark them) because
       `setup_user_email` creates their rows.
     - Emails differing only in case are verified for one user only, with
       a warning logged instead of a crash.
   - Changing the email in seller settings emails a confirmation link (with
     email-change wording) to the new address.
   - Un-verifying a user by hand needs both records: edit the User and the
     allauth email address in the admin.
2. **Switch email auth to allauth** (#77). *Done.*
   - allauth is mounted at `/auth/`, so the login page stays `/auth/login/`.
     The old custom paths (`/auth/register/`, `/auth/password-reset/`,
     `/auth/password-change/`, `/auth/verify-email-resend/`) and the earlier
     `/auth/accounts/*` mount redirect to their allauth pages. Links from
     custom verification emails (`/auth/verify-email/<token>/`) still work
     until #79.
   - Serbian templates for every allauth page are in `templates/account/`
     and `templates/socialaccount/`, built from the earlier designs. The
     emails are in `templates/account/email/`. `AccountAdapter.send_mail` adds
     `SITE_NAME`, because allauth renders emails without context processors.
   - Error messages are Serbian: `AccountAdapter.error_messages` plus
     `users/allauth_forms.py` for form-level checks and Django's password
     validators. Translation stays off site-wide (see "Language").
   - Signup sets no roles. `/seller/register/` sends visitors to the
     verified signup, then to the welcome page, where they open a shop.
   - Email change is allauth's re-verifying flow (`/auth/email/`). Seller
     settings no longer edit the email; they link there.
   - Logout is POST-only.
   - `ACCOUNT_RATE_LIMITS` is written out in settings. Enumeration
     prevention is on: duplicate signups and resets for unknown emails get
     an email instead of an on-page hint.
   - The custom register/login/logout/reset/change views, forms, templates
     and tests are deleted. `users/test_auth_flows.py` covers the allauth
     flows instead.
3. **Google signup from the login page** (#78). *Done, scope narrowed.*
   - `pre_social_login` no longer limits new social accounts to the signup
     page, so "Nastavi sa Google" on the login page creates the account.
   - A new social account needs an email the provider verified. Before,
     `save_user` marked every social email verified, including Facebook's
     (configured `VERIFIED_EMAIL: False`) and addresses typed into the social
     signup step. Without a verified email (no email, or an unverified one)
     the user is sent to email signup and can connect the social account
     later. Google emails are provider-verified, so Google signups work in
     one step.
   - Linking a provider to a local account whose email is not verified
     (never verified, or made unverified by an admin edit) treats that
     account as possibly someone else's. Someone may have registered the
     owner's address first. Everything that person could still use is
     revoked in one transaction: the password and unused links (#72), other
     social logins, and other email addresses.
   - An address already verified for a different account is never used.
     Linking it, or signing up with it as a new account (for example
     another user's extra provider email), sends the user to the login page
     instead. Another account's *unverified* row for the address (an
     unproven claim, such as a pending email change) is removed when the
     provider proves ownership. Otherwise allauth's signup would treat the
     address as taken.
   - `SOCIALACCOUNT_EMAIL_VERIFICATION` stays `"none"`. New social accounts
     always have a verified email, and `"mandatory"` would also block linked
     users whose email became unverified (for example after an admin edit)
     from logging in with Google.
   - Social signup sets no roles, like email signup.
   - **Not done, on purpose:** replacing our linking code with allauth's
     `SOCIALACCOUNT_EMAIL_AUTHENTICATION`. It would add nothing, and it is
     weaker. It trusts every configured provider equally, where
     `pre_social_login` checks that the provider verified that particular
     address. It also does not lock out the password of a never-verified
     local account when linking (PR #72).
4. **Clean up** (#79). *Done.*
   - `VerificationToken`, `verify_email_view` and the custom verification
     links are gone. Nobody signed up between the #86 deploy and this
     change, so no link was still open. `/auth/verify-email/<token>/`
     redirects to the login page.
   - `User.email_verified` and `email_verified_at` are dropped, together
     with `users/email_sync.py` and `users/signals.py`. allauth's
     `EmailAddress` is the only record of verification:
     - `User.email_verified` is a read-only property over it, for templates
       and the admin.
     - `User.mark_email_verified()` records a verified primary address. It
       is used for provider-proven links, the seed command and tests.
   - Migration `users/0005` first gives every user still flagged verified a
     verified primary `EmailAddress`, then drops the columns.
   - Un-verifying a user is done in the admin under Accounts › Email
     addresses. Changing a user's email in the admin user form deletes the
     old address (it stops working for login and reset) and adds the new
     one unverified (`User.set_primary_email`). Users change their own
     email through allauth (`/auth/email/`).
   - Migration `users/0005` can be reversed. Rolling it back rebuilds
     `email_verified` from allauth's rows.
   - The old-URL redirects stay. They cost nothing, and bookmarks and old
     emails may still point at them.

### Do Now, Whichever Option Wins

- Fix the open redirect in `login_view` (#75) with `url_has_allowed_host_and_scheme`.
  It is a one-line change, worth a small separate PR rather than waiting for
  step 2.

---

## Language

allauth ships a Latin-script Serbian translation (`sr_Latn`). Turning on
`USE_I18N` with `LANGUAGE_CODE = "sr-latn"` would translate allauth's pages, but
it also changes number and date formatting across the whole site, for example
decimal commas in prices. Overriding the templates the site actually uses keeps
the Serbian text and the design under project control. Turning on translation is
a separate decision.

---

## Open Questions

- Sign-in by email code (`ACCOUNT_LOGIN_BY_CODE_ENABLED`): the user enters
  their email, receives a short code and types it in instead of a password.
  Passwords keep working. Decide after step 2.
- `is_buyer` gates nothing: it is only a label in
  `templates/users/account_settings.html` and an admin filter. The model
  default stays `True`, so signup does not need to touch it. Whether to drop
  the field entirely is a later cleanup. *Dropped in #89.*
