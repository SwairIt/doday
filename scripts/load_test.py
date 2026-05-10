"""Light load-test для baseline: N concurrent клиентов × T секунд бьют по
ключевым endpoint'ам. Цель — увидеть p50/p95/p99 latency и error-rate перед
Habr-launch. Не stress-test (он ломает прод); лёгкая нагрузка чтобы понять
выдержит ли первые 100-500 одновременных юзеров.

Запуск:
    uv run python scripts/load_test.py https://getdoday.ru 50 30

  base_url   — без trailing slash
  concurrent — сколько одновременных воркеров (50 — типичный Habr-frontpage)
  duration   — сколько секунд бить (30 хватает чтоб увидеть p99)

Цели для green:
- p95 < 2.0s
- error-rate < 1%
- RPS reasonable (не 0.5)
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field

import httpx

# Анонимные публичные endpoint'ы — не требуют auth, безопасно бить.
PUBLIC_ENDPOINTS: list[str] = [
    "/",
    "/pricing",
    "/help",
    "/changelog",
    "/roadmap",
    "/privacy",
    "/sitemap.xml",
    "/robots.txt",
    "/manifest.webmanifest",
    "/health",
]


@dataclass
class Result:
    latencies_ms: list[float] = field(default_factory=list)
    statuses: Counter[int] = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)


async def worker(base_url: str, deadline: float, result: Result, client: httpx.AsyncClient) -> None:
    i = 0
    while time.monotonic() < deadline:
        path = PUBLIC_ENDPOINTS[i % len(PUBLIC_ENDPOINTS)]
        i += 1
        t0 = time.perf_counter()
        try:
            r = await client.get(base_url + path)
            elapsed = (time.perf_counter() - t0) * 1000
            result.latencies_ms.append(elapsed)
            result.statuses[r.status_code] += 1
        except (httpx.TimeoutException, httpx.RequestError) as e:
            result.errors.append(f"{type(e).__name__}: {e}")


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, round((p / 100.0) * (len(s) - 1))))
    return s[k]


async def run(base_url: str, concurrent: int, duration: int) -> int:
    print(f"target: {base_url} | concurrent={concurrent} | duration={duration}s")
    print(f"endpoints: {len(PUBLIC_ENDPOINTS)} (rotating round-robin per worker)")
    print()

    deadline = time.monotonic() + duration
    result = Result()

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False, http2=False) as client:
        await asyncio.gather(
            *[worker(base_url, deadline, result, client) for _ in range(concurrent)]
        )

    n = len(result.latencies_ms)
    n_err = len(result.errors)
    n_total = n + n_err
    rps = n_total / duration if duration > 0 else 0.0

    print(f"requests:  {n_total}  ({rps:.1f} RPS)")
    print(f"errors:    {n_err}  ({(n_err / n_total * 100) if n_total else 0:.2f}%)")
    print()
    print("status code distribution:")
    for code, cnt in sorted(result.statuses.items()):
        print(f"  {code}: {cnt}")
    print()
    if result.latencies_ms:
        ms = result.latencies_ms
        print("latency (ms):")
        print(f"  min:  {min(ms):.0f}")
        print(f"  p50:  {percentile(ms, 50):.0f}")
        print(f"  p95:  {percentile(ms, 95):.0f}")
        print(f"  p99:  {percentile(ms, 99):.0f}")
        print(f"  max:  {max(ms):.0f}")
        print(f"  mean: {statistics.mean(ms):.0f}")
    if result.errors:
        print()
        print("first 5 errors:")
        for e in result.errors[:5]:
            print(f"  {e}")

    # Green criteria for pre-Habr baseline.
    p95 = percentile(result.latencies_ms, 95) if result.latencies_ms else 0.0
    err_rate = (n_err / n_total) if n_total else 0.0
    print()
    if p95 < 2000 and err_rate < 0.01 and rps > 5:
        print("GREEN — p95 < 2s, errors < 1%, RPS reasonable")
        return 0
    print("YELLOW/RED — see numbers above")
    return 1


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 1:
        print("usage: load_test.py <base_url> [concurrent=20] [duration=30]")
        return 2
    base_url = args[0].rstrip("/")
    concurrent = int(args[1]) if len(args) > 1 else 20
    duration = int(args[2]) if len(args) > 2 else 30
    return asyncio.run(run(base_url, concurrent, duration))


if __name__ == "__main__":
    sys.exit(main())
