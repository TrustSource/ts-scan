import click
import typing as t

from pathlib import Path

from . import cli
from .scan import output_scans

from .. import msg, analyse_with_ds
from ..pm import load_scans


@cli.command('analyse')
@cli.inout_default_options(_in=True, _out=True, _fmt=True)
@click.option('--disable-deepscan', default=False, is_flag=True,
              help='Disable scanning of the package\'s sources if available using TrustSource Deepscan')
@click.option('--Xdeepscan', default=[], multiple=True,
              help='Specifies an option which should be passed to the TrustSource DeepScan')
def analyse_scan(path: Path,
                 output_path: t.Optional[Path],
                 scan_format: str,
                 disable_deepscan: bool,
                 xdeepscan: []):

    with path.open('r') as fp:
        scans = load_scans(fp, scan_format)

    analysed_scans = []
    for s in scans:

        # Apply DS analysis
        if not disable_deepscan:
            s = analyse_with_ds(s, ds_args=xdeepscan)

        analysed_scans.append(s)

    output_scans(scans, output_path)
