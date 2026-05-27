import click
import time
import typing as t
import ts_deepscan
from urllib.parse import urlsplit, urlunsplit

from tqdm import tqdm
from pathlib import Path

from . import cli, msg, load_scans_from_file
from ..pm import DependencyScan, dump_scans
from ..api import TrustSourceAPI


@cli.command('upload', help='Transfers scan and analyse results to TrustSource API')
@cli.inout_default_options(_in=True, _out=False, _fmt=True)
@cli.api_default_options()
@click.option('--wait-for-analysis', default=False, is_flag=True,
              help='Wait for analysis completion. Policy exit flags apply in this mode')
@click.option('--wait-timeout', default=60, type=int, metavar='INT', show_default=True,
              help='Max seconds to wait for analysis results when --wait-for-analysis is used')
@click.option('--exit-on-legal/--no-exit-on-legal', default=False,
              help='With --wait-for-analysis, exit with code (1) in case of legal issues (default: disabled)')
@click.option('--exit-on-vulns/--no-exit-on-vulns', default=False,
              help='With --wait-for-analysis, exit with code (1) in case of vulnerabilities (default: disabled)')
@click.option('--Werror', default=False, is_flag=True,
              help='With --wait-for-analysis, treat warnings as violations')
def upload_scan(path: Path,
                scan_format: str,
                project_name: str,
                base_url: str,
                api_key: str,
                wait_for_analysis: bool,
                wait_timeout: int,
                exit_on_legal: bool,
                exit_on_vulns: bool,
                werror: bool):

    api = TrustSourceAPI(base_url, api_key)
    ds_base_url = f'{base_url}/v2/repository'

    scans = load_scans_from_file(path, scan_format)

    # Store upload results
    def store_scans():
        with path.open('w') as fp:
            dump_scans(scans, fp, scan_format)

    for scan in scans:
        _upload_deepscans(scan, ds_base_url, api_key, store_scans)
        upload_result = _upload_scan(scan, project_name, api)

        if wait_for_analysis and upload_result:
            _wait_for_analysis_and_evaluate(upload_result, api, base_url,
                                            exit_on_legal, exit_on_vulns, werror,
                                            wait_timeout)


def _upload_deepscans(scan: DependencyScan, ds_base_url: str, api_key: str, store_scans):
    uploaded = {}
    deepscans = {k: ds for k, ds in scan.deepscans.items() if ds.stats['total'] > 0}

    if not deepscans:
        return

    # Upload Deepscan (if not already uploaded)
    for k, ds in tqdm(deepscans.items(), desc='Uploading deepscans'):
        if ds.uid or ts_deepscan.upload_scan(ds, module_name=k, api_key=api_key, base_url=ds_base_url):
            uploaded[k] = ds
            store_scans()

    # Assigne upload results (uid and url) to dependencies
    for dep in scan.iterdeps_once():
        if ds := uploaded.get(dep.key):
            ver = dep.version

            if not ver:
                ver = 'unknown'

            dep.meta['versions'] = [{
                'version': ver,
                'deepScanId': ds.uid,
                'deepScanUrl': ds.url
            }]

    store_scans()


def _upload_scan(scan: DependencyScan, project_name: str, api: TrustSourceAPI):
    msg.info('Uploading dependencies scan...')

    try:
        # noinspection PyUnresolvedReferences
        data = scan.to_dict().copy()

        # Remove local data
        data.pop('deepscans', None)
        data.pop('source', None)

        # Add required data
        data['project'] = project_name

        resp = api.upload_scan(data)
        msg.good('Uploaded dependencies scan')
        return resp

        # print(json.dumps(resp, indent=2))

    except TrustSourceAPI.Error as err:
        msg.fail('Transfer failed')
        msg.fail(text=err)
        return None


def _wait_for_analysis_and_evaluate(upload_result: dict,
                                    api: TrustSourceAPI,
                                    base_url: str,
                                    exit_on_legal: bool,
                                    exit_on_vulns: bool,
                                    werror: bool,
                                    wait_timeout: int):
    scan_id = upload_result.get('_id') or upload_result.get('scanId') or upload_result.get('id')
    if not scan_id:
        msg.fail('Unable to wait for analysis: upload response does not contain a scan id')
        exit(2)

    msg.info(f'Waiting for analysis results (scan_id={scan_id})...')
    analysis_result = _poll_analysis_result(api, scan_id, timeout=wait_timeout)
    link = _build_analysis_link(base_url, analysis_result)
    link_msg = link or 'result link unavailable'

    fail_reasons = _eval_analysis_result(analysis_result, exit_on_legal, exit_on_vulns, werror)
    if fail_reasons:
        if werror:
            fail_reasons.append('warnings are treated as violations (--Werror)')
        msg.info(
            f'Analysis completed and results are available: {link_msg}. '
            f'Returning non-zero exit code due to enabled policy checks: {"; ".join(fail_reasons)}'
        )
        exit(1)

    msg.good(f'Analysis completed successfully. Results are available: {link_msg}.')


def _poll_analysis_result(api: TrustSourceAPI, scan_id: str, interval: int = 5, timeout: int = 60) -> dict:
    terminal_fail_statuses = {'failed', 'error', 'cancelled', 'canceled'}
    started_at = time.monotonic()

    while True:
        try:
            result = api.get_analysis_results(scan_id)
        except TrustSourceAPI.Error as err:
            msg.fail('Failed to request analysis results')
            msg.fail(text=err)
            exit(2)

        status = str(result.get('analysisStatus', '')).lower()
        if status == 'finished':
            return result

        if status in terminal_fail_statuses:
            msg.fail(f'Execution failed: analysis did not complete successfully (status={status})')
            exit(1)

        elapsed = time.monotonic() - started_at
        remaining = timeout - elapsed
        if remaining <= 0:
            msg.info(f'Stopped waiting after {timeout}s because analysis is not finished yet.')
            exit(2)

        shown_status = status or 'unknown'
        sleep_for = min(interval, remaining)
        msg.info(f'Analysis is {shown_status}. Polling again in {int(sleep_for)}s...')
        time.sleep(sleep_for)


def _build_analysis_link(base_url: str, analysis_result: dict) -> t.Optional[str]:
    analysis_id = analysis_result.get('_id')
    project_id = analysis_result.get('projectId')
    module_id = analysis_result.get('moduleId')

    if not analysis_id or not project_id or not module_id:
        return None

    app_base_url = _app_base_url(base_url)
    return f'{app_base_url}/projects/{project_id}/modules/{module_id}/dependencies?analysis={analysis_id}'


def _app_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    netloc = parsed.netloc

    if netloc.startswith('api.'):
        netloc = f'app.{netloc[4:]}'
    elif netloc == 'api':
        netloc = 'app'

    if not parsed.scheme or not netloc:
        return base_url.rstrip('/').replace('://api.', '://app.', 1)

    return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip('/'), '', ''))


def _eval_analysis_result(analysis_result: dict,
                          exit_on_legal: bool,
                          exit_on_vulns: bool,
                          werror: bool) -> t.List[str]:
    stats = analysis_result.get('statistics') or {}
    counts = _extract_policy_counts(stats)

    fail_reasons = []

    if exit_on_legal:
        legal_violations = counts['legal_violations']
        legal_warnings = counts['legal_warnings']

        if legal_violations > 0 or (werror and legal_warnings > 0):
            fail_reasons.append(
                f'legal policy failed (violations={legal_violations}, warnings={legal_warnings})'
            )

    if exit_on_vulns:
        vuln_violations = counts['vuln_violations']
        vuln_warnings = counts['vuln_warnings']

        if vuln_violations > 0 or (werror and vuln_warnings > 0):
            fail_reasons.append(
                f'vulnerability policy failed (violations={vuln_violations}, warnings={vuln_warnings})'
            )

    return fail_reasons


def _extract_policy_counts(stats: t.Any) -> dict:
    def _to_bucket(value: t.Any) -> dict:
        if not isinstance(value, dict):
            return {}
        return value

    def _to_int(value: t.Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    # Statistics keys are defined by the TrustSource analysis response schema.
    legal = _to_bucket(stats.get('legal'))
    multy_legal = _to_bucket(stats.get('multy-legal'))
    vulnerability = _to_bucket(stats.get('vulnerability'))

    return {
        'legal_violations': _to_int(legal.get('violations')) + _to_int(multy_legal.get('violations')),
        'legal_warnings': _to_int(legal.get('warnings')) + _to_int(multy_legal.get('warnings')),
        'vuln_violations': _to_int(vulnerability.get('violations')),
        'vuln_warnings': _to_int(vulnerability.get('warnings')),
    }
