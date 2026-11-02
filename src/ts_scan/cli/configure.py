import click
import toml

from click.core import ParameterSource

from . import cli, msg, update_private_file


def _mask(value: str) -> str:
    return '***' if len(value) <= 5 else f'{value[:5]}***'


@cli.command('configure', help='Stores the TrustSource API key and base URL in a profile of the ts-scan config')
@click.option('--api-key', 'api_key', type=str, help='TrustSource API Key')
@click.option('--base-url', 'base_url', type=str, help="TrustSource API base URL, '/v2' is appended if missing")
@click.pass_context
def configure(ctx, **kwargs):
    cfg = ctx.obj['config']
    cfg_path = ctx.obj['config_path']
    profile = ctx.parent.params['profile']

    # Only values passed on the command line are stored, so a key from the environment stays there
    updates = {name: value for name, value in kwargs.items()
               if value is not None and ctx.get_parameter_source(name) == ParameterSource.COMMANDLINE}

    settings = cfg.setdefault(profile, {})

    if not updates:
        msg.info(f"Profile '{profile}' in {cfg_path}:")
        for name in kwargs:
            value = settings.get(name)
            if value is not None and name == 'api_key':
                value = _mask(value)
            msg.text(f"  {name} = {value if value is not None else '(not set)'}")
        return

    settings.update(updates)
    update_private_file(cfg_path, toml.dumps(cfg))
    msg.good(f"Updated profile '{profile}' in {cfg_path}")
