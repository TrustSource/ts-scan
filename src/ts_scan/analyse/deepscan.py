import concurrent.futures as futures
import importlib
import importlib.util
import itertools
import typing as t
import warnings

from pathlib import Path
from threading import Lock
from types import ModuleType

from tqdm import tqdm


try:
    import ts_deepscan as _ts_deepscan
    from ts_deepscan.scanner import Scan as DSScan
except ModuleNotFoundError as err:
    if err.name != 'ts_deepscan':
        raise
    _ts_deepscan = None
    DSScan = t.Any


DEEPSCAN_INSTALL_HINT = 'Install it with: pip install "ts-scan[analyse]"'
_reported_unavailable_operations: set[str] = set()
_ds_dataset = None

_gitignore_patterns = {
    'npm': ['Node.gitignore'],
    'pypi': ['Python.gitignore'],
}


class DeepScanNotInstalledError(RuntimeError):
    pass


def is_deepscan_installed() -> bool:
    return importlib.util.find_spec('ts_deepscan') is not None


def deepscan_feature_help(description: str) -> str:
    if is_deepscan_installed():
        return description
    return f'{description} [Unavailable: ts-deepscan is not installed. {DEEPSCAN_INSTALL_HINT}]'


def report_deepscan_unavailable(
        operation: str,
        reporter: t.Optional[t.Callable[[str], t.Any]] = None) -> None:
    if operation in _reported_unavailable_operations:
        return

    _reported_unavailable_operations.add(operation)
    message = f'Skipped {operation} because ts-deepscan is not installed. {DEEPSCAN_INSTALL_HINT}'
    if reporter is not None:
        reporter(message)
    else:
        warnings.warn(message, RuntimeWarning, stacklevel=2)


def require_deepscan() -> ModuleType:
    global _ts_deepscan

    if _ts_deepscan is not None:
        return _ts_deepscan

    try:
        _ts_deepscan = importlib.import_module('ts_deepscan')
        return _ts_deepscan
    except ModuleNotFoundError as err:
        if err.name != 'ts_deepscan':
            raise
        raise DeepScanNotInstalledError(
            f'ts-deepscan is required for this operation. {DEEPSCAN_INSTALL_HINT}'
        ) from err


def _textutils() -> t.Any:
    require_deepscan()
    return importlib.import_module('ts_deepscan.analyser.textutils')


def upload_scan(scan: t.Any, module_name: str, api_key: str, base_url: str) -> bool:
    return bool(require_deepscan().upload_scan(
        scan,
        module_name=module_name,
        api_key=api_key,
        base_url=base_url,
    ))


def _parse_ds_args(ds_args: t.List[str]) -> t.Tuple[t.List[str], t.Dict[str, t.Any]]:
    from ..cli import parse_cmd_params_from_args

    deepscan_cli = importlib.import_module('ts_deepscan.cli')
    ds_args = list(itertools.chain.from_iterable(arg.split(',') for arg in ds_args))
    ds_opts = parse_cmd_params_from_args(deepscan_cli.scan, ds_args, only_opts=True)
    return ds_args, ds_opts


def get_ds_dataset() -> t.Any:
    global _ds_dataset

    if _ds_dataset is None:
        _ds_dataset = require_deepscan().create_dataset()
    return _ds_dataset


def get_license_from_text(
        text: str,
        as_lic_text_only: bool = True,
        reporter: t.Optional[t.Callable[[str], t.Any]] = None,
) -> t.Optional[t.Tuple[dict, t.List[str]]]:
    try:
        textutils = _textutils()
    except DeepScanNotInstalledError:
        report_deepscan_unavailable('license text analysis', reporter)
        return None

    dataset = get_ds_dataset()
    if res := textutils.analyse_license_text(text, dataset=dataset, search_copyright=False):
        if (key := res.get('key')) and (score := res.get('score', 0)) and score >= 0.9:
            return res, [key]

    if not as_lic_text_only and (
            res := textutils.analyse_text(
                text,
                timeout=10,
                dataset=dataset,
                search_copyright=False,
            )):
        if 'licenses' in res:
            return res, res['licenses']

    return None


def _analyse_dep_with_ds(dep: t.Any, dataset: t.Any, **ds_opts: t.Any) -> tuple:
    gitignores = [Path(__file__).parent.joinpath('gitignore').joinpath(pattern)
                  for pattern in _gitignore_patterns.get(dep.type, [])]
    deepscan = require_deepscan()
    scanner = deepscan.create_scanner(
        **ds_opts,
        default_gitignores=gitignores,
        dataset=dataset,
    )

    ds_res = None
    lic_file_res = None

    if dep.package_files:
        sources = [Path(src) for src in dep.package_files]
        ds_res = deepscan.execute_scan(sources, scanner, title=dep.key)

    if 'license_file' not in dep.meta and (lic_file := dep.license_file):
        lic_file_path = Path(lic_file)
        if lic_file_path.exists():
            with lic_file_path.open(errors='surrogateescape') as fp:
                lic_file_res = _textutils().analyse_license_text(fp.read(), dataset)

    return ds_res, lic_file_res


def _analyse_dep_with_ds_completed(dep: t.Any, scan: t.Any, pbar: t.Any, completion_lock: Lock):
    def complete(task: t.Any):
        ds_res, lic_file_res = task.result()

        with completion_lock:
            if ds_res:
                scan.deepscans[dep.key] = ds_res
                extend_dep_from_ds(dep, ds_res)

            if lic_file_res:
                dep.meta['license_file'] = lic_file_res

        with tqdm.get_lock():
            pbar.update()

    return complete


def analyse_scan_with_ds(scan: t.Any, ds_args: t.List[str]) -> None:
    if scan.deepscans:
        return

    _, ds_opts = _parse_ds_args(ds_args)
    dataset = get_ds_dataset()
    tasks = []
    pool = futures.ThreadPoolExecutor(max_workers=2)
    completion_lock = Lock()
    deps = [dep for dep in scan.iterdeps() if dep.package_files or dep.license_file]
    pbar = tqdm(desc='Analysing dependencies', total=len(deps))

    for dep in deps:
        task = pool.submit(_analyse_dep_with_ds, dep, dataset, **ds_opts)
        task.add_done_callback(_analyse_dep_with_ds_completed(dep, scan, pbar, completion_lock))
        tasks.append(task)

    futures.wait(tasks, return_when=futures.ALL_COMPLETED)
    pbar.close()


def analyse_path_with_ds(path: Path, ds_args: t.List[str]) -> t.Any:
    _, ds_opts = _parse_ds_args(ds_args)
    dataset = get_ds_dataset()
    deepscan = require_deepscan()
    scanner = deepscan.create_scanner(**ds_opts, dataset=dataset)
    return deepscan.execute_scan([path], scanner, title=f"'{path.name}'")


def extend_dep_from_ds(dep: t.Any, ds: t.Any) -> None:
    from ..pm import License, LicenseKind

    summary = t.cast(t.Mapping[str, t.Any], ds.summary)
    for ds_lic in summary.get('licenses', []):
        if next((lic for lic in dep.licenses
                 if lic.kind == LicenseKind.EFFECTIVE and lic.name == ds_lic), None) is None:
            dep.licenses.append(License(name=ds_lic, kind=LicenseKind.EFFECTIVE))

    for name, coding in summary.get('crypto_algorithms', {}).items():
        dep.add_crypto_algorithm(algorithm=name, strength=coding)
