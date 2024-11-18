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
from click_params import FirstOf
from urllib.parse import urlparse

from alive_progress import alive_bar

from . import (msg,
               do_scan,
               do_scan_with_syft,
               process_scan,
               process_scan_with_ds,
               scanner_options,
               parse_cmd_opts_from_args,
               SyftNotFoundError)

from .pm import DependencyScan


def api_default_options(f):
    f = click.option('--project-name', 'project_name',
                     type=str, required=True, help='Project name')(f)
    f = click.option('--api-key', 'api_key',
                     type=str, required=True, help='TrustSource API Key')(f)
    f = click.option('--base-url', 'base_url',
                     default='https://api.trustsource.io/v2', help='TrustSource API base URL')(f)
    return f


@click.group()
@click.version_option(package_name='ts-scan')
def start():
    pass


@start.command('scan')
@click.option('-o', '--output', 'output_path', required=False, type=click.Path(path_type=Path),
              help='Output path for the scan')
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
@click.argument('sources', type=FirstOf(click.Path(exists=True, path_type=Path), click.STRING), nargs=-1)
def scan_dependencies(sources: t.List[t.Union[Path, str]],
                      output_path: t.Optional[Path],
                      verbose: bool,
                      tag: str,
                      branch: str,
                      use_syft: bool,
                      syft_path: t.Optional[Path],
                      xsyft: [],
                      enable_deepscan: bool,
                      xdeepscan: [],
                      **kwargs):
    def _do_scan():
        if use_syft:
            try:
                yield from do_scan_with_syft(sources, syft_path, syft_opts=xsyft)
            except SyftNotFoundError as err:
                msg.fail(err)
                exit(1)
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

    scans = []
    for s in _do_scan():
        s.tag = tag
        s.branch = branch

        if enable_deepscan:
            scans.append(process_scan_with_ds(s, ds_args=xdeepscan))
        else:
            scans.append(process_scan(s))

    if output_path:
        output_path = output_path.resolve()
        with output_path.open('w') as fp:
            json.dump(scans, fp, indent=2)
    else:
        json.dumps(scans, indent=2)


@start.command('upload')
@click.option('--Xdeepscan',
              default=[],
              multiple=True,
              help='Specifies an option which should be passed to the DeepScan (used when DeepScan results are '
                   'uploaded)')
@api_default_options
@click.argument('path', type=click.Path(exists=True, path_type=Path))
def upload_scan(path: Path, project_name: str, base_url: str, api_key: str, xdeepscan: [str]):
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
        if scan := json.load(fp):
            if type(scan) is list:
                for s in scan:
                    s['project'] = project_name
                    _do_upload(s)
            elif type(scan) is dict:
                scan['project'] = project_name
                _do_upload(scan)
            else:
                raise ValueError('Unexpected scan type')
        else:
            print("Cannot load scan data")
            exit(1)


@start.command('check')
@click.option('--breakOnLegalIssues', default=True, is_flag=True,
              help="Exit with code 2 in case of legal issues")
@click.option('--breakOnVulnerabilities', default=True, is_flag=True,
              help="Exit with code 2 in case of vulnerabilities")
@click.option('--breakOnViolationsOnly', default=False, is_flag=True,
              help="Exit with code 2 if only violations were found")
@click.option('--breakOnViolationsAndWarnings', default=False, is_flag=True,
              help="Exit with code 2 if violations or warnings were found")
@click.option('--assumeComponentsModified', default=False, is_flag=True,
              help="Assume that components are modified by checking legal settings")
@api_default_options
@click.argument('path', type=click.Path(exists=True, path_type=Path))
def check_scan(project_name: str, base_url: str, api_key: str, path: Path,
               breakOnLegalIssues=True,
               breakOnVulnerabilities=True,
               breakOnViolationsOnly=False,
               breakOnViolationsAndWarnings=False,
               assumeComponentsModified=False,
               **kwargs):
    with path.open('r') as fp:
        data = json.load(fp)

    if type(data) is list:
        scans = [DependencyScan.from_dict(d) for d in data]
    else:
        scans = [DependencyScan.from_dict(data)]

    for scan in scans:
        comps = []

        for dep in scan.iterdeps():
            for v in dep.versions:
                comps.append({
                    'key': dep.key,
                    'name': dep.name,
                    'version': v
                })

        if not comps:
            continue

        check = {
            'projectName': project_name,
            'moduleName': scan.module,
            'components': comps
        }

        headers = {
            'Content-Type': 'application/json',
            'user-agent': 'ts-scan/1.0.0',
            'x-api-key': api_key
        }

        response = requests.post(base_url + 'compliance/check/component', json=check, headers=headers)

        if response.status_code == 200:
            results = response.json()
            for w in results.get('warnings', []):
                comp = f'{w.get("component")}:{w.get("version")}'
                status = w.get('status').replace('_', ' ')
                msg.warn(f'{comp}: {status}')

            if not breakOnLegalIssues and not breakOnVulnerabilities:
                return

            if breakOnLegalIssues:
                violations = 0
                warnings = 0

                for res in results['data']:
                    comp = res['component']
                    comp_key = f'{comp["key"]}:{comp["version"]}'

                    res = res['changed'] if assumeComponentsModified else res['not_changed']
                    for v in res['violations']:
                        log_msg = f'{comp_key}: {v["message"]}'
                        if v['type'] == 'violation':
                            msg.fail(log_msg)
                            violations += 1
                        elif v['type'] == 'warning':
                            msg.warn(log_msg)
                            warnings += 1

                        msg.divider(char=' ')

                if breakOnViolationsAndWarnings and (violations > 0 or warnings > 0):
                    exit(2)

                if breakOnViolationsOnly and violations > 0:
                    exit(2)

            if breakOnVulnerabilities:
                violations = 0
                warnings = 0
                vulns = {}

                for res in results['data']:
                    comp = res['component']
                    comp_key = f'{comp["key"]}:{comp["version"]}'

                    vulns.setdefault(comp_key, [])

                    for v in res['vulnerabilities']:
                        vulns[comp_key].append(v["name"])
                        if v['status'] == 'violations':
                            violations += 1
                        elif v['status'] == 'warning':
                            warnings += 1

                for comp_key, vulns in vulns.items():
                    if vulns:
                        msg.fail(f'{comp_key}:{vulns}')

                if breakOnViolationsAndWarnings and (violations > 0 or warnings > 0):
                    exit(2)

                if breakOnViolationsOnly and violations > 0:
                    exit(2)

        elif 400 <= response.status_code < 500:
            data = response.json()
            if err := data.get('error'):
                msg.fail(err)
            exit(1)
        else:
            msg.fail(f'Check failed with status code: {response.status_code}')
            exit(1)


__sbom_formats = {
    'spdx-rdf': 'spdx/rdf',
    'spdx-json': 'spdx/json',
    'cyclonedx': 'cyclonedx'
}


@start.command('import')
@click.option('-f', '--format', 'sbom_format', type=click.Choice(choices=list(__sbom_formats.keys())), required=True,
              help='SBOM file format')
@click.option('-v', '--version', 'version', type=str, required=True, help='SBOM format version')
@click.option('--module', 'module', type=str, required=True, help='Module name')
@click.option('--module-id', 'moduleId', type=str, required=True, help='Module identifier')
@click.option('--pkg-type', 'pkgType', type=str, help='Type of pkg to apply for included components')
@click.option('--release', type=str, help='Release identifier')
@click.option('--branch', type=str, help='Code branch')
@click.option('--tag', type=str, help='Code tag')
@api_default_options
@click.argument('path', type=click.Path(exists=True, path_type=Path))
def import_sbom(sbom_format: str, **kwargs):
    path: Path = kwargs.pop('path')
    api_key: str = kwargs.pop('api_key')
    base_url: str = kwargs.pop('base_url')

    if sbom_format not in __sbom_formats:
        print('Unsupported SBOM format')
        exit(1)

    url = f'{base_url}/core/imports/scan/{__sbom_formats[sbom_format]}'

    headers = {
        'user-agent': 'ts-scan/1.0.0',
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
        exit(1)
