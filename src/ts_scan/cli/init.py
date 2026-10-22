import click
import toml

from click.core import ParameterSource

from pathlib import Path

from . import cli, msg, param_default_value, write_private_file


@cli.command('init', help='Initializes a new TrustSource project')
@cli.api_default_options(is_project_name_required=False, is_api_key_required=False)
@click.argument('path', type=click.Path(exists=True, path_type=Path, file_okay=False))
@click.pass_context
def init_project(ctx, path: Path, **kwargs):
    proj_cfg_path = path / 'tsproject.toml'

    if proj_cfg_path.exists():
        msg.info("Project already initialized.")
        return
    else:
        proj_cfg = {}
        for param in ctx.command.params:
            if isinstance(param, click.Option):
                if param.name is None:
                    continue
                # A key taken from the environment stays there instead of being persisted to disk
                if param.name == 'api_key' and \
                        ctx.get_parameter_source('api_key') == ParameterSource.ENVIRONMENT:
                    continue

                value = kwargs.get(param.name)
                if value is not None and value != param_default_value(param, ctx):
                    proj_cfg[param.name] = value

        write_private_file(proj_cfg_path, toml.dumps(proj_cfg))

        if 'api_key' in proj_cfg:
            msg.warn(f"{proj_cfg_path} contains your API key. Do not commit it: add it to .gitignore, "
                     "or omit --api-key and set TS_API_KEY or the user settings file instead.")
