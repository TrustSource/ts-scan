import json
import os
import requests
import typing as t

from copy import copy
from pathlib import Path

DEFAULT_BASE_URL = 'https://api.trustsource.io/v2'
API_VERSION_SUFFIX = '/v2'

# Seconds to wait for the API before giving up; override with the environment variable below
DEFAULT_REQUEST_TIMEOUT = 60
REQUEST_TIMEOUT_ENV = 'TS_REQUEST_TIMEOUT'


def request_timeout() -> float:
    """Returns the API request timeout in seconds: TS_REQUEST_TIMEOUT if set, else the default."""
    raw = os.environ.get(REQUEST_TIMEOUT_ENV)
    if not raw:
        return DEFAULT_REQUEST_TIMEOUT

    try:
        value = float(raw)
    except ValueError:
        value = 0

    if value <= 0:
        raise ValueError(f'{REQUEST_TIMEOUT_ENV} must be a positive number of seconds, got {raw!r}')
    return value


def normalize_base_url(base_url: str) -> str:
    """Returns the base URL ending with the API version, appending '/v2' if it is missing."""
    base_url = base_url.rstrip('/')
    if not base_url.endswith(API_VERSION_SUFFIX):
        base_url += API_VERSION_SUFFIX
    return base_url


class TrustSourceAPI:
    class Error(Exception):
        def __init__(self, text: str):
            try:
                data = json.loads(text)
                msg = data.get('message', text)
            except Exception:
                msg = text

            super().__init__(msg)

    def __init__(self, base_url: str, api_key: str, timeout: t.Optional[float] = None):
        self.__base_url = normalize_base_url(base_url)
        self.__timeout = timeout if timeout is not None else request_timeout()
        self.__headers = {
            'Content-Type': 'application/json',
            'user-agent': f'ts-scan/1.1.0',
            'x-api-key': api_key,
            # 'X-APIKEY': api_key
        }

    @property
    def base_url(self) -> str:
        return self.__base_url

    def _timeout_error(self) -> 'TrustSourceAPI.Error':
        return TrustSourceAPI.Error(f'The TrustSource API did not respond within {self.__timeout:g} seconds. '
                                    f'Raise the limit with {REQUEST_TIMEOUT_ENV} if the request is expected to take longer.')

    def _post(self,
              path: str,
              headers: t.Optional[dict] = None,
              data: t.Optional[t.Any] = None,
              json_data: t.Optional[dict] = None,
              params: t.Optional[dict] = None) -> dict:
        _headers = copy(self.__headers)

        if headers:
            _headers.update(headers)

        try:
            resp = requests.post(f'{self.__base_url}/{path}',
                                 json=json_data,
                                 data=data,
                                 headers=_headers,
                                 params=params,
                                 timeout=self.__timeout)
        except requests.exceptions.Timeout as err:
            raise self._timeout_error() from err

        if resp:
            return resp.json()
        else:
            raise TrustSourceAPI.Error(resp.text)

    def _get(self, path: str, headers: t.Optional[dict] = None, params: t.Optional[dict] = None) -> dict:
        _headers = copy(self.__headers)

        if headers:
            _headers.update(headers)

        try:
            resp = requests.get(f'{self.__base_url}/{path}',
                                headers=_headers,
                                params=params,
                                timeout=self.__timeout)
        except requests.exceptions.Timeout as err:
            raise self._timeout_error() from err

        if resp:
            return resp.json()
        else:
            raise TrustSourceAPI.Error(resp.text)

    def upload_scan(self, data: dict) -> dict:
        return self._post('core/scans', json_data=data)

    def find_cves(self, comps: t.List[str]) -> t.List[dict]:
        return self._post('vulnerabilities/cveFindByKey', json_data={
            'comps': [{'key': comp} for comp in comps]
        }).get('comps', [])

    def check_components(self, proj_name: str, mod_name: str, comps: t.List[dict]) -> dict:
        return self._post('compliance/check/component', json_data={
            'projectName': proj_name,
            'moduleName': mod_name,
            'components': comps
        })

    def import_sbom(self, sbom_path: Path, sbom_format: str, params: dict) -> dict:
        with sbom_path.open('r') as fp:
            return self._post(f'core/imports/scan/{sbom_format}', data=fp.read(), params=params)

    def get_analysis_results(self, scan_id: str) -> dict:
        return self._get(f'core/scans/{scan_id}')