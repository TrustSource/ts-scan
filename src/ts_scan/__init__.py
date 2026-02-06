import click
import typing as t

from pathlib import Path
from subprocess import CalledProcessError

from .pm import Scanner, Dependency, DependencyScan, License, get_license_from_text
from .cli import cli, msg

def _get_version_from_metadata(default: str = '1.0.0') -> str:
    try:
        from importlib.metadata import version, PackageNotFoundError
    except Exception:
        try:
            from importlib_metadata import version, PackageNotFoundError  # type: ignore
        except Exception:
            return default

    candidates = ['ts-scan', 'ts_scan', __name__]
    for name in candidates:
        try:
            return version(name)
        except PackageNotFoundError:
            continue
        except Exception:
            continue

    return default


__version__ = _get_version_from_metadata()


def __get_pm_scanner_classes() -> t.List[t.Type[Scanner]]:
    from .pm.pypi import PypiScanner
    from .pm.maven import MavenScanner
    from .pm.gradle import GradleScanner
    from .pm.node import NodeScanner
    from .pm.nuget import NugetScanner
    from .pm.cargo import CargoScanner
    from .pm.golang import GolangScanner

    return [
        PypiScanner,
        MavenScanner,
        GradleScanner,
        NodeScanner,
        NugetScanner,
        CargoScanner,
        GolangScanner
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


def create_scanners(scanner_classes: t.Iterable[t.Type[Scanner]], **kwargs) -> t.Iterable[Scanner]:
    scanner_args = {cls.name().lower(): {} for cls in scanner_classes}
    other_args = {}

    for arg, val in kwargs.items():
        scanner_prefix_pos = arg.find('_')
        if scanner_prefix_pos >= 0:
            scanner_prefix = arg[:scanner_prefix_pos]
            scanner_arg = arg[scanner_prefix_pos + 1:]
            if scanner_prefix in scanner_args:
                scanner_args[scanner_prefix][scanner_arg] = val
        else:
            other_args[arg] = val

    return [cls(**other_args, **scanner_args[cls.name().lower()]) for cls in scanner_classes]


def do_scan(paths: t.List[Path], **kwargs) -> t.Iterable[DependencyScan]:
    """
    Excutes actual scan routines
    :param paths: List of paths to be scanned
    :return: An iterable over scan results
    """

    def apply_scanner(s, p) -> t.Tuple[bool, t.Optional[DependencyScan]]:
        if s.accepts(p):
            msg.info(f'Found {s.name()} project. Scanning for dependencies...')
            scan = _execute_scan(p, s)
            if scan:
                scan.source = str(p)
                msg.good(f'{s.name()} scan is done!')
            
            return True, scan
        
        return False, None


    scanners = [s for s in create_scanners(__get_pm_scanner_classes(), **kwargs) if not s.ignore]

    for p in paths:
        p = p.resolve()

        msg.info(f'Running dependency scan for {p}.')
        scanned_at_least_once = False

        for scanner in scanners:
            accepted, scan = apply_scanner(scanner, p)
            
            if accepted:
                scanned_at_least_once = True
            
            if scan:
                yield scan
           

        if scanned_at_least_once:
            msg.good(f'Dependency scan completed.')
        else:
            from .pm.generic import GenericScanner
            
            if generic_scanner := next(iter(create_scanners([GenericScanner], **kwargs)), None) :
                _, scan = apply_scanner(generic_scanner, p)
                if scan:
                    yield scan
            else:
                msg.warn(f'No supported projects found.')


def do_scan_with_syft(sources: t.List[t.Union[Path, str]], **kwargs) -> t.Iterable[DependencyScan]:
    from .pm.syft import SyftScanner

    if scanners := create_scanners([SyftScanner], **kwargs):
        for src in sources:

            msg.info(f'Scanning for dependencies using Syft...')

            if scan := _execute_scan(src, scanners[0]):
                scan.source = str(src)
                yield scan


def _execute_scan(src: t.Union[Path, str], scanner: Scanner) -> t.Optional[DependencyScan]:
    try:
        return scanner.scan(src)

    except CalledProcessError as err:
        if scanner.verbose:
            if stdout := err.stdout:
                print(stdout.decode('utf-8'))                
            if stderr := err.stderr:
                print(stderr.decode('utf-8'))

        msg.fail(f'{scanner.name()} failed with non-zero exit code {err.returncode}.')
        if not scanner.verbose:
            msg.fail(f'Use --verbose to see the error details.')

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

        if not dep.licenses and dep.license_file:
            if res := get_license_from_text(Path(dep.license_file).read_text()):
                dep.meta['license_file'] = res[0]
                dep.licenses = [License(name=lic) for lic in res[1]]

    return scan
