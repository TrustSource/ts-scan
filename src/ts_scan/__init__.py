import click
import typing as t

from pathlib import Path

from .pm import Scanner, Dependency, DependencyScan
from .cli import cli, msg


def __get_pm_scanner_classes() -> t.List[t.Type[Scanner]]:
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
    from .pm.syft import SyftScanner

    scanner_classes = __get_pm_scanner_classes()
    scanner_classes.append(SyftScanner)

    for cls in scanner_classes:
        for opt, opt_params in cls.options().items():
            opt_prefix = cls.name().lower()
            f = click.option(f'--{opt_prefix}:{opt}', f'{opt_prefix}_{opt}', **opt_params)(f)

    return f


cli.scanner_options = scanner_options


def create_scanners(scanner_classes: t.Iterable[t.Type[Scanner]], **kwargs) -> [Scanner]:
    scanner_args = {cls.name().lower(): {} for cls in scanner_classes}
    other_args = {}

    for arg, val in kwargs.items():
        scanner_prefix_pos = arg.find('_')
        if scanner_prefix_pos >= 0:
            scanner_prefix = arg[:scanner_prefix_pos]
            scanner_arg = arg[scanner_prefix_pos + 1:]
            if _scanner_args := scanner_args.get(scanner_prefix):
                _scanner_args[scanner_arg] = val
        else:
            other_args[arg] = val

    return [cls(**other_args, **scanner_args[cls.name().lower()]) for cls in scanner_classes]


def do_scan(paths: [Path], **kwargs) -> t.Iterable[DependencyScan]:
    """
    Excutes actual scan routines
    :param paths: List of paths to be scanned
    :return: An iterable over scan results
    """
    scanners = [s for s in create_scanners(__get_pm_scanner_classes(), **kwargs) if not s.ignore]

    for p in paths:
        p = p.resolve()

        for scanner in scanners:
            if not scanner.accepts(p):
                continue

            # with msg.loading(f'Scanning for {name} dependencies...'):
            msg.info(f'Scanning for {scanner.name()} dependencies...')

            if scan := _execute_scan(p, scanner):
                yield scan

            msg.good(f'{scanner.name()} scan is done!')


def do_scan_with_syft(sources: t.List[t.Union[Path, str]], **kwargs) -> t.Iterable[DependencyScan]:
    from .pm.syft import SyftScanner

    if scanners := create_scanners([SyftScanner], **kwargs):
        for src in sources:

            msg.info(f'Scanning for dependencies using Syft...')

            if scan := _execute_scan(src, scanners[0]):
                yield scan


def _execute_scan(src: t.Union[Path, str], scanner: Scanner) -> t.Optional[DependencyScan]:
    try:
        return scanner.scan(src)
    except Exception as err:
        msg.fail(f'An error occured while scanning {scanner.name()} dependencies...')

        if len(err.args) > 1:
            msg.fail(err.args[1])
        else:
            msg.fail(err)

        return None


def process_scan(scan: DependencyScan) -> DependencyScan:
    for dep in scan.iterdeps():
        dep.meta['purl'] = dep.purl.to_string()

    return scan
