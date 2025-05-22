# SPDX-FileCopyrightText: 2023 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import click
import typing as t
import toml

from wasabi import Printer
from pathlib import Path

from ..pm import DependencyScan, load_scans

_default_config_location = '~/.ts-scan/config'

msg = Printer(line_max=240)


def start():
    import ts_scan.cli.scan
    import ts_scan.cli.analyse
    import ts_scan.cli.check
    import ts_scan.cli.upload
    import ts_scan.cli.import_sbom
    import ts_scan.cli.convert
    import ts_scan.cli.init

    cli()


class CLI(click.Group):
    def invoke(self, ctx):
        ctx.obj = {
            'args': ctx.args
        }
        super().invoke(ctx)


@click.group(cls=CLI, context_settings={'auto_envvar_prefix': 'TS'})
@click.version_option(package_name='ts-scan')
@click.option('--config',
              default=Path(_default_config_location),
              type=click.Path(path_type=Path, dir_okay=False))
@click.option('-p', '--profile', default='default', type=str)
@click.pass_context
def cli(ctx, config: Path, profile: str):
    cfg_path = config.expanduser().resolve(strict=False)

    if not cfg_path.exists():
        cfg_path = _create_default_config()

    cfg_data = toml.load(cfg_path)

    ctx.obj['config'] = cfg_data
    ctx.obj['config_path'] = cfg_path

    defaults = cfg_data.get(profile)

    if defaults is None:
        msg.fail(f"Profile '{profile}' not found in the config file.")
        exit(1)

    ctx.default_map = defaults

    for sub in ctx.command.commands.values():
        sub.context_settings['default_map'] = defaults

    if args := ctx.obj['args']:
        params = parse_cmd_params_from_args(ctx.command.commands[ctx.invoked_subcommand], args.copy())
        if path := params.get('path'):
            if path.is_file():
                try:
                    scans = load_scans(path, ctx.params.get('scan_format', scan_format_default))
                    # Read the 'param' iff. there is only one scan
                    if len(scans) == 1:
                        path = Path(scans[0].source)
                except:
                    pass

            if proj_cfg := _load_project_config(path):
                ctx.default_map.update(proj_cfg)


def _create_default_config() -> Path:
    cfg = {
        'default': {}
    }

    cfg_path = Path(_default_config_location).expanduser()
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)

        with cfg_path.open('w') as fp:
            cfg_str = toml.dumps(cfg)
            fp.write(cfg_str)

    return cfg_path


def _load_project_config(path: Path) -> dict:
    cfg_path = path / 'tsproject.toml'
    if cfg_path.exists():
        return toml.load(cfg_path)

    return {}


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
            f = click.argument('path',
                               type=click.Path(exists=True, path_type=Path))(f)
        if _out:
            f = click.option('-o', '--output', 'output_path',
                             type=click.Path(path_type=Path),
                             required=False,
                             help='Output path for the scan')(f)
        if _fmt:
            f = click.option('-f', '--format', 'scan_format',
                             type=click.Choice(choices=scan_formats),
                             default=scan_format_default,
                             help='Scans file format')(f)
        return f

    return _apply


def parse_cmd_params_from_args(cmd: click.Command, args: [str], only_opts=False) -> t.Dict[str, t.Any]:
    with cmd.context_class(cmd) as ctx:
        parser = cmd.make_parser(ctx)
        params, _, param_order = parser.parse_args(args=args)

    res = {}
    for param in param_order:
        if not only_opts or isinstance(param, click.Option):
            value, _ = param.handle_parse_result(ctx, params, [])
            res[param.name] = value

    return res


def parse_input_from_args(args: [str]) -> t.Optional[Path]:
    input_arg = click.Argument(['path'], type=click.Path(exists=True, path_type=Path))

    parser = click.OptionParser()
    parser.ignore_unknown_options = True
    parser.add_argument(input_arg, 'path')

    _, args, order = parser.parse_args(args=args)

    return None


def load_scans_from_file(path: Path, scan_format: str) -> t.List[DependencyScan]:
    try:
        return load_scans(path, scan_format)
    except:
        msg.fail(f"Failed to load scan in the '{scan_format}' format. Please ensure the format is correct.")
        exit(2)


def param_default_value(param: click.Parameter, ctx: click.Context):
    if param.name in ctx.default_map:
        return ctx.default_map[param.name]
    else:
        return param.default


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

scan_format_default = 'ts'
