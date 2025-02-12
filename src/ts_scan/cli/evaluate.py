import click
import json
import typing as t

from tqdm import tqdm
from pathlib import Path
from concurrent import futures

from . import cli, load_scans_from_file
from .. import DependencyScan

from ..api import TrustSourceAPI


@cli.command('eval', help="Evaluates the scan result, may exit with non zero upon demand")
@cli.inout_default_options(_in=True, _out=True, _fmt=True)
@cli.api_default_options(project_name=False)
@click.option('--vulns-confidence', type=click.Choice(choices=['high', 'medium', 'low']), default='medium',
              help="Confidence level for matching CVEs to packages")
@click.option('--exit-with-failure-on-vulns', default=False, is_flag=True,
              help="Exit with a nonzero exit code (1) if vulnerabilities were found")
def eval_scan(path: Path,
              output_path: t.Optional[Path],
              scan_format: str,
              base_url: str,
              api_key: str,
              vulns_confidence: str,
              exit_with_failure_on_vulns: bool):

    if vulns_confidence == 'high':
        vulns_confidence = 1
    elif vulns_confidence == 'medium':
        vulns_confidence = 2
    else:
        vulns_confidence = 3

    ts_api = TrustSourceAPI(base_url, api_key)

    scans = load_scans_from_file(path, scan_format)
    vulns = {}

    for scan in scans:
        vulns.update(eval_vulns(scan, vulns_confidence, ts_api))

    if output_path:
        with output_path.resolve().open('w') as fp:
            json.dump(vulns, fp, indent=2) # noqa
    else:
        print(json.dumps(vulns, indent=2))

    if vulns and exit_with_failure_on_vulns:
        exit(1)


def eval_vulns(scan: DependencyScan, confidence: int, api: TrustSourceAPI) -> t.Dict[str, dict]:
    vulns = {}
    purls = [dep.purl.to_string() for dep in scan.iterdeps_once()]
    pbar = tqdm(desc="Checking vulnerabilities", total=len(purls))

    def check_completed(_task):
        result = _task.result()
        for res in result:
            comp_vulns = []
            for res_cves in res.get('cves', []):
                if (cves := res_cves['cves']) and cves and (res_cves.get('confidence', 0) < confidence):
                    comp_vulns.append(res_cves)

            if comp_vulns:
                vulns[res['key']] = comp_vulns

        pbar.update(len(result))

    tasks = []
    pool = futures.ThreadPoolExecutor()
    chunk_size = min(len(purls) // pool._max_workers, 40)

    for i in range(0, len(purls), chunk_size):
        task = pool.submit(lambda _purls: check_vulns(_purls, api), purls[i:i + chunk_size])
        task.add_done_callback(check_completed)
        tasks.append(task)

    futures.wait(tasks, return_when=futures.ALL_COMPLETED)
    return vulns

