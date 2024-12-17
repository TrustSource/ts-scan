import json
import click
import itertools
import requests

import ts_deepscan

from pathlib import Path
from alive_progress import alive_bar

from . import cli
from .. import parse_cmd_opts_from_args
from ..pm import load_scans


@cli.command('upload')
@cli.inout_default_options(_in=True, _out=False, _fmt=True)
@cli.api_default_options
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

    def _do_upload(data: dict):
        deepscans = data.pop('deepscans', {})

        if deepscans := [(k, d) for k, d in deepscans.items() if d['stats']['total'] > 0]:
            deepscans_uploaded = {}

            ds_args = list(itertools.chain.from_iterable(xd.split(',') for xd in xdeepscan))
            ds_opts = parse_cmd_opts_from_args(ds_cmd, ds_args)

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

        headers = {
            'Content-Type': 'application/json',
            'user-agent': f'ts-scan/1.1.0',
            'x-api-key': api_key
        }

        response = requests.post(base_url + '/core/scans', json=data, headers=headers)

        if response.status_code == 201:
            print("Transfer success!")
            return
        else:
            print(json.dumps(response.text, indent=2))
            exit(2)

    ######

    with path.open('r') as fp:
        scans = load_scans(fp, scan_format)

    for s in scans:
        d = s.todict()
        d['project'] = project_name

        _do_upload(d)
