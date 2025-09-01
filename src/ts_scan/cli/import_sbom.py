import click

from pathlib import Path

from . import cli, msg, sbom_formats
from ..api import TrustSourceAPI


@cli.command('import', help='Imports SBOM documents directly to TrustSource API')
@click.option('-f', '--format', 'sbom_format', type=click.Choice(choices=list(sbom_formats)), required=True,
              help='SBOM file format')
@click.option('-v', '--version', 'version', type=str, required=True, help='SBOM format version')
@click.option('--module', 'module', type=str, required=True, help='Module name')
@click.option('--module-id', 'moduleId', type=str, required=True, help='Module identifier')
@click.option('--pkg-type', 'pkgType', type=str, help='Type of pkg to apply for included components')
@click.option('--release', type=str, help='Release identifier')
@click.option('--branch', type=str, help='Code branch')
@click.option('--tag', type=str, help='Code tag')
@cli.inout_default_options(_in=True, _out=False, _fmt=False)
@cli.api_default_options()
def import_sbom(path: Path,
                api_key: str,
                base_url: str,
                project_name: str,
                sbom_format: str,
                **kwargs):

    api = TrustSourceAPI(base_url, api_key)

    params = {k: v for k, v in kwargs.items() if v}
    params['project'] = project_name

    msg.info('Importing a SBOM...')

    try:
        _ = api.import_sbom(path, sbom_format, params)
        msg.good("Transfer success!")

    except TrustSourceAPI.Error as err:
        msg.fail(f"Import failed: {err}")
