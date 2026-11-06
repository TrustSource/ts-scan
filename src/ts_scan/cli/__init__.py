# SPDX-FileCopyrightText: 2023 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import os
import click
import tempfile
import typing as t
import toml

from wasabi.printer import Printer
from pathlib import Path

from ..pm import DependencyScan, load_scans
from ..api import DEFAULT_BASE_URL

_default_config_location = '~/.ts-scan/config'

# Tool settings: taken from the command line, the environment or the ts-scan config only,
# never from the project settings of a scanned directory
TOOL_ONLY_OPTIONS = ('api_key', 'base_url')

msg = Printer(line_max=240, colors={'info': 'cyan'})


def start():
    import ts_scan.cli.scan
    import ts_scan.cli.analyse
    import ts_scan.cli.check
    import ts_scan.cli.upload
    import ts_scan.cli.import_sbom
    import ts_scan.cli.convert
    import ts_scan.cli.init
    import ts_scan.cli.configure

    cli()


class CLI(click.Group):
    scanner_options: t.Callable[..., t.Any]
    api_default_options: t.Callable[..., t.Any]
    inout_default_options: t.Callable[..., t.Any]

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

    # 'configure' may create a new profile
    if defaults is None and ctx.invoked_subcommand == 'configure':
        defaults = {}

    if defaults is None:
        msg.fail(f"Profile '{profile}' not found in the config file.")
        exit(1)

    ctx.default_map = defaults

    for sub in ctx.command.commands.values():
        sub.context_settings['default_map'] = defaults

    if args := ctx.obj['args']:
        params = parse_cmd_params_from_args(ctx.command.commands[ctx.invoked_subcommand], args.copy())
        path = params.get('path')
        if path is None:
            # 'scan' takes several sources, the project settings are read from the first local one
            path = next((src for src in params.get('sources') or () if isinstance(src, Path)), None)

        if path:
            if path.is_file():
                try:
                    scans = load_scans(path, ctx.params.get('scan_format', scan_format_default))
                    # Read the 'param' iff. there is only one scan
                    if len(scans) == 1 and scans[0].source:
                        path = Path(scans[0].source)
                except:
                    pass

            if proj_cfg := _load_project_config(path):
                ctx.default_map.update(proj_cfg)


def write_private_file(path: Path, content: str) -> None:
    """Creates a new file readable by the current user only (0600 on POSIX).

    Fails if the file already exists, so a pre-planted file or symlink is never written through.
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as fp:
        fp.write(content)


def _create_default_config() -> Path:
    cfg = {
        'default': {}
    }

    cfg_path = Path(_default_config_location).expanduser()
    if not cfg_path.exists():
        cfg_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_private_file(cfg_path, toml.dumps(cfg))

    return cfg_path


def update_private_file(path: Path, content: str) -> None:
    """Creates or replaces a file readable by the current user only (0600 on POSIX).

    The content is written to a new temporary file that atomically replaces the target, so an
    existing file or symlink at the target is never written through.
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.')
    try:
        with os.fdopen(fd, 'w') as fp:
            fp.write(content)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def _load_project_config(path: Path) -> dict:
    cfg_path = path / 'tsproject.toml'
    if not cfg_path.exists():
        return {}

    proj_cfg = toml.load(cfg_path)
    for key in TOOL_ONLY_OPTIONS:
        if key in proj_cfg:
            del proj_cfg[key]
            msg.warn(f"Ignoring '{key}' in {cfg_path}: the API endpoint and key are only taken from "
                     "the command line, the environment or the ts-scan config (see 'ts-scan configure')")

    return proj_cfg


def api_default_options(project_name=True, is_project_name_required=True, project_name_help_hint='',
                        is_api_key_required=True):
    def _apply(f):
        if project_name:
            help_msg = 'Project name'
            if project_name_help_hint:
                help_msg += f' [{project_name_help_hint}]'

            f = click.option('--project-name', 'project_name',
                             type=str, required=is_project_name_required, help=help_msg)(f)

        f = click.option('--api-key', 'api_key',
                         type=str, required=is_api_key_required, help='TrustSource API Key')(f)

        f = click.option('--base-url', 'base_url',
                         default=DEFAULT_BASE_URL,
                         help="TrustSource API base URL, '/v2' is appended if missing")(f)
        return f

    return _apply


def inout_default_options(_in: bool, _out: bool, _fmt: bool):
    def _apply(f):
        if _in:
            f = click.argument('path',
                               type=click.Path(exists=True, path_type=Path))(f)
        if _out:
            f = click.option('-o', '--output', 'output_path',
                             type=click.Path(path_type=Path, dir_okay=False),
                             required=False,
                             help='Output file for the scan')(f)
        if _fmt:
            f = click.option('-f', '--format', 'scan_format',
                             type=click.Choice(choices=scan_formats),
                             default=scan_format_default,
                             help='Scans file format')(f)
        return f

    return _apply


def parse_cmd_params_from_args(cmd: click.Command, args: t.List[str], only_opts=False) -> t.Dict[str, t.Any]:
    with cmd.context_class(cmd) as ctx:
        parser = cmd.make_parser(ctx)
        params, _, param_order = parser.parse_args(args=args)

    res = {}
    for param in param_order:
        if not only_opts or isinstance(param, click.Option):
            value, _ = param.handle_parse_result(ctx, params, [])
            res[param.name] = value

    return res


def parse_input_from_args(args: t.List[str]) -> t.Optional[Path]:
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
    if param.name is not None and ctx.default_map is not None and param.name in ctx.default_map:
        return ctx.default_map[param.name]
    else:
        return param.default


cli.api_default_options = api_default_options
cli.inout_default_options = inout_default_options

sbom_formats = ['spdx', 'cyclonedx']

scan_formats = [
    'ts',
    'spdx-tag', 'spdx-json', 'spdx-yaml', 'spdx-xml',
    'cyclonedx-json', 'cyclonedx-xml'
]

scan_format_default = 'ts'
