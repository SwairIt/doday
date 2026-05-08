"""Tests for scripts/smoke_test.py — live-endpoint smoke-test."""

import httpx
import pytest

from scripts.smoke_test import Endpoint, check_endpoints


@pytest.fixture(scope="session", autouse=True)
def _init_test_db() -> None:  # shadows conftest fixture intentionally
    return


def test_all_green_returns_no_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/", 200, "landing")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert len(results) == 1
    assert results[0].actual_status == 200
    assert results[0].actual_status == results[0].endpoint.expected_status


def test_404_on_expected_200_marks_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/", 200, "landing")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status == 404
    assert results[0].actual_status != results[0].endpoint.expected_status


def test_404_where_401_expected_marks_failure() -> None:
    """Critical: protected route disappeared from registry."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/app/today", 401, "auth-gate")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status == 404
    assert results[0].actual_status != results[0].endpoint.expected_status


def test_401_on_protected_endpoint_is_success() -> None:
    """401 on /app/* means auth gate works AND route is registered."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/app/today", 401, "auth-gate")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status == 401
    assert results[0].actual_status == results[0].endpoint.expected_status


def test_timeout_marks_failure_with_error_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/", 200, "landing")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status is None
    assert results[0].error is not None
    assert "Timeout" in results[0].error


def test_does_not_follow_redirects() -> None:
    """A redirect on a 200-expected endpoint is suspicious — keep raw status."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "/other"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    endpoints = [Endpoint("/", 200, "landing")]
    results = check_endpoints("https://example.com", endpoints, client=client)

    assert results[0].actual_status == 302  # not silently followed to 200
