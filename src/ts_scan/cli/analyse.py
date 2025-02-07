import click
import typing as t

from pathlib import Path

from . import cli
from .scan import output_scans

from ..pm import load_scans
from ..analyse import analyse_with_ds, analyse_with_scanoss


@cli.command('analyse', help='Analyse the scan result')
@cli.inout_default_options(_in=True, _out=True, _fmt=True)
@click.option('--disable-deepscan', default=False, is_flag=True,
              help='Disable scanning of the package\'s sources if available using TrustSource Deepscan')
@click.option('--disable-scanoss', default=False, is_flag=True,
              help='Disable analysing results using ScanOSS scanner')
@click.option('--Xdeepscan', default=[], multiple=True,
              help='Specifies an option which should be passed to the TrustSource DeepScan')
def analyse_scan(path: Path,
                 output_path: t.Optional[Path],
                 scan_format: str,
                 disable_deepscan: bool,
                 disable_scanoss: bool,
                 xdeepscan: []):

    scans = load_scans(path, scan_format)

    analysed_scans = []
    for s in scans:
        # Apply DS analysis
        if not disable_deepscan:
            s = analyse_with_ds(s, ds_args=xdeepscan)

        # Apply ScanOSS analysis
        if not disable_scanoss:
            s = analyse_with_scanoss(s)

        analysed_scans.append(s)

    output_scans(analysed_scans, output_path)
