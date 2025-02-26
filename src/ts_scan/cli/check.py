import click
import json
import typing as t

from tqdm import tqdm
from pathlib import Path
from concurrent import futures

from . import cli, load_scans_from_file
from .. import msg, DependencyScan

from ..api import TrustSourceAPI


@cli.command('check', help='Checks the scan result')
@cli.inout_default_options(_in=True, _out=True, _fmt=True)
@cli.api_default_options(is_project_name_required=False, project_name_help_hint="required w/o '--vulns-only'")
@click.option('--vulns-only', default=False, is_flag=True,
              help="Only check component vulnerabilities")
@click.option('--exit-on-legal/--no-exit-on-legal', default=True,
              help="Exit with code (1) in case of legal issues")
@click.option('--exit-on-vulns/--no-exit-on-vulns', default=True,
              help="Exit with code (1) in case of vulnerabilities")
@click.option('--Werror', default=False, is_flag=True,
              help="Treat warnings as violations")
@click.option('--vulns-confidence', type=click.Choice(choices=['high', 'medium', 'low']), default='medium',
              help="Confidence level while checking component vulnerabilities")
def check_scan(path: Path, output_path: t.Optional[Path], scan_format: str,
               project_name: str, base_url: str, api_key: str,
               vulns_only: bool,
               exit_on_legal: bool,
               exit_on_vulns: bool,
               werror: bool,
               vulns_confidence: str):
    ts_api = TrustSourceAPI(base_url, api_key)
    scans = load_scans_from_file(path, scan_format)

    if vulns_only:
        check_vulns(ts_api, scans, vulns_confidence, output_path, exit_on_vulns)
    else:
        if not project_name:
            print("Usage: ts-scan check [OPTIONS] PATH")
            print("Try 'ts-scan check --help' for help.")
            print("\nError: Missing option '--project-name'.")
            exit(2)
        check_comps(ts_api, scans, project_name, exit_on_legal, exit_on_vulns, werror, output_path)


def check_comps(api: TrustSourceAPI,
                scans: t.List[DependencyScan],
                proj_name: str,
                exit_on_legal: bool,
                exit_on_vulns: bool,
                werror: bool,
                output_path: t.Optional[Path]):

    res = {}

    for scan in scans:
        comps = []

        for dep in scan.iterdeps_once():
            for v in dep.versions:
                comps.append({
                    'key': dep.key,
                    'name': dep.name,
                    'version': v
                })

        if not comps:
            continue

        try:
            check = api.check_components(proj_name, scan.module, comps)
        except TrustSourceAPI.Error as err:
            print(f"An error occured while requesting vulnerabilities information for the scan")
            print(err)
            exit(2)

        if not check:
            continue

        res[scan.module] = check
        if output_path:
            with output_path.resolve().open('w') as fp:
                json.dump(res, fp, indent=2)  # noqa

        for w in check.get('warnings', []):
            comp = f'{w.get("component")}:{w.get("version")}'
            status = w.get('status').replace('_', ' ')
            msg.warn(f'{comp}: {status}')

        if exit_on_legal:
            violations = 0
            warnings = 0

            for res in check['data']:
                comp = res['component']
                comp_key = f'{comp["key"]}:{comp["version"]}'

                res = res['not_changed']

                for v in res['violations']:
                    log_msg = f'{comp_key}: {v["message"]}'
                    if v['type'] == 'violation':
                        msg.fail(log_msg)
                        violations += 1
                    elif v['type'] == 'warning':
                        msg.warn(log_msg)
                        warnings += 1

                    msg.divider(char=' ')

            if violations > 0 or (werror and warnings > 0):
                exit(1)

        if exit_on_vulns:
            violations = 0
            warnings = 0
            vulns = {}

            for res in check['data']:
                comp = res['component']
                comp_key = f'{comp["key"]}:{comp["version"]}'

                vulns.setdefault(comp_key, [])

                for v in res['vulnerabilities']:
                    vulns[comp_key].append(v["name"])
                    if v['status'] == 'violations':
                        violations += 1
                    elif v['status'] == 'warning':
                        warnings += 1

            for comp_key, vulns in vulns.items():
                if vulns:
                    msg.fail(f'{comp_key}:{vulns}')

            if violations > 0 or (werror and warnings > 0):
                exit(1)


def check_vulns(api: TrustSourceAPI,
                scans: t.List[DependencyScan],
                vulns_confidence: str,
                output_path: t.Optional[Path],
                exit_on_vulns: bool):

    if vulns_confidence == 'high':
        vulns_confidence = 1
    elif vulns_confidence == 'medium':
        vulns_confidence = 2
    else:
        vulns_confidence = 3

    vulns = {}

    for scan in scans:
        vulns.update(eval_vulns(scan, vulns_confidence, api))

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
