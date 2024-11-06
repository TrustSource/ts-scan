# SPDX-FileCopyrightText: 2023 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import json
import click
import requests
import itertools
import typing as t

import ts_deepscan

from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from alive_progress import alive_bar

from ts_python_client.cli import get_start_cmd, scan, upload, ScanCommand, UploadCommand
from ts_python_client.commands import parse_cmd_opts_from_args

from . import msg, do_scan, do_scan_with_syft, process_scan, process_scan_with_ds, scanner_options, SyftNotFoundError

from .pm import DependencyScan

start = get_start_cmd(package_name='ts-scan')


def main():
    start()


@click.option('--verbose', default=False, is_flag=True,
              help="Verbose mode")
@click.option('--tag', required=False, type=str,
              help="Project's tag in the VCS")
@click.option('--branch', required=False, type=str,
              help="Project's branch in the VCS")
@click.option('--use-syft', default=False, is_flag=True,
              help='Use Syft scanner for the file system scan')
@click.option('--syft-path', default=None, type=click.Path(path_type=Path),
              help='Path to the Syft executable')
@click.option('--Xsyft', default=[], multiple=True,
              help='Specifies an option with should be passed to the Syft')
@click.option('--enable-deepscan', default=False, is_flag=True,
              help='Enables scanning of the package\'s sources if available')
@click.option('--Xdeepscan', default=[], multiple=True,
              help='Specifies an option which should be passed to the DeepScan')
@scanner_options
@scan.impl
def scan_dependencies(sources: ScanCommand.Sources, verbose: bool, tag: str, branch: str,
                      use_syft: bool, syft_path: t.Optional[Path], xsyft: [],
                      enable_deepscan: bool, xdeepscan: [], **kwargs) -> Iterable[DependencyScan]:

    def _do_scan():
        if use_syft:
            try:
                yield from do_scan_with_syft(sources, syft_path, syft_opts=xsyft)
            except SyftNotFoundError as err:
                msg.fail(err)
                exit(2)
        else:
            paths = []
            urls = []
            for src in sources:
                if isinstance(src, Path):
                    paths.append(src)
                else:
                    try:
                        url = urlparse(src)
                        if url.scheme == 'file':
                            paths.append(Path(url.path))
                        else:
                            urls.append(src)
                    except ValueError:
                        msg.fail(f'Cannot parse source: {src}')

            yield from do_scan(paths, verbose=verbose, **kwargs)
            if urls:
                msg.info("Scanning URL sources using Syft...")
                try:
                    yield from do_scan_with_syft(urls, syft_path, syft_opts=xsyft)
                except SyftNotFoundError as err:
                    msg.fail(err)

    for s in _do_scan():
        s.tag = tag
        s.branch = branch

        if enable_deepscan:
            yield process_scan_with_ds(s, ds_args=xdeepscan)
        else:
            yield process_scan(s)


@click.option('--Xdeepscan',
              default=[],
              multiple=True,
              help='Specifies an option which should be passed to the DeepScan (used when DeepScan results are '
                   'uploaded)')
@upload.impl
def upload_data(data, base_url, api_key, xdeepscan: [str]):
    from ts_deepscan.cli import upload as ds_cmd

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
            if ds := deepscans_uploaded.get(d['key'], None):
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
    upload.default(data, base_url, api_key)


__sbom_formats = {
    'spdx-rdf': 'spdx/rdf',
    'spdx-json': 'spdx/json',
    'cyclonedx': 'cyclonedx'
}


@start.command('import')
@click.option('-f', '--format', 'sbom_format', type=click.Choice(choices=list(__sbom_formats.keys())), required=True,
              help='SBOM file format')
@click.option('-v', '--version', 'version', type=str, required=True, help='SBOM format version')
@click.option('--project-name', 'project', type=str, required=True, help='Project name')
@click.option('--module', 'module', type=str, required=True, help='Module name')
@click.option('--module-id', 'moduleId', type=str, required=True, help='Module identifier')
@click.option('--api-key', 'api_key', type=str, required=True, help='TrustSource API Key')
@click.option('--pkg-type', 'pkgType', type=str, help='Type of pkg to apply for included components')
@click.option('--release', type=str, help='Release identifier')
@click.option('--branch', type=str, help='Code branch')
@click.option('--tag', type=str, help='Code tag')
@click.option('--base-url', 'base_url', default=UploadCommand.baseUrl, help='TrustSource API base URL')
@click.argument('path', type=click.Path(exists=True, path_type=Path))
def import_sbom(sbom_format: str, **kwargs):
    path: Path = kwargs.pop('path')
    api_key: str = kwargs.pop('api_key')
    base_url: str = kwargs.pop('base_url')

    if sbom_format not in __sbom_formats:
        print('Unsupported SBOM format')
        exit(2)

    url = f'{base_url}/core/imports/scan/{__sbom_formats[sbom_format]}'

    headers = {
        'Accept': 'application/json',
        'User-Agent': 'ts-scan/1.0.0',
        'x-api-key': api_key
    }

    params = {k: v for k, v in kwargs.items() if v}

    with path.open('r') as fp:
        if sbom_format == 'cyclonedx':
            data = fp.read()
            headers['Content-Type'] = 'application/json'
            response = requests.post(url, data=data, headers=headers, params=params)
        else:
            content_type = 'application/json' if sbom_format == 'spdx-json' else 'application/xml'
            files = {'file': (path.name, fp, content_type)}
            headers['Content-Type'] = 'multipart/form-data'
            response = requests.post(url, files=files, headers=headers, params=params)

    if response.status_code == 201:
        print("Transfer success!")
        exit(0)
    else:
        print(json.dumps(response.text, indent=2))
        exit(2)
