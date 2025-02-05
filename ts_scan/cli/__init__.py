# SPDX-FileCopyrightText: 2023 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import click

from pathlib import Path


def start():
    import ts_scan.cli.scan
    import ts_scan.cli.upload
    import ts_scan.cli.analyse
    import ts_scan.cli.check
    import ts_scan.cli.evaluate
    import ts_scan.cli.import_sbom

    cli()


@click.group()
@click.version_option(package_name='ts-scan')
def cli():
    pass


def api_default_options(project_name=True):
    def _apply(f):
        if project_name:
            f = click.option('--project-name', 'project_name',
                             type=str, required=True, help='Project name')(f)

        f = click.option('--api-key', 'api_key',
                         type=str, required=True, help='TrustSource API Key')(f)
        f = click.option('--base-url', 'base_url',
                         default='https://api.trustsource.io', help='TrustSource API base URL')(f)
        return f

    return _apply


def inout_default_options(_in: bool, _out: bool, _fmt: bool):
    def _apply(f):
        if _in:
            f = click.argument('path', type=click.Path(exists=True, path_type=Path))(f)
        if _out:
            f = click.option('-o', '--output', 'output_path', required=False, type=click.Path(path_type=Path),
                             help='Output path for the scan')(f)
        if _fmt:
            f = click.option('-f', '--format', 'scan_format', type=click.Choice(choices=scan_formats),
                             default='ts', help='Scans file format')(f)
        return f

    return _apply


def parse_cmd_opts_from_args(cmd: click.Command, args: [str]):
    ctx = cmd.context_class(cmd)
    with ctx:
        parser = cmd.make_parser(ctx)
        values, _, order = parser.parse_args(args)

    opts = {k: d for (k, d), ty in zip(values.items(), order) if isinstance(ty, click.Option)}
    return opts


cli.api_default_options = api_default_options
cli.inout_default_options = inout_default_options

sbom_formats = {
    'spdx-rdf': 'spdx/rdf',
    'spdx-json': 'spdx/json',
    'cyclonedx': 'cyclonedx'
}

scan_formats = [
    'ts',
    'spdx-tag', 'spdx-json', 'spdx-yaml', 'spdx-xml',
    'cyclonedx-json', 'cyclonedx-xml'
]
