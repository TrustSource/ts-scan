import requests
import typing as t


class TrustSourceAPI:
    class Error(Exception):
        pass

    def __init__(self, base_url: str, api_key: str):
        self.__base_url = base_url
        self.__headers = {
            'Content-Type': 'application/json',
            'user-agent': f'ts-scan/1.1.0',
            'x-api-key': api_key,
            # 'X-APIKEY': api_key
        }

    def _post(self, path: str, data: dict, base_url=None) -> dict:
        if not base_url:
            base_url = self.__base_url
        resp = requests.post(f'{base_url}/{path}', json=data, headers=self.__headers)
        if resp:
            return resp.json()
        else:
            raise TrustSourceAPI.Error(resp.text)

    def upload_scan(self, data: dict) -> dict:
        return self._post('v2/core/scans', data)

    def find_cves(self, comps: t.List[str]) -> t.List[dict]:
        return self._post('v2/vulnerabilities/cveFindByKey', {
            'comps': [{'key': comp} for comp in comps]
        }).get('comps', [])

    def check_components(self, proj_name: str, mod_name: str, comps: t.List[dict]) -> dict:
        return self._post('v2/compliance/check/component', {
            'projectName': proj_name,
            'moduleName': mod_name,
            'components': comps
        })
