import tempfile
import itertools
import typing as t
import subprocess

from wasabi import msg
from pathlib import Path
from distutils.spawn import find_executable

from ts_python_client.commands import parse_cmd_opts_from_args

from .pm import Dependency, DependencyScan


def do_scan(paths: [Path]) -> t.Iterable[DependencyScan]:
    """
    Imports and excutes actual scan routines
    :param paths: List of paths to be scanned
    :return: An iterable over scan results
    """
    from .pm.pypi import scan as pypi_scan
    from .pm.maven import scan as maven_scan

    for p in paths:
        p = p.resolve()

        if scan := pypi_scan(p):
            yield scan

        if scan := maven_scan(p):
            yield scan


def do_scan_with_syft(paths: [Path],
                      syft_path: t.Optional[Path] = None,
                      syft_opts: t.Optional[t.List[str]] = None) -> t.Iterable[DependencyScan]:
    from .spdx import scan as spdx_scan

    syft_tool = find_executable('syft', syft_path)

    if not syft_tool:
        print('Cannot find Syft executable. Please ensure that the Syft tool is installed on your system or specify '
              'the path using \'--swift-path\' option.')
        print('For the installation instructions please refer to: https://github.com/anchore/syft#installation')
        exit(2)
    else:
        msg.good('Found Syft: {}'.format(syft_tool))

    for p in paths:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(f'{tmpdir}/{p.name}.spdx.json')
            cmd = [syft_tool, str(p), '-o', f'spdx-json={output}']
            errcode = subprocess.call(cmd)

            if errcode != 0:
                msg.fail(f'Syft failed to scan with the error code {errcode}')
                exit(2)

            if scan := spdx_scan(output):
                scan.module = p.name
                scan.moduleId = f'image:{scan.module}'

                yield scan


def process_scan(scan: DependencyScan) -> DependencyScan:
    for dep in scan.iterdeps():
        __process_dep(dep)

    return scan


def process_scan_with_ds(scan: DependencyScan, ds_args: t.List[str]) -> DependencyScan:
    import ts_deepscan
    import ts_deepscan.cli
    import ts_deepscan.analyser.textutils

    global __ds_scanner
    global __ds_dataset

    if not __ds_scanner:
        ds_args = list(itertools.chain.from_iterable(xd.split(',') for xd in ds_args))
        ds_opts = parse_cmd_opts_from_args(ts_deepscan.cli.scan, ds_args)

        __ds_scanner = ts_deepscan.create_scanner(**ds_opts)

    if not __ds_dataset:
        if __ds_scanner:
            for analyser in __ds_scanner.analysers:
                if __ds_dataset := getattr(analyser, 'dataset', None):
                    break
        else:
            __ds_dataset = ts_deepscan.create_dataset()

    for dep in scan.iterdeps():
        __process_dep(dep)

        if (sources := dep.files) and __ds_scanner:
            sources = [Path(src) for src in sources]
            ds_res = ts_deepscan.execute_scan(sources, __ds_scanner, title=dep.key)
            scan.deepscans[dep.key] = ds_res

        if (lic_file := dep.license_file) and lic_file.exists() and __ds_dataset:
            with lic_file.open(errors="surrogateescape") as fp:
                if lic_file_res := ts_deepscan.analyser.textutils.analyse_license_text(fp.read(), __ds_dataset):
                    dep.meta['license_file'] = lic_file_res

    return scan


__ds_scanner = None
__ds_dataset = None


def __process_dep(dep: Dependency):
    purl_v = '@' + dep.versions[0] if dep.versions else ''
    purl_ns = '/' + dep.purl_namespace if dep.purl_namespace else ''

    dep.meta['purl'] = f'pkg:{dep.purl_type}{purl_ns}/{dep.name}{purl_v}'
