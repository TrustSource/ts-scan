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
                process_scan)

from ..pm import dump_scans, ExecutableNotFoundError
from ..analyse import obom


@cli.command('scan', help='Scans a target and determines its composition')
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
@click.option('--include-obom', default=False, is_flag=True,
              help=obom.obom_feature_help(
                  'Also extract an OBOM (IAM access graph) from any IaC '
                  '(CloudFormation/SAM, Terraform) found in the local scan sources'))
@click.option('--obom-output', 'obom_output_path', type=click.Path(path_type=Path),
              required=False,
              help='Output path for the OBOM JSON (default: alongside --output, or stdout)')
@click.argument('sources',
                type=click_params.FirstOf(click.Path(exists=True, path_type=Path), click.STRING),
                nargs=-1)
def scan_dependencies(sources: t.List[t.Union[Path, str]],
                      output_path: t.Optional[Path],
                      scan_format: str,
                      verbose: bool,
                      tag: str,
                      branch: str,
                      use_syft: bool,
                      include_obom: bool,
                      obom_output_path: t.Optional[Path],
                      **kwargs):

    def _do_scan():
        try:
            if use_syft:
                yield from do_scan_with_syft(sources, verbose=verbose, **kwargs)
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
                    yield from do_scan_with_syft(urls, verbose=verbose, **kwargs)

        except ExecutableNotFoundError as err:
            msg.fail(err)
            exit(2)

    scans = []
    for s in _do_scan():
        s.tag = tag
        s.branch = branch

        scans.append(process_scan(s))

    if scans:
        output_scans(scans, output_path, scan_format)

    if include_obom:
        # Second pass, independent of the dependency scan above: IaC sources
        # (CloudFormation/SAM, Terraform) aren't tied to a specific
        # package-manager DependencyScan, so this doesn't feed into `scans`
        # -- it's its own artifact. Only local paths are examined (a
        # `file://` URL source is not resolved back to a path here; run
        # against a local checkout for OBOM).
        local_paths = [src for src in sources if isinstance(src, Path)]
        if not local_paths:
            msg.warn('--include-obom: no local paths among the scan sources, skipping')
        else:
            try:
                obom.require_checkov()
            except obom.CheckovNotInstalledError as err:
                msg.fail(str(err))
                exit(2)

            msg.info('Extracting OBOM (IAM access graph) from IaC sources...')
            result = obom.ObomResult()
            for p in local_paths:
                result.extend(obom.extract(str(p)))

            if result.edges or result.unresolved:
                msg.good(f'OBOM extraction done: {len(result.edges)} edges, '
                          f'{len(result.unresolved)} unresolved.')
            else:
                msg.info('OBOM extraction found no IaC-derived IAM grants in the scan sources.')

            output_obom(result, obom_output_path or output_path)


def output_scans(scans: list, path: t.Optional[Path], fmt: str = 'ts'):
    if path:
        with path.resolve().open('w') as fp:
            dump_scans(scans, fp, fmt)
    else:
        output = StringIO()
        dump_scans(scans, output, fmt)
        output.seek(0)
        print(output.read())


def output_obom(result: 'obom.ObomResult', path: t.Optional[Path]):
    import json

    obom_dict = result.to_dict()
    if path:
        # Sibling file next to the main scan output (or the explicit
        # --obom-output path itself), never overwrite --output's own file.
        obom_path = path if path.suffix == '.json' and '.obom' in path.suffixes else \
            path.with_name(f'{path.stem}.obom.json')
        with obom_path.resolve().open('w') as fp:
            json.dump(obom_dict, fp, indent=2)
    else:
        print(json.dumps(obom_dict, indent=2))
