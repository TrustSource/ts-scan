import json
import requests
import typing as t

from copy import copy
from pathlib import Path


class TrustSourceAPI:
    class Error(Exception):
        def __init__(self, text: str):
            try:
                data = json.loads(text)
                msg = data.get('message', text)
            except Exception:
                msg = text

            super().__init__(msg)

    def __init__(self, base_url: str, api_key: str):
        self.__base_url = base_url
        self.__headers = {
            'Content-Type': 'application/json',
            'user-agent': f'ts-scan/1.1.0',
            'x-api-key': api_key,
            # 'X-APIKEY': api_key
        }

    def _post(self,
              path: str,
              headers: t.Optional[dict] = None,
              data: t.Optional[t.Any] = None,
              json_data: t.Optional[dict] = None,
              params: t.Optional[dict] = None,
              base_url=None) -> dict:

        if not base_url:
            base_url = self.__base_url

        _headers = copy(self.__headers)

        if headers:
            _headers.update(headers)

        resp = requests.post(f'{base_url}/{path}',
                             json=json_data,
                             data=data,
                             headers=_headers,
                             params=params)

        if resp:
            return resp.json()
        else:
            raise TrustSourceAPI.Error(resp.text)

    def upload_scan(self, data: dict) -> dict:
        return self._post('v2/core/scans', json_data=data)

    def find_cves(self, comps: t.List[str]) -> t.List[dict]:
        return self._post('v2/vulnerabilities/cveFindByKey', json_data={
            'comps': [{'key': comp} for comp in comps]
        }).get('comps', [])

    def check_components(self, proj_name: str, mod_name: str, comps: t.List[dict]) -> dict:
        return self._post('v2/compliance/check/component', json_data={
            'projectName': proj_name,
            'moduleName': mod_name,
            'components': comps
        })

    def import_sbom(self, sbom_path: Path, sbom_format: str, params: dict) -> dict:
        with sbom_path.open('r') as fp:
            return self._post(f'v2/core/imports/scan/{sbom_format}', data=fp.read(), params=params)
