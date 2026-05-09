"""Morning email digest — sent daily to opt-in users at 7:00 МСК.

The cron worker on prod (system crontab) calls
`POST /api/digest/cron-trigger?token=<secret>` once a day; the endpoint runs
`send_morning_digests_for_all_users(session)` which iterates over users with
`morning_digest_enabled=True`, composes a per-user letter, sends it via SMTP
and marks `morning_digest_last_sent_at` to dedupe within the day.
"""
