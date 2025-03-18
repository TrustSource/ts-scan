import click
import typing as t
import ts_deepscan

from pathlib import Path

from . import cli, load_scans_from_file
from .scan import output_scans
from .. import DependencyScan

from ..analyse import analyse_scan_with_ds, analyse_path_with_ds
from ..analyse.scanoss import analyse_scan as analyse_scan_with_scanoss


@cli.command('analyse', help='Analyze scanned dependencies or folder contents')
@cli.inout_default_options(_in=True, _out=True, _fmt=True)
@click.option('--disable-deepscan', default=False, is_flag=True,
              help='Disable scanning of the package\'s sources if available using TrustSource Deepscan')
@click.option('--disable-scanoss', default=False, is_flag=True,
              help='Disable analysing results using ScanOSS scanner')
@click.option('--scanoss-api-key', 'scanoss_api_key', type=str, required=False, help='SCANOSS API Key')
@click.option('--Xdeepscan', default=[], multiple=True,
              help='Specifies an option which should be passed to the TrustSource DeepScan')
def analyse_scan(path: Path,
                 output_path: t.Optional[Path],
                 scan_format: str,
                 disable_deepscan: bool,
                 disable_scanoss: bool,
                 scanoss_api_key: t.Optional[str],
                 xdeepscan: tuple[str]):

    xdeepscan = list(xdeepscan)

    if not disable_deepscan:
        if not disable_scanoss and "--include-scanoss-wfp" not in xdeepscan:
            xdeepscan.append("--include-scanoss-wfp")

    analysed_scans = []

    if path.is_dir():
        if not disable_deepscan:
            ds_scan = analyse_path_with_ds(path, ds_args=xdeepscan)
            scan = DependencyScan(module='unknown', moduleId='unknown')
            scan.deepscans['unknown'] = ds_scan

            if not disable_scanoss:
                analyse_scan_with_scanoss(scan, scanoss_api_key)

            analysed_scans.append(scan)
    else:
        scans = load_scans_from_file(path, scan_format)

        for s in scans:
            # Apply DS analysis
            if not disable_deepscan:
                analyse_scan_with_ds(s, ds_args=xdeepscan)

            # Apply ScanOSS analysis
            if not disable_scanoss:
                analyse_scan_with_scanoss(s, scanoss_api_key)

            analysed_scans.append(s)

    output_scans(analysed_scans, output_path)



