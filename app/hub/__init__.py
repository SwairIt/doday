"""Doday Studio hub — the new root landing at `getdoday.ru/`.

Doday is no longer a single product (todo-list). It's an umbrella for several
solo-built products on shared infrastructure:

- **Doday Tasks** — original todo + teams app → `/doday`, app at `/doday/app/today`
- **Lessio** — Telegram-кабинет for tutors → `/lessio`
- **Беллстрой ТВ** — meme arcade game → `/game`
- **Tap Tower** — clicker mini-app → `/taptower`

Hub page renders a cards layout with each project's status (Active / Validation
/ Toy / Legacy) so visitors can pick a destination. Moved here from the old
`pages.router.landing` route on 2026-05-25.
"""
