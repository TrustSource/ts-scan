import click
import typing as t

from pathlib import Path

from . import cli, scan_formats
from .scan import output_scans
from ..pm import load_scans


@cli.command('convert', help='Converts SBOM elements from one format to another')
@cli.inout_default_options(_in=True, _out=True, _fmt=True)
@click.option('-of', '--output-format', 'output_format',
              type=click.Choice(choices=scan_formats), default='ts', help='Output SBOM format')
def convert(path: Path,
            output_path: t.Optional[Path],
            scan_format: str,
            output_format: str):
    if scans := load_scans(path, scan_format):
        output_scans(scans, output_path, output_format)
