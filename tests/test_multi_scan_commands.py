import io
import json
import typing as t
from pathlib import Path
from types import SimpleNamespace

from ts_scan.cli import analyse as analyse_cli
from ts_scan.cli import check as check_cli
from ts_scan.cli import convert as convert_cli
from ts_scan.cli import upload as upload_cli
from ts_scan.pm import Dependency, DependencyScan, dump_scans, load_scans


def _invoke(command: t.Any, **kwargs: t.Any) -> t.Any:
    callback = t.cast(t.Callable[..., t.Any], command.callback)
    return callback(**kwargs)


def _scans() -> list[DependencyScan]:
    return [
        DependencyScan(
            module='backend',
            moduleId='maven:backend',
            dependencies=[Dependency(name='requests', type='pypi', versions=['2.32.3'])],
        ),
        DependencyScan(
            module='frontend',
            moduleId='npm:frontend',
            dependencies=[Dependency(name='react', type='npm', versions=['19.1.1'])],
        ),
    ]


def _write_scans(path: Path) -> None:
    path.write_text(json.dumps([scan.to_dict() for scan in _scans()]))


def test_upload_sends_each_scan_as_a_separate_request_in_file_order(tmp_path, monkeypatch):
    scan_path = tmp_path / 'scans.json'
    _write_scans(scan_path)
    uploaded = []

    class FakeAPI:
        def __init__(self, base_url, api_key):
            assert base_url == 'https://api.example.test'
            assert api_key == 'secret'

        def upload_scan(self, data):
            uploaded.append(data)
            return {'id': data['moduleId']}

    monkeypatch.setattr(upload_cli, 'TrustSourceAPI', FakeAPI)

    _invoke(
        upload_cli.upload_scan,
        path=scan_path,
        scan_format='ts',
        project_name='example',
        base_url='https://api.example.test',
        api_key='secret',
        wait_for_analysis=False,
        wait_timeout=60,
        exit_on_legal=False,
        exit_on_vulns=False,
        werror=False,
    )

    assert [payload['moduleId'] for payload in uploaded] == [
        'maven:backend',
        'npm:frontend',
    ]
    assert all(payload['project'] == 'example' for payload in uploaded)


def test_analyse_processes_and_outputs_every_scan(tmp_path, monkeypatch):
    scan_path = tmp_path / 'scans.json'
    _write_scans(scan_path)
    analysed = []
    output = []

    monkeypatch.setattr(analyse_cli, 'require_deepscan', lambda: None)
    monkeypatch.setattr(
        analyse_cli,
        'analyse_scan_with_ds',
        lambda scan, ds_args: analysed.append(scan.moduleId),
    )
    monkeypatch.setattr(
        analyse_cli,
        'output_scans',
        lambda scans, path: output.extend(scans),
    )

    _invoke(
        analyse_cli.analyse_scan,
        path=scan_path,
        output_path=None,
        scan_format='ts',
        disable_deepscan=False,
        disable_scanoss=True,
        scanoss_api_key=None,
        xdeepscan=(),
    )

    assert analysed == ['maven:backend', 'npm:frontend']
    assert [scan.moduleId for scan in output] == analysed


def test_check_queries_components_from_every_scan(tmp_path, monkeypatch):
    scan_path = tmp_path / 'scans.json'
    _write_scans(scan_path)
    requested_purls = []

    class FakeAPI:
        def __init__(self, base_url, api_key):
            assert base_url == 'https://api.example.test'
            assert api_key == 'secret'

        def find_cves(self, purls):
            requested_purls.extend(purls)
            return []

    monkeypatch.setattr(check_cli, 'TrustSourceAPI', FakeAPI)

    _invoke(
        check_cli.check_scan,
        path=scan_path,
        output_path=None,
        scan_format='ts',
        base_url='https://api.example.test',
        api_key='secret',
        exit_on_vulns=False,
        vulns_confidence='medium',
    )

    assert requested_purls == [
        'pkg:pypi/requests@2.32.3',
        'pkg:npm/react@19.1.1',
    ]


def test_check_accepts_empty_scans():
    api = SimpleNamespace(find_cves=lambda purls: (_ for _ in ()).throw(AssertionError()))

    assert check_cli.eval_vulns(
        DependencyScan(module='empty', moduleId='empty'), 2, t.cast(t.Any, api)
    ) == {}


def test_convert_preserves_all_scans_in_ts_output(tmp_path):
    scan_path = tmp_path / 'scans.json'
    output_path = tmp_path / 'converted.json'
    _write_scans(scan_path)

    _invoke(
        convert_cli.convert,
        path=scan_path,
        output_path=output_path,
        scan_format='ts',
        output_format='ts',
    )

    assert [scan.moduleId for scan in load_scans(output_path, 'ts')] == [
        'maven:backend',
        'npm:frontend',
    ]


def test_single_document_formats_reject_multiple_scans_instead_of_dropping_them():
    for scan_format in ('spdx-json', 'cyclonedx-json'):
        try:
            dump_scans(_scans(), io.StringIO(), scan_format)
        except ValueError as error:
            assert 'supports one scan per document' in str(error)
        else:
            raise AssertionError(f'{scan_format} silently accepted multiple scans')
