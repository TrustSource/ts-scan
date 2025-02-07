import itertools
import typing as t
import importlib.resources
import concurrent.futures as futures

import ts_deepscan.cli
import ts_deepscan.analyser.textutils

from ts_deepscan.analyser.ScanossAnalyser import ScanossAnalyser

from tqdm import tqdm
from pathlib import Path

from ..pm import DependencyScan
from ..cli import parse_cmd_opts_from_args

__ds_dataset = None

__gitignore_patterns = {
    "pypi": ["Python.gitignore"]
}

__tqdm_bar_format = '{desc:<40}{percentage:3.0f}%|{bar:10}{r_bar}'


def _analyse_with_ds(dep, dataset, **ds_opts) -> tuple:
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


def _analyse_with_ds_completed(scan, dep, pbar):
    def complete(task):
        ds_res, lic_file_res = task.result()

        if ds_res:
            scan.deepscans[dep.key] = ds_res

        if lic_file_res:
            dep.meta['license_file'] = lic_file_res

        with tqdm.get_lock():
            pbar.update()

    return complete


def analyse_with_ds(scan: DependencyScan, ds_args: t.List[str]) -> DependencyScan:
    if scan.deepscans:
        return scan

    ds_args = list(itertools.chain.from_iterable(xd.split(',') for xd in ds_args))
    ds_opts = parse_cmd_opts_from_args(ts_deepscan.cli.scan, ds_args)  # noqa

    global __ds_dataset

    if not __ds_dataset:
        __ds_dataset = ts_deepscan.create_dataset()

    tasks = []
    pool = futures.ThreadPoolExecutor(max_workers=2)

    deps = [dep for dep in scan.iterdeps() if dep.package_files or dep.license_file]
    pbar = tqdm(desc="Analysing dependencies", total=len(deps), bar_format=__tqdm_bar_format)

    for dep in deps:
        task = pool.submit(_analyse_with_ds, dep, __ds_dataset, **ds_opts)
        task.add_done_callback(_analyse_with_ds_completed(scan, dep, pbar))
        tasks.append(task)

    futures.wait(tasks, return_when=futures.ALL_COMPLETED)

    pbar.close()
    return scan


def analyse_with_scanoss(scan: DependencyScan) -> DependencyScan:
    for key, ds in tqdm(scan.deepscans.items(), desc="Analysing results using SCANOSS", bar_format=__tqdm_bar_format):
        wfps = []
        for path, res in ds.result.items():
            if (scanoss := res.get('scanoss')) and (wfp := scanoss.get('wfp')):
                wfps.append(wfp)

        if wfps and (wfps_results := ScanossAnalyser.scan(wfps)):
            for p, res in wfps_results.items():
                ds.result[p]['scanoss']['wfp_result'] = res

    return scan
