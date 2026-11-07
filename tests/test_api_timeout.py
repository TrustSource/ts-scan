import pytest

from ts_scan import api as api_module
from ts_scan.api import DEFAULT_REQUEST_TIMEOUT, REQUEST_TIMEOUT_ENV, TrustSourceAPI, request_timeout


class _Response:
    ok = True

    def __bool__(self):
        return True

    def json(self):
        return {}


@pytest.fixture
def sent(monkeypatch):
    """Records the keyword arguments of every request made by TrustSourceAPI."""
    calls = []

    def _record(url, **kwargs):
        calls.append(kwargs)
        return _Response()

    monkeypatch.setattr(api_module.requests, 'post', _record)
    monkeypatch.setattr(api_module.requests, 'get', _record)
    monkeypatch.delenv(REQUEST_TIMEOUT_ENV, raising=False)
    return calls


def test_requests_carry_the_default_timeout(sent):
    api = TrustSourceAPI('https://api.trustsource.io', 'key')
    api.upload_scan({})
    api.find_cves(['pypi:x@1'])
    api._get('core/projects')

    assert [c['timeout'] for c in sent] == [DEFAULT_REQUEST_TIMEOUT] * 3


def test_timeout_can_be_set_in_the_environment(sent, monkeypatch):
    monkeypatch.setenv(REQUEST_TIMEOUT_ENV, '180')
    TrustSourceAPI('https://api.trustsource.io', 'key').upload_scan({})

    assert sent[0]['timeout'] == 180


def test_timeout_argument_wins_over_the_environment(sent, monkeypatch):
    monkeypatch.setenv(REQUEST_TIMEOUT_ENV, '180')
    TrustSourceAPI('https://api.trustsource.io', 'key', timeout=5).upload_scan({})

    assert sent[0]['timeout'] == 5


@pytest.mark.parametrize('value', ['abc', '0', '-3'])
def test_invalid_timeout_in_the_environment_is_rejected(monkeypatch, value):
    monkeypatch.setenv(REQUEST_TIMEOUT_ENV, value)

    with pytest.raises(ValueError, match=REQUEST_TIMEOUT_ENV):
        request_timeout()


@pytest.mark.parametrize('method, call', [
    ('post', lambda api: api.upload_scan({})),
    ('get', lambda api: api._get('core/projects')),
])
def test_a_timed_out_request_becomes_an_api_error(monkeypatch, method, call):
    def _timeout(url, **kwargs):
        raise api_module.requests.exceptions.ReadTimeout()

    monkeypatch.setattr(api_module.requests, method, _timeout)
    monkeypatch.delenv(REQUEST_TIMEOUT_ENV, raising=False)

    with pytest.raises(TrustSourceAPI.Error, match=f'within {DEFAULT_REQUEST_TIMEOUT} seconds.*{REQUEST_TIMEOUT_ENV}'):
        call(TrustSourceAPI('https://api.trustsource.io', 'key'))
