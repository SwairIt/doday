"""Live HTTP smoke-test — verifies key endpoints respond as expected.

CLI:  uv run python scripts/smoke_test.py [base_url]
Default base_url: https://getdoday.ru

Exit code: 0 if all green, 1 on any failure (with summary table on stderr).
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Endpoint:
    path: str
    expected_status: int
    label: str


@dataclass(frozen=True)
class Result:
    endpoint: Endpoint
    actual_status: int | None  # None if request failed before getting a response
    error: str | None


# Endpoints checked by `main()`. Adding new public routes? Add them here too.
ENDPOINTS: list[Endpoint] = [
    Endpoint("/", 200, "landing"),
    Endpoint("/privacy", 200, "privacy"),
    Endpoint("/pricing", 200, "pricing"),
    Endpoint("/changelog", 200, "changelog"),
    Endpoint("/roadmap", 200, "roadmap"),
    Endpoint("/help", 200, "help"),
    Endpoint("/help/articles.json", 200, "help-articles"),
    Endpoint("/sitemap.xml", 200, "sitemap"),
    Endpoint("/robots.txt", 200, "robots"),
    Endpoint("/og.svg", 200, "og-image"),
    Endpoint("/favicon.ico", 200, "favicon"),
    Endpoint("/manifest.webmanifest", 200, "pwa-manifest"),
    Endpoint("/service-worker.js", 200, "pwa-sw"),
    Endpoint("/health", 200, "health"),
    Endpoint("/version", 200, "version"),
    Endpoint("/auth/register", 200, "register-page"),
    Endpoint("/auth/login", 200, "login-page"),
    Endpoint("/app/today", 401, "auth-gate-today"),
    Endpoint("/app/inbox", 401, "auth-gate-inbox"),
    Endpoint("/app/calendar", 401, "auth-gate-calendar"),
    Endpoint("/app/profile", 303, "profile-redirects-settings"),
    Endpoint("/miniapp/", 303, "miniapp-redirects-link"),
    Endpoint("/miniapp/link", 200, "miniapp-link-page"),
    Endpoint("/miniapp/assets/miniapp.js", 200, "miniapp-js-bundle"),
]


def check_endpoints(
    base_url: str,
    endpoints: Iterable[Endpoint],
    client: httpx.Client | None = None,
) -> list[Result]:
    """GET every endpoint, collect Result. Caller may pass a pre-built client
    (used in tests with MockTransport)."""
    base_url = base_url.rstrip("/")
    own_client = client is None
    if client is None:
        client = httpx.Client(timeout=10.0, follow_redirects=False)
    results: list[Result] = []
    try:
        for ep in endpoints:
            url = base_url + ep.path
            try:
                resp = client.get(url)
                results.append(Result(ep, resp.status_code, None))
            except (httpx.TimeoutException, httpx.RequestError) as e:
                results.append(Result(ep, None, f"{type(e).__name__}: {e}"))
    finally:
        if own_client:
            client.close()
    return results


def format_result(r: Result) -> str:
    if r.actual_status is None:
        return f"  ✗  {r.endpoint.path:32}  {r.error}"
    if r.actual_status == r.endpoint.expected_status:
        return f"  ✓  {r.endpoint.path:32}  {r.actual_status}"
    return (
        f"  ✗  {r.endpoint.path:32}  got {r.actual_status}, expected {r.endpoint.expected_status}"
    )


def main(argv: list[str] | None = None) -> int:
    # Force UTF-8 stdout/stderr for glyphs on Windows cp1251 console.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:] if argv is None else argv
    base_url = args[0] if args else "https://getdoday.ru"
    print(f"smoke test against {base_url}\n")

    results = check_endpoints(base_url, ENDPOINTS)
    failed = [
        r
        for r in results
        if r.actual_status is None or r.actual_status != r.endpoint.expected_status
    ]

    for r in results:
        print(format_result(r))

    print()
    if failed:
        print(f"{len(failed)} of {len(results)} endpoints failed", file=sys.stderr)
        return 1
    print(f"all {len(results)} green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
