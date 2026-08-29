# English submissions: ready-to-paste texts

Long-form article: `/marketing-preview/english-bots-ai-seo/raw` (dev.to front
matter already included — set `published: true` and fill `canonical_url` after
the first publication).

Post the long form on dev.to first, then link to it everywhere else. Cross-posts
without a canonical URL compete with the original in search, and the original
doesn't always win.

---

## Hacker News

Submit as a link to the dev.to post, not as Show HN — Show HN is for products,
this is a write-up.

**Title** (pick one, keep it under 80 characters):

```
Your IP rate limit is one header away from useless
```

```
I found 12 holes in my own product after 176 bots signed up
```

**First comment** (post it right after submitting — HN expects the author to
add context):

```
Author here. Short version of what's in the post:

- My rate limit ran on --forwarded-allow-ips='*', so uvicorn took the leftmost
  X-Forwarded-For value — the one the client writes. Forty requests with a
  rotating header, zero rejections. Every IP-based limit I had was decorative.
- json.dumps() into a <script type="application/ld+json"> block is not safe:
  the HTML parser closes the tag at the first </script sequence regardless of
  JSON string boundaries. A question title was enough to get stored XSS on a
  public page.
- finally in an async generator is not a place to persist state. When the
  client disconnects, GeneratorExit lands at the yield and the DB session is
  already closing, so the "save whatever we collected" block silently did
  nothing.

Happy to answer questions about any of it, including the parts I got wrong.
```

Best time: 8–10 a.m. New York, Tuesday to Thursday. Stay near the thread for
the first two hours — that matters more than the title.

---

## r/Python

**Title:**

```
A user's disconnect was silently eating AI responses — and other things I found
after auditing my own FastAPI project
```

Post the full text. Do not put links in the first paragraph — the automod
removes those. Put the repository link at the end, once.

**Opening paragraph to lead with:**

```
Four months into building a FastAPI monolith solo, 176 bots signed up in two
weeks. Fixing that turned into a full audit of my own code: signed form
timestamps instead of a memory-based rate limit, an IDOR in a JSON endpoint the
HTML view guarded correctly, stored XSS through JSON-LD, and an async generator
whose finally block never ran on client disconnect. Code and explanations below.
```

---

## r/webdev

**Title:**

```
json.dumps() inside a <script> tag is not safe — how a question title became
stored XSS on my public pages
```

Post the XSS section plus the session-epoch section, ~600 words, with a link to
the full write-up at the end.

---

## r/netsec

**Title:**

```
Forging X-Forwarded-For against uvicorn behind nginx: why
--forwarded-allow-ips='*' makes IP rate limits decorative
```

Strictly the technical part: the uvicorn source, the nginx header order, the
40-request table, the fix. No product mentions at all — r/netsec removes posts
that read like promotion.

---

## Indie Hackers / r/SideProject

**Title:**

```
176 bots signed up to my side project. The audit that followed found 12 holes
I'd written myself.
```

Lead with the product story, not the code: four months solo, what the bots cost
in time, what the audit changed, what it means for a one-person product. Link
the technical write-up for those who want the details.

---

## Lobste.rs

Link submission, tags: `security`, `python`, `web`. Needs an invite — ask
someone who's already there. Same title as Hacker News.

---

## Cross-post checklist

1. dev.to first — it becomes the canonical URL for everything else.
2. Hashnode and Medium: paste with `canonical_url` pointing at dev.to.
3. Every Reddit post gets its own excerpt, not the same text. Same wording in
   five subreddits reads as spam and gets removed.
4. Answer comments in the first two hours. Everywhere.
