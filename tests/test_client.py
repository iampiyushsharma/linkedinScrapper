import httpx
import pytest

from app.exceptions import (
    LinkedInAuthError,
    LinkedInBlockedError,
    LinkedInClientError,
    LinkedInRateLimitError,
)
from app.linkedin.client import LinkedInClient, _generate_jsessionid, _is_retryable


def test_generate_jsessionid():
    js = _generate_jsessionid()
    assert js.startswith("ajax:") and js[5:].isdigit() and len(js) == 24


def test_is_retryable_only_for_transient():
    assert _is_retryable(LinkedInClientError("boom")) is True
    assert _is_retryable(LinkedInAuthError("x")) is False
    assert _is_retryable(LinkedInRateLimitError("x")) is False
    assert _is_retryable(LinkedInBlockedError("x")) is False
    assert _is_retryable(ValueError("x")) is False


@pytest.mark.asyncio
async def test_missing_cookie_raises_immediately():
    c = LinkedInClient()
    c.li_at = None
    with pytest.raises(LinkedInAuthError):
        await c.get_profile("someone")
    await c.close()


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_status_code_mapping(monkeypatch):
    # 5xx is covered by test_is_retryable_only_for_transient; excluded here so
    # the test doesn't sit through tenacity's backoff.
    cases = {
        401: LinkedInAuthError,
        302: LinkedInAuthError,
        429: LinkedInRateLimitError,
    }
    for code, exc in cases.items():
        c = LinkedInClient()
        c.li_at = "x"
        c._http = httpx.AsyncClient(transport=_mock_transport(lambda r, code=code: httpx.Response(code)))
        with pytest.raises(exc):
            await c.get_profile("someone")
        await c.close()


@pytest.mark.asyncio
async def test_non_json_200_is_blocked():
    c = LinkedInClient()
    c.li_at = "x"
    c._http = httpx.AsyncClient(
        transport=_mock_transport(lambda r: httpx.Response(200, text="<html>login</html>"))
    )
    with pytest.raises(LinkedInBlockedError):
        await c.get_profile("someone")
    await c.close()


@pytest.mark.asyncio
async def test_happy_path_returns_merged_graph():
    body = {"data": {"*elements": ["urn:li:fsd_profile:1"]}, "included": [{"entityUrn": "x"}]}

    def handler(request):
        assert 'JSESSIONID="ajax:' in request.headers["cookie"]
        assert request.headers["csrf-token"].startswith("ajax:")
        return httpx.Response(200, json=body, headers={"content-type": "application/json"})

    c = LinkedInClient()
    c.li_at = "valid"
    c._http = httpx.AsyncClient(transport=_mock_transport(handler))
    out = await c.get_profile("someone")  # full=False -> single request
    assert out["data"]["*elements"] == ["urn:li:fsd_profile:1"]
    assert out["included"] == [{"entityUrn": "x"}]
    await c.close()
