import click
import tempfile
import itertools
import typing as t
import subprocess

from wasabi import Printer
from pathlib import Path
from distutils.spawn import find_executable
from urllib.parse import urlparse

from ts_python_client.cli import ScanCommand
from ts_python_client.commands import parse_cmd_opts_from_args

from .pm import Scanner, Dependency, DependencyScan

msg = Printer()


def __get_scanner_classes():
    from .pm.pypi import PypiScanner
    from .pm.maven import MavenScanner
    from .pm.node import NodeScanner
    from .pm.nuget import NugetScanner

    return [
        PypiScanner,
        MavenScanner,
        NodeScanner,
        NugetScanner
    ]


def scanner_options(f):
    for cls in __get_scanner_classes():
        for opt, opt_params in cls.options().items():
            opt_prefix = cls.name().lower()
            f = click.option(f'--{opt_prefix}:{opt}', f'{opt_prefix}_{opt}', **opt_params)(f)

    return f


def create_scanners(**kwargs) -> [Scanner]:
    scanner_classes = __get_scanner_classes()

    scanner_args = {cls.name().lower(): {} for cls in scanner_classes}
    other_args = {}

    for arg, val in kwargs.items():
        scanner_prefix_pos = arg.find('_')
        if scanner_prefix_pos >= 0:
            scanner_prefix = arg[:scanner_prefix_pos]
            scanner_arg = arg[scanner_prefix_pos + 1:]
            scanner_args[scanner_prefix][scanner_arg] = val
        else:
            other_args[arg] = val

    return [cls(**other_args, **scanner_args[cls.name().lower()]) for cls in scanner_classes]


def do_scan(paths: [Path], **kwargs) -> t.Iterable[DependencyScan]:
    """
    Excutes actual scan routines
    :param paths: List of paths to be scanned
    :return: An iterable over scan results
    """
    scanners = create_scanners(**kwargs)
    for p in paths:
        p = p.resolve()

        for scanner in scanners:
            if scanner.ignore:
                continue

            # with msg.loading(f'Scanning for {name} dependencies...'):
            msg.info(f'Scanning for {scanner.name()} dependencies...')

            try:
                if scan := scanner.scan(p):
                    yield scan

                msg.good(f'{scanner.name()} scan is done!')

            except Exception as err:
                msg.fail(f'An error occured while scanning {scanner.name()} dependencies...')

                if len(err.args) > 1:
                    msg.fail(err.args[1])
                else:
                    msg.fail(err)

                pass


class SyftNotFoundError(Exception):
    pass


def do_scan_with_syft(sources: ScanCommand.Sources,
                      syft_path: t.Optional[Path] = None,
                      syft_opts: t.Optional[t.List[str]] = None) -> t.Iterable[DependencyScan]:
    from .syft import import_scan

    syft_tool = find_executable('syft', syft_path)

    if not syft_tool:
        raise SyftNotFoundError(
            """
'Cannot find Syft executable. Please ensure that the Syft tool is installed on your system 
or specify the path using \'--swift-path\' option.
For the installation instructions please refer to: https://github.com/anchore/syft#installation                     
            """)
    else:
        msg.good('Found Syft: {}'.format(syft_tool))

    for src in sources:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(f'{tmpdir}/scan.json')
            cmd = [syft_tool, str(src), '-o', f'syft-json={output}']
            errcode = subprocess.call(cmd)

            if errcode != 0:
                msg.fail(f'Syft failed to scan {str(src)}. Error code: {errcode}')
                continue

            if scan := import_scan(output):
                if isinstance(src, Path):
                    scan.moduleId = f'{src.name}:{scan.module}'
                else:
                    try:
                        url = urlparse(src)
                        scan.moduleId = f'{url.scheme}:{scan.module}'
                    except ValueError:
                        pass

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
