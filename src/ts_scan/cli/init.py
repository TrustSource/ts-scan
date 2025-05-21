import click
import toml

from pathlib import Path

from . import cli, msg, param_default_value


@cli.command('init', help='Initializes a new TrustSource project')
@cli.api_default_options(is_project_name_required=False)
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
                value = kwargs.get(param.name)
                if value is not None and value != param_default_value(param, ctx):
                    proj_cfg[param.name] = value

        with proj_cfg_path.open('w') as fp:
            cfg_str = toml.dumps(proj_cfg)
            fp.write(cfg_str)
