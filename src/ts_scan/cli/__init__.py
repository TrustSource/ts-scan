# SPDX-FileCopyrightText: 2023 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import click
import typing as t

from wasabi import Printer
from pathlib import Path

from ..pm import DependencyScan, load_scans

msg = Printer(line_max=240)


def start():
    import ts_scan.cli.scan
    import ts_scan.cli.analyse
    import ts_scan.cli.check
    import ts_scan.cli.upload
    import ts_scan.cli.import_sbom
    import ts_scan.cli.convert

    cli()


@click.group()
@click.version_option(package_name='ts-scan')
def cli():
    pass


def api_default_options(project_name=True, is_project_name_required=True, project_name_help_hint=''):
    def _apply(f):
        if project_name:
            help_msg = 'Project name'
            if project_name_help_hint:
                help_msg += f' [{project_name_help_hint}]'
            f = click.option('--project-name', 'project_name',
                             type=str, required=is_project_name_required, help=help_msg)(f)

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
        params, _, param_order = parser.parse_args(args=args)

        opts = {}
        for param in param_order:
            if isinstance(param, click.Option):
                value, _ = param.handle_parse_result(ctx, params, [])
                opts[param.name] = value

    return opts


def load_scans_from_file(path: Path, scan_format: str) -> t.List[DependencyScan]:
    try:
        return load_scans(path, scan_format)
    except:
        msg.fail(f"Failed to load scan in the '{scan_format}' format. Please ensure the format is correct.")
        exit(2)


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
