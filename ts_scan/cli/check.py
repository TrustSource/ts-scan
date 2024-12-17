import json
import click
import requests

from pathlib import Path

from . import cli
from .. import msg
from ..pm import DependencyScan


@cli.command('check')
@cli.inout_default_options(_in=True, _out=False, _fmt=True)
@cli.api_default_options
@click.option('--breakOnLegalIssues', default=True, is_flag=True,
              help="Exit with code 2 in case of legal issues")
@click.option('--breakOnVulnerabilities', default=True, is_flag=True,
              help="Exit with code 2 in case of vulnerabilities")
@click.option('--breakOnViolationsOnly', default=False, is_flag=True,
              help="Exit with code 2 if only violations were found")
@click.option('--breakOnViolationsAndWarnings', default=False, is_flag=True,
              help="Exit with code 2 if violations or warnings were found")
@click.option('--assumeComponentsModified', default=False, is_flag=True,
              help="Assume that components are modified by checking legal settings")
def check_scan(project_name: str, base_url: str, api_key: str,
               path: Path,
               scan_format: str,
               breakOnLegalIssues=True,
               breakOnVulnerabilities=True,
               breakOnViolationsOnly=False,
               breakOnViolationsAndWarnings=False,
               assumeComponentsModified=False,
               **kwargs):
    with path.open('r') as fp:
        data = json.load(fp)
        if type(data) is list:
            scans = [DependencyScan.from_dict(d) for d in data]
        else:
            scans = [DependencyScan.from_dict(data)]

    for scan in scans:
        comps = []

        for dep in scan.iterdeps():
            for v in dep.versions:
                comps.append({
                    'key': dep.key,
                    'name': dep.name,
                    'version': v
                })

        if not comps:
            continue

        check = {
            'projectName': project_name,
            'moduleName': scan.module,
            'components': comps
        }

        headers = {
            'Content-Type': 'application/json',
            'user-agent': 'ts-scan/1.0.0',
            'x-api-key': api_key
        }

        response = requests.post(base_url + 'compliance/check/component', json=check, headers=headers)

        if response.status_code == 200:
            results = response.json()
            for w in results.get('warnings', []):
                comp = f'{w.get("component")}:{w.get("version")}'
                status = w.get('status').replace('_', ' ')
                msg.warn(f'{comp}: {status}')

            if not breakOnLegalIssues and not breakOnVulnerabilities:
                return

            if breakOnLegalIssues:
                violations = 0
                warnings = 0

                for res in results['data']:
                    comp = res['component']
                    comp_key = f'{comp["key"]}:{comp["version"]}'

                    res = res['changed'] if assumeComponentsModified else res['not_changed']
                    for v in res['violations']:
                        log_msg = f'{comp_key}: {v["message"]}'
                        if v['type'] == 'violation':
                            msg.fail(log_msg)
                            violations += 1
                        elif v['type'] == 'warning':
                            msg.warn(log_msg)
                            warnings += 1

                        msg.divider(char=' ')

                if breakOnViolationsAndWarnings and (violations > 0 or warnings > 0):
                    exit(2)

                if breakOnViolationsOnly and violations > 0:
                    exit(2)

            if breakOnVulnerabilities:
                violations = 0
                warnings = 0
                vulns = {}

                for res in results['data']:
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

                if breakOnViolationsAndWarnings and (violations > 0 or warnings > 0):
                    exit(2)

                if breakOnViolationsOnly and violations > 0:
                    exit(2)

        elif 400 <= response.status_code < 500:
            data = response.json()
            if err := data.get('error'):
                msg.fail(err)
            exit(1)
        else:
            msg.fail(f'Check failed with status code: {response.status_code}')
            exit(1)
