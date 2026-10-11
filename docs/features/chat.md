# Chat — Requirements & Design

Buyer-seller messaging via long polling. No WebSockets, no Redis, no deployment changes.

---

## Scope

Buyers can initiate a conversation with a seller about a specific product. Sellers can reply. Both parties can continue the thread. No group chat, no support tickets — one thread per (buyer, seller, product) triple.

---

## Data Model

### `Conversation`

| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `buyer` | FK → User | the initiating buyer |
| `seller` | FK → Seller | the seller |
| `product` | FK → Product (nullable) | context product; nullable so thread survives if product is deleted |
| `created_at` | DateTimeField | auto |
| `updated_at` | DateTimeField | auto, updated on each new message |

Unique together: `(buyer, seller, product)` — one thread per combination.

### `Message`

| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `conversation` | FK → Conversation | |
| `sender` | FK → User | buyer or seller's user |
| `body` | TextField | max 2000 chars |
| `created_at` | DateTimeField | auto |
| `is_read` | BooleanField | default False |

`is_read` is set to `True` when the *other* participant polls/opens the thread.

---

## URLs

All under `/chat/` prefix, login required everywhere.

| URL | Name | Description |
|---|---|---|
| `GET /chat/` | `chat_inbox` | List all conversations for current user |
| `GET /chat/<int:pk>/` | `chat_detail` | Open a conversation thread |
| `POST /chat/<int:pk>/send/` | `chat_send` | Send a message (returns JSON) |
| `GET /chat/<int:pk>/poll/` | `chat_poll` | Long-poll for new messages (returns JSON) |
| `POST /chat/start/` | `chat_start` | Start a new conversation (from product page) |

---

## Views

### `chat_inbox`
- Query all `Conversation` objects where `buyer = request.user` OR `seller__user = request.user`.
- Order by `updated_at DESC`.
- Annotate with unread count for the current user.
- Render `chat/inbox.html`.

### `chat_detail`
- Verify current user is buyer or seller's user — 403 otherwise.
- Mark all messages sent by the other participant as `is_read=True`.
- Render last 100 messages, oldest first.
- Render `chat/detail.html`.

### `chat_send` (POST, JSON response)
- Verify participant, validate body (non-empty, ≤ 2000 chars).
- Create `Message`, touch `conversation.updated_at`.
- Return `{"ok": true, "message": {"id": …, "body": …, "created_at": …, "is_mine": true}}`.
- 400 JSON on validation error.

### `chat_poll` (GET, JSON response)
- Query param: `after=<message_id>` (last seen message id).
- Return all messages in this conversation with `id > after`, newest-first limited to 50.
- Mark fetched messages from the other participant as `is_read=True`.
- Return `{"messages": [...], "unread_total": <int>}`.
- 403 if not participant.

### `chat_start` (POST)
- Body: `seller_id`, `product_id` (optional).
- `get_or_create` a Conversation for `(buyer=request.user, seller=..., product=...)`.
- Redirect to `chat_detail` for the conversation.
- If user is the seller of the product: return 400 (can't message yourself).

---

## Frontend (vanilla JS, no framework)

### Polling loop (in `chat/detail.html`)

```
let lastId = <id of last rendered message>;

async function poll() {
    const res = await fetch(`/chat/<pk>/poll/?after=${lastId}`);
    const data = await res.json();
    if (data.messages.length) {
        appendMessages(data.messages);
        lastId = data.messages[0].id;  // messages are newest-first
    }
    setTimeout(poll, 3000);  // 3 second interval
}
poll();
```

- New messages are appended to the bottom of the thread.
- Auto-scroll to bottom only if user is already near the bottom (within 100px).
- Send button does a `fetch` POST and optimistically appends the message without waiting for the next poll.

### Unread badge in nav
- A `<span id="chat-badge">` in base.html nav shows the total unread count for the current user.
- Polled every 15 seconds via a separate lightweight endpoint (reuse `chat_poll` with `after=0` on inbox, or a dedicated `/chat/unread/` endpoint returning `{"count": N}`).
- Hidden when count is 0.

---

## Entry Point from Product Page

Add a **"Pošalji poruku prodavcu"** button on `product_public_detail.html`, visible to logged-in non-owner buyers. Clicking it POSTs to `chat_start` and lands on the conversation thread.

---

## Permissions & Security

- All chat views require `@login_required`.
- `chat_detail`, `chat_send`, `chat_poll`: verify `request.user == conversation.buyer OR request.user == conversation.seller.user` — raise 403 otherwise.
- `chat_start`: prevent seller messaging their own product.
- Message body sanitised — render with `{{ message.body|escape }}` (Django default), no HTML allowed.
- Rate limit send: max 20 messages per user per minute (use Django's cache-based rate limiting or a simple counter in the session).

---

## Django App Layout

```
chat/
  __init__.py
  models.py          # Conversation, Message
  views.py           # all views above
  urls.py
  forms.py           # MessageForm (body field)
  admin.py
  tests/
    test_models.py
    test_views.py
  templates/
    chat/
      inbox.html
      detail.html
```

Register in `INSTALLED_APPS` and include `chat.urls` at `/chat/` in `config/urls.py`.

---

## Out of Scope (v1)

- File/image attachments
- Message search
- Email notifications for new messages
- Read receipts visible to sender
- Delete/edit messages
- Admin moderation UI (Django admin registration is enough for now)
