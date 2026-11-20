# Authentication — Move Email Auth onto allauth

Status: **decided, option B**, 2026-11-19. Written 2026-11-19.

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
  users keep their flags.
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
  `pre_social_login`.
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
   - Until step 2, `users/email_sync.py` and `users/signals.py` keep the
     two in step:
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
2. **Switch email auth to allauth** (#77).
   - Move `templates/users/login.html`, `register.html`,
     `password_reset_*.html` and `verify_email_resend.html` to
     `templates/account/…`, adapting the form field names. The design and
     Serbian text stay the same.
   - Email signup sets no `is_buyer` / `is_seller` (see Decisions). Check
     every view and template that reads `is_buyer` before dropping it from
     the signup flow.
   - Write Serbian email templates in `templates/account/email/`
     (`email_confirmation_*`, `password_reset_key_*`, `account_already_exists_*`).
   - Keep `/auth/login/`, `/auth/register/`, `/auth/password-reset/` and the
     other old URLs working as redirects.
   - Set `ACCOUNT_RATE_LIMITS` explicitly and review the defaults.
   - `/seller/register/` (`seller_register_view`) creates the account and
     logs the user in with no email verification at all. Fold it into the
     allauth signup.
   - Seller settings email change: #76 makes it reset verification and
     send the custom link. Replace that with allauth's email change flow.
   - This fixes problems 2–6.
3. **Simplify social linking** (#78).
   - Enable `SOCIALACCOUNT_EMAIL_AUTHENTICATION` and `..._AUTO_CONNECT`.
   - Cut `pre_social_login` down to what allauth does not cover. Drop the
     "signup only from the register page" rule, so Google creates accounts
     from the login page too (see Decisions).
   - Keep the PR #72 hardening (lock out the password of an unverified local
     account when linking) unless allauth is shown to cover it.
   - The existing `users/test_adapters.py` cases are the acceptance tests.
4. **Clean up** (#79).
   - Delete `VerificationToken`, `send_verification_email`,
     `send_password_reset_email`, and the custom views and forms they replace.
   - Delete `User.email_verified` and `email_verified_at`, or keep them as a
     read-only property backed by `EmailAddress`.
   - Old `/auth/verify-email/<token>/` and `/auth/reset-password/<token>/` URLs
     redirect to the "request a new link" pages.

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
  the field entirely is a later cleanup.
