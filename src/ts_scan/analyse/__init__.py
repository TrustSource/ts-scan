import itertools
import typing as t
import importlib.resources
import concurrent.futures as futures

import ts_deepscan.cli
import ts_deepscan.analyser.textutils

from ts_deepscan import Scan as DSScan

from tqdm import tqdm
from pathlib import Path
from threading import Lock

from ..pm import DependencyScan, Dependency
from ..cli import parse_cmd_params_from_args

__ds_dataset = None

__gitignore_patterns = {
    "npm": ["Node.gitignore"],
    "pypi": ["Python.gitignore"]
}


def _parse_ds_args(ds_args: t.List[str]) -> t.Tuple[t.List[str], t.Dict[str, t.Any]]:
    ds_args = list(itertools.chain.from_iterable(xd.split(',') for xd in ds_args))
    ds_opts = parse_cmd_params_from_args(ts_deepscan.cli.scan, ds_args, only_opts=True)  # noqa

    return ds_args, ds_opts


def _get_ds_dataset():
    global __ds_dataset

    if not __ds_dataset:
        __ds_dataset = ts_deepscan.create_dataset()

    return __ds_dataset


def _analyse_dep_with_ds(dep, dataset, **ds_opts) -> tuple:
    gitignores = [importlib.resources.path(f'{__package__}.gitignore', pat)
                  for pat in __gitignore_patterns.get(dep.type, [])]

    scanner = ts_deepscan.create_scanner(**ds_opts, default_gitignores=gitignores, dataset=dataset)  # noqa

    ds_res = None
    lic_file_res = None

    if dep.package_files:
        sources = [Path(src) for src in dep.package_files]
        ds_res = ts_deepscan.execute_scan(sources, scanner, title=dep.key)

    if (lic_file := dep.license_file) and __ds_dataset:
        lic_file_path = Path(lic_file)
        if lic_file_path.exists():
            with lic_file_path.open(errors="surrogateescape") as fp:
                lic_file_res = ts_deepscan.analyser.textutils.analyse_license_text(fp.read(), __ds_dataset)  # noqa

    return ds_res, lic_file_res


def _analyse_dep_with_ds_completed(dep, scan, pbar, completion_lock):
    def complete(task):
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


def analyse_scan_with_ds(scan: DependencyScan, ds_args: t.List[str]):
    if scan.deepscans:
        return scan

    ds_args, ds_opts = _parse_ds_args(ds_args)
    dataset = _get_ds_dataset()

    tasks = []
    pool = futures.ThreadPoolExecutor(max_workers=2)
    completion_lock = Lock()

    deps = [dep for dep in scan.iterdeps() if dep.package_files or dep.license_file]
    pbar = tqdm(desc="Analysing dependencies", total=len(deps))

    for dep in deps:
        task = pool.submit(_analyse_dep_with_ds, dep, dataset, **ds_opts)
        task.add_done_callback(_analyse_dep_with_ds_completed(dep, scan, pbar, completion_lock))
        tasks.append(task)

    futures.wait(tasks, return_when=futures.ALL_COMPLETED)

    pbar.close()


def analyse_path_with_ds(path: Path, ds_args: t.List[str]) -> DSScan:
    ds_args, ds_opts = _parse_ds_args(ds_args)
    dataset = _get_ds_dataset()

    scanner = ts_deepscan.create_scanner(**ds_opts, dataset=dataset)  # noqa

    return ts_deepscan.execute_scan([path], scanner, title=f"'{path.name}'")


def extend_dep_from_ds(dep: Dependency, ds: DSScan):
    from ..pm import License, LicenseKind

    for ds_lic in ds.summary.get('licenses', []):
        if next((lic for lic in dep.licenses
                 if lic.kind == LicenseKind.EFFECTIVE and lic.name == ds_lic), None) is None:
            dep.licenses.append(License(name=ds_lic, kind=LicenseKind.EFFECTIVE))

    for name, coding in ds.summary.get('crypto_algorithms', {}).items():
        dep.add_crypto_algorithm(algorithm=name, strength=coding)
