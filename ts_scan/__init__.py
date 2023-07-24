import itertools
import sys

import ts_deepscan
import docker

from pathlib import Path
from typing import Iterable, List

from ts_python_client.commands import parse_cmd_opts_from_args
from docker.errors import ImageNotFound

from .pm import DependencyScan


def do_scan(paths: List[Path]) -> Iterable[DependencyScan]:
    """
    Imports and excutes actual scan routines
    :param paths: List of paths to be scanned
    :return: An iterable over scan results
    """
    from .pm.pypi import scan as pypi_scan
    from .pm.maven import scan as maven_scan

    for p in paths:
        if scan := pypi_scan(p):
            yield scan

        if scan := maven_scan(p):
            yield scan


__ds_scanner = None
__ds_dataset = None

def process_scan(scan: DependencyScan, 
    enable_deepscan: bool, ds_args: list,
    enable_ort: bool, ort_i: Path, ort_o: Path,  ort_args: list
) -> DependencyScan:
    
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

    
    if enable_ort:
        if not ort_i or not ort_o:
            raise ValueError("If ORT is enabled, '--ort-i' and '--ort-o' are required.")
        
        d_client = docker.from_env()
        
        # check if ort image exists
        try:
            d_client.images.get("ghcr.io/trustsource/ort")

        except ImageNotFound:
            answer = input("Could not find ORT docker image, would you like to download it now? [Y/n]")

            if answer.strip().lower() in {"", "yes", "ye", "y", "absolutely my guy"}:
                d_client.images.pull("ghcr.io/trustsource/ort:latest")

            else:
                sys.exit()

        
        ort_i = ort_i.resolve()
        ort_o = ort_o.resolve()

        if ort_i == ort_o:
            volumes = {
                ort_i: {"bind": "/ort", "mode": "rw"}
            }

            ort_cmd = f"analyze -i /ort -o /ort {' '.join(ort_args)}"

        else:
            volumes = {
                ort_i.resolve(): {"bind": "/ort-in", "mode": "rw"},
                ort_o.resolve(): {"bind": "/ort-out", "mode": "rw"}
            }

            ort_cmd = f"analyze -i /ort-in -o /ort-out {' '.join(ort_args)}"

        print("Running ORT with these options:")
        print(ort_cmd)

        container = d_client.containers.run(
            "ghcr.io/trustsource/ort:latest",
            ort_cmd,
            detach=True,
            volumes=volumes
        )

        for line in container.logs(stream=True):
            print(line.decode("utf-8"), end="")

        container.stop()
        container.remove()


    for dep in scan.iterdeps():
        if (sources := dep.files) and __ds_scanner:
            sources = [Path(src) for src in sources]
            ds_res = ts_deepscan.execute_scan(sources, __ds_scanner, title=dep.key)
            scan.deepscans[dep.key] = ds_res

        if (lic_file := dep.license_file) and lic_file.exists() and __ds_dataset:
            with lic_file.open(errors="surrogateescape") as fp:
                if lic_file_res := ts_deepscan.analyser.textutils.analyse_license_text(fp.read(), __ds_dataset):
                    dep.meta['license_file'] = lic_file_res

    return scan