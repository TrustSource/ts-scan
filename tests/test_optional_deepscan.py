import importlib
import typing as t
from types import SimpleNamespace

import click
from click.testing import CliRunner

from ts_scan.cli import analyse as analyse_cli
from ts_scan.cli.upload import _upload_deepscans
from ts_scan.analyse.deepscan import (DEEPSCAN_INSTALL_HINT, DeepScanNotInstalledError,
                                      deepscan_feature_help, require_deepscan)
from ts_scan.pm import DependencyScan, get_license_from_text

upload_cli = importlib.import_module('ts_scan.cli.upload')
deepscan_module = importlib.import_module('ts_scan.analyse.deepscan')


def test_analyse_help_marks_command_unavailable_when_deepscan_is_missing(monkeypatch):
    monkeypatch.setattr('ts_scan.analyse.deepscan.is_deepscan_installed', lambda: False)

    help_text = deepscan_feature_help('Analyze scanned dependencies')

    assert 'Unavailable: ts-deepscan is not installed' in help_text
    assert DEEPSCAN_INSTALL_HINT in help_text


def test_require_deepscan_provides_install_hint(monkeypatch):
    missing = ModuleNotFoundError("No module named 'ts_deepscan'", name='ts_deepscan')
    monkeypatch.setattr(deepscan_module, '_ts_deepscan', None)
    monkeypatch.setattr(
        'ts_scan.analyse.deepscan.importlib.import_module',
        lambda _: (_ for _ in ()).throw(missing),
    )

    try:
        require_deepscan()
    except DeepScanNotInstalledError as err:
        assert DEEPSCAN_INSTALL_HINT in str(err)
    else:
        raise AssertionError('Expected DeepScanNotInstalledError')


def test_analyse_command_remains_available_but_fails_with_hint(monkeypatch, tmp_path):
    def unavailable():
        raise DeepScanNotInstalledError(f'ts-deepscan is required. {DEEPSCAN_INSTALL_HINT}')

    monkeypatch.setattr(analyse_cli, 'require_deepscan', unavailable)

    result = CliRunner().invoke(analyse_cli.analyse_scan, [str(tmp_path)])

    assert result.exit_code == 1
    assert 'ts-deepscan is required' in result.output
    assert DEEPSCAN_INSTALL_HINT in result.output


def test_license_analysis_warns_once_when_deepscan_is_missing(monkeypatch):
    messages = []

    def unavailable():
        raise DeepScanNotInstalledError('ts-deepscan is required')

    monkeypatch.setattr(deepscan_module, 'require_deepscan', unavailable)
    monkeypatch.setattr(deepscan_module, '_reported_unavailable_operations', set())
    monkeypatch.setattr(importlib.import_module('ts_scan.cli').msg, 'warn', messages.append)

    assert get_license_from_text('license text') is None
    assert get_license_from_text('more license text') is None
    assert len(messages) == 1
    assert 'Skipped license text analysis' in messages[0]
    assert DEEPSCAN_INSTALL_HINT in messages[0]


def test_upload_without_deepscan_data_does_not_require_package(monkeypatch):
    monkeypatch.setattr(
        upload_cli,
        'require_deepscan',
        lambda: (_ for _ in ()).throw(AssertionError('should not be called')),
    )
    scan = DependencyScan(module='example', moduleId='example')

    _upload_deepscans(scan, 'https://example.test', 'key', lambda: None)


def test_upload_with_deepscan_data_reports_missing_package(monkeypatch):
    def unavailable():
        raise DeepScanNotInstalledError(f'ts-deepscan is required. {DEEPSCAN_INSTALL_HINT}')

    monkeypatch.setattr(upload_cli, 'require_deepscan', unavailable)
    scan = DependencyScan(module='example', moduleId='example')
    scan.deepscans['example'] = t.cast(t.Any, SimpleNamespace(stats={'total': 1}))

    try:
        _upload_deepscans(scan, 'https://example.test', 'key', lambda: None)
    except click.ClickException as err:
        assert DEEPSCAN_INSTALL_HINT in str(err)
    else:
        raise AssertionError('Expected ClickException')
