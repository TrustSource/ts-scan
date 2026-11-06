import click
import toml

from pathlib import Path

from . import cli, msg, param_default_value, write_private_file


@cli.command('init', help='Initializes a new TrustSource project')
@click.option('--project-name', 'project_name', type=str, required=False, help='Project name')
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

                value = kwargs.get(param.name)
                if value is not None and value != param_default_value(param, ctx):
                    proj_cfg[param.name] = value

        write_private_file(proj_cfg_path, toml.dumps(proj_cfg))
