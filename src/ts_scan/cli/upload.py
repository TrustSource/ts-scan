import json
import ts_deepscan

from tqdm import tqdm
from pathlib import Path

from . import cli, load_scans_from_file
from ..api import TrustSourceAPI


@cli.command('upload', help='Transfers scan and analyse results to TrustSource API')
@cli.inout_default_options(_in=True, _out=False, _fmt=True)
@cli.api_default_options()
def upload_scan(path: Path,
                scan_format: str,
                project_name: str,
                base_url: str,
                api_key: str):

    api = TrustSourceAPI(base_url, api_key)
    ds_base_url = f'{base_url}/v2/repository'

    def _do_upload(data: dict):
        deepscans = data.pop('deepscans', {})

        if deepscans := [(k, ds) for k, ds in deepscans.items() if ds['stats']['total'] > 0]:
            deepscans_uploaded = {}

            for k, ds in tqdm(deepscans, desc='Uploading deepscans'):
                if res := ts_deepscan.upload_data(data=ds, module_name=k, api_key=api_key, base_url=ds_base_url):
                    deepscans_uploaded[k] = res

            deps = data.get('dependencies', []).copy()
            while deps:
                dep = deps.pop()
                if ds := deepscans_uploaded.get(dep['key']):
                    if versions := dep.get('versions', []):
                        ver = versions[0]
                    else:
                        ver = 'unknown'

                    meta = dep.get('meta', {})
                    meta['versions'] = [{
                        'version': ver,
                        'deepScanId': ds[0],
                        'deepScanUrl': ds[1]
                    }]
                    dep['meta'] = meta

                deps.extend(dep.get('dependencies', []))

        print('Uploading dependencies scan...')

        try:
            resp = api.upload_scan(data)
            print("Transfer success!")
            print(json.dumps(resp, indent=2))
        except TrustSourceAPI.Error as err:
            print("Transfer failed")
            print(err)

    ######

    scans = load_scans_from_file(path, scan_format)

    for s in scans:
        # noinspection PyUnresolvedReferences
        d = s.to_dict()
        d['project'] = project_name

        _do_upload(d)
