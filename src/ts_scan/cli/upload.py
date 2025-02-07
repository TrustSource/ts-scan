import json
import click
import itertools

import ts_deepscan

from pathlib import Path
from alive_progress import alive_bar

from . import cli
from ..pm import load_scans
from ..cli import parse_cmd_opts_from_args
from ..api import TrustSourceAPI


@cli.command('upload', help='Transfers scan and analyse results to TrustSource API')
@cli.inout_default_options(_in=True, _out=False, _fmt=True)
@cli.api_default_options()
@click.option('--Xdeepscan',
              default=[],
              multiple=True,
              help='Specifies an option which should be passed to the DeepScan (used when DeepScan results are '
                   'uploaded)')
def upload_scan(path: Path,
                scan_format: str,
                project_name: str,
                base_url: str,
                api_key: str,
                xdeepscan: [str]):
    from ts_deepscan.cli import upload as ds_cmd

    api = TrustSourceAPI(base_url, api_key)

    def _do_upload(data: dict):
        deepscans = data.pop('deepscans', {})

        if deepscans := [(k, ds) for k, ds in deepscans.items() if ds['stats']['total'] > 0]:
            deepscans_uploaded = {}

            ds_args = list(itertools.chain.from_iterable(xd.split(',') for xd in xdeepscan))
            ds_opts = parse_cmd_opts_from_args(ds_cmd, ds_args) # noqa

            with alive_bar(len(deepscans), title='Uploading deepscans') as progress:
                for k, d in deepscans:
                    if res := ts_deepscan.upload_data(data=d, module_name=k, api_key=api_key, **ds_opts):
                        deepscans_uploaded[k] = res
                    progress()

            deps = data.get('dependencies', []).copy()
            while deps:
                d = deps.pop()
                if ds := deepscans_uploaded.get(d['key']):
                    if versions := d.get('versions', []):
                        ver = versions[0]
                    else:
                        ver = 'unknown'

                    meta = d.get('meta', {})
                    meta['versions'] = [{
                        'version': ver,
                        'deepScanId': ds[0],
                        'deepScanUrl': ds[1]
                    }]
                    d['meta'] = meta

                deps.extend(d.get('dependencies', []))

        print('Uploading dependencies scan...')

        try:
            resp = api.upload_scan(data)
            print("Transfer success!")
            print(json.dumps(resp, indent=2))
        except TrustSourceAPI.Error as err:
            print("Transfer failed")
            print(err)

    ######

    scans = load_scans(path, scan_format)

    for s in scans:
        # noinspection PyUnresolvedReferences
        d = s.to_dict()
        d['project'] = project_name

        _do_upload(d)
