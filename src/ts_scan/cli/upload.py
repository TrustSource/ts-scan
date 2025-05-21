import json
import ts_deepscan

from tqdm import tqdm
from pathlib import Path

from . import cli, msg, load_scans_from_file
from ..pm import DependencyScan, dump_scans
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

    scans = load_scans_from_file(path, scan_format)

    # Store upload results
    def store_scans():
        with path.open('w') as fp:
            dump_scans(scans, fp, scan_format)

    for scan in scans:
        _upload_deepscans(scan, ds_base_url, api_key, store_scans)
        _upload_scan(scan, project_name, api)


def _upload_deepscans(scan: DependencyScan, ds_base_url: str, api_key: str, store_scans):
    uploaded = {}
    deepscans = {k: ds for k, ds in scan.deepscans.items() if ds.stats['total'] > 0}

    if not deepscans:
        return

    # Upload Deepscan (if not already uploaded)
    for k, ds in tqdm(deepscans.items(), desc='Uploading deepscans'):
        if ds.uid or ts_deepscan.upload_scan(ds, module_name=k, api_key=api_key, base_url=ds_base_url):
            uploaded[k] = ds
            store_scans()

    # Assigne upload results (uid and url) to dependencies
    for dep in scan.iterdeps_once():
        if ds := uploaded.get(dep.key):
            ver = dep.version

            if not ver:
                ver = 'unknown'

            dep.meta['versions'] = [{
                'version': ver,
                'deepScanId': ds.uid,
                'deepScanUrl': ds.url
            }]

    store_scans()


def _upload_scan(scan: DependencyScan, project_name: str, api: TrustSourceAPI):
    msg.info('Uploading dependencies scan...')

    try:
        # noinspection PyUnresolvedReferences
        data = scan.to_dict().copy()

        # Remove local data
        data.pop('deepscans', None)
        data.pop('source', None)

        # Add required data
        data['project'] = project_name

        resp = api.upload_scan(data)
        msg.good("Transfer success!")

        # print(json.dumps(resp, indent=2))

    except TrustSourceAPI.Error as err:
        msg.fail("Transfer failed")
        msg.fail(text=err)
