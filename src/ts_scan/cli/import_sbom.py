import json
import click
import requests

from pathlib import Path

from . import cli, api_default_options, sbom_formats


@cli.command('import', help='Imports SBOM documents directly to TrustSource API')
@click.option('-f', '--format', 'sbom_format', type=click.Choice(choices=list(sbom_formats.keys())), required=True,
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

    if sbom_format not in sbom_formats:
        print('Unsupported SBOM format')
        exit(1)

    url = f'{base_url}/core/imports/scan/{sbom_formats[sbom_format]}'

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
