import click
import json
import typing as t

from tqdm import tqdm
from pathlib import Path
from concurrent import futures

from . import cli, load_scans_from_file
from .. import msg, DependencyScan

from ..api import TrustSourceAPI


@cli.command('check', help='Checks the scan result for vulnerabilities')
@cli.inout_default_options(_in=True, _out=True, _fmt=True)
@cli.api_default_options(project_name=False)
@click.option('--exit-on-vulns/--no-exit-on-vulns', default=False,
              help="Exit with code (1) in case of vulnerabilities")
@click.option('--vulns-confidence', type=click.Choice(choices=['high', 'medium', 'low']), default='medium',
              help="Confidence level while checking component vulnerabilities")
def check_scan(path: Path, output_path: t.Optional[Path], scan_format: str,
               base_url: str, api_key: str,
               exit_on_vulns: bool,
               vulns_confidence: str):
    
    ts_api = TrustSourceAPI(base_url, api_key)
    scans = load_scans_from_file(path, scan_format)
    check_vulns(ts_api, scans, vulns_confidence, output_path, exit_on_vulns)


def check_vulns(api: TrustSourceAPI,
                scans: t.List[DependencyScan],
                vulns_confidence: str,
                output_path: t.Optional[Path],
                exit_on_vulns: bool):

    if vulns_confidence == 'high':
        confidence = 1
    elif vulns_confidence == 'medium':
        confidence = 2
    else:
        confidence = 3

    vulns = {}

    for scan in scans:
        vulns.update(eval_vulns(scan, confidence, api))

    if not vulns:
        msg.good('No vulnerabilities identified')
    else:
        if output_path:
            with output_path.resolve().open('w') as fp:
                json.dump(vulns, fp, indent=2)  # noqa
        else:
            print(json.dumps(vulns, indent=2))

        if exit_on_vulns:
            exit(1)


def eval_vulns(scan: DependencyScan, confidence: int, api: TrustSourceAPI) -> t.Dict[str, dict]:
    vulns = {}
    purls = [dep.purl.to_string() for dep in scan.iterdeps_once()]
    pbar = tqdm(desc="Checking vulnerabilities", total=len(purls))

    def _check_completed(_task):
        result = _task.result()
        for res in result:
            comp_vulns = []
            for res_cves in res.get('cves', []):
                if (cves := res_cves['cves']) and cves and (res_cves.get('confidence', 0) < confidence):
                    comp_vulns.append(res_cves)

            if comp_vulns:
                vulns[res['key']] = comp_vulns

        pbar.update(len(result))

    def _check_vulns(_purls: t.List[str], _api: TrustSourceAPI) -> list:
        try:
            return _api.find_cves(_purls)

        except TrustSourceAPI.Error as err:
            print(f"An error occured while requesting vulnerabilities information for the scan")
            print(err)
            return []

    tasks = []
    pool = futures.ThreadPoolExecutor()
    chunk_size = min(len(purls) // pool._max_workers, 20)

    for i in range(0, len(purls), chunk_size):
        task = pool.submit(lambda _purls: _check_vulns(_purls, api), purls[i:i + chunk_size])
        task.add_done_callback(_check_completed)
        tasks.append(task)

    futures.wait(tasks, return_when=futures.ALL_COMPLETED)
    return vulns
