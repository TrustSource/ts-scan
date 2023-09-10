import itertools

import ts_deepscan

from pathlib import Path
from typing import Iterable

from ts_python_client.commands import parse_cmd_opts_from_args

from .pm import DependencyScan


def do_scan(paths: [Path]) -> Iterable[DependencyScan]:
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


__ds_scanner = None
__ds_dataset = None

def process_scan(scan: DependencyScan, enable_deepscan: bool, ds_args: []) -> DependencyScan:
    from ts_deepscan.cli import scan as ds_cmd

    global __ds_scanner
    global __ds_dataset

    if not __ds_scanner and enable_deepscan:
        ds_args = list(itertools.chain.from_iterable(xd.split(',') for xd in ds_args))
        ds_opts = parse_cmd_opts_from_args(ds_cmd, ds_args)

        __ds_scanner = ts_deepscan.create_scanner(**ds_opts)


    if not __ds_dataset:
        if __ds_scanner:
            for analyser in __ds_scanner.analysers:
                if __ds_dataset := getattr(analyser, 'dataset', None):
                    break
        else:
            __ds_dataset = ts_deepscan.create_dataset()

    for dep in scan.iterdeps():
        purl_v = '@' + dep.versions[0] if dep.versions else ''
        purl_ns = '/' + dep.purl_namespace if dep.purl_namespace else ''

        dep.meta['purl'] = f'pkg:{dep.purl_type}{purl_ns}/{dep.name}{purl_v}'

        if (sources := dep.files) and __ds_scanner:
            sources = [Path(src) for src in sources]
            ds_res = ts_deepscan.execute_scan(sources, __ds_scanner, title=dep.key)
            scan.deepscans[dep.key] = ds_res

        if (lic_file := dep.license_file) and lic_file.exists() and __ds_dataset:
            with lic_file.open(errors="surrogateescape") as fp:
                if lic_file_res := ts_deepscan.analyser.textutils.analyse_license_text(fp.read(), __ds_dataset):
                    dep.meta['license_file'] = lic_file_res

    return scan