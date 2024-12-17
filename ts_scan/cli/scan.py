import typing as t
from io import StringIO

import click
import click_params

from pathlib import Path
from urllib.parse import urlparse

from . import cli
from .. import (msg,
                do_scan,
                do_scan_with_syft,
                process_scan,
                SyftNotFoundError)

from ..pm import dump_scans


@cli.command('scan')
@cli.inout_default_options(_in=False, _out=True, _fmt=True)
@cli.scanner_options
@click.option('--verbose', default=False, is_flag=True,
              help="Verbose mode")
@click.option('--tag', required=False, type=str,
              help="Project's tag in the VCS")
@click.option('--branch', required=False, type=str,
              help="Project's branch in the VCS")
@click.option('--use-syft', default=False, is_flag=True,
              help='Use Syft scanner for the file system scan')
@click.option('--syft-path', default=None, type=click.Path(path_type=Path),
              help='Path to the Syft executable')
@click.option('--Xsyft', default=[], multiple=True,
              help='Specifies an option with should be passed to the Syft')
@click.argument('sources', type=click_params.FirstOf(click.Path(exists=True, path_type=Path), click.STRING), nargs=-1)
def scan_dependencies(sources: t.List[t.Union[Path, str]],
                      output_path: t.Optional[Path],
                      scan_format: str,
                      verbose: bool,
                      tag: str,
                      branch: str,
                      use_syft: bool,
                      syft_path: t.Optional[Path],
                      xsyft: [],
                      **kwargs):

    def _do_scan():
        if use_syft:
            try:
                yield from do_scan_with_syft(sources, syft_path, syft_opts=xsyft)
            except SyftNotFoundError as err:
                msg.fail(err)
                exit(1)
        else:
            paths = []
            urls = []
            for src in sources:
                if isinstance(src, Path):
                    paths.append(src)
                else:
                    try:
                        url = urlparse(src)
                        if url.scheme == 'file':
                            paths.append(Path(url.path))
                        else:
                            urls.append(src)
                    except ValueError:
                        msg.fail(f'Cannot parse source: {src}')

            yield from do_scan(paths, verbose=verbose, **kwargs)
            if urls:
                msg.info("Scanning URL sources using Syft...")
                try:
                    yield from do_scan_with_syft(urls, syft_path, syft_opts=xsyft)
                except SyftNotFoundError as err:
                    msg.fail(err)

    scans = []
    for s in _do_scan():
        s.tag = tag
        s.branch = branch

        scans.append(process_scan(s))

    output_scans(scans, output_path, scan_format)


def output_scans(scans: list, path: t.Optional[Path], fmt: str = 'ts'):
    if path:
        with path.resolve().open('w') as fp:
            dump_scans(scans, fp, fmt)
    else:
        output = StringIO()
        dump_scans(scans, output, fmt)
        print(output.read())
