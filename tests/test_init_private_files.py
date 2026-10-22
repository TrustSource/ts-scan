import os
import stat
import sys

import pytest
import toml
from click.testing import CliRunner

from ts_scan.cli import cli, start  # noqa: F401  (start() registers the sub-commands)
import ts_scan.cli.init  # noqa: F401

posix_only = pytest.mark.skipif(sys.platform == 'win32', reason='POSIX file modes')


def _mode(path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def _run(tmp_path, monkeypatch, *args, env=None):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    monkeypatch.delenv('TS_API_KEY', raising=False)
    project = tmp_path / 'project'
    project.mkdir(exist_ok=True)
    result = CliRunner().invoke(cli, ['init', *args, str(project)], env=env)
    return result, project / 'tsproject.toml'


def test_init_without_api_key_is_allowed(tmp_path, monkeypatch):
    result, cfg = _run(tmp_path, monkeypatch, '--project-name', 'Demo')

    assert result.exit_code == 0, result.output
    assert toml.load(cfg) == {'project_name': 'Demo'}
    assert 'API key' not in result.output


def test_init_warns_when_the_key_is_written(tmp_path, monkeypatch):
    result, cfg = _run(tmp_path, monkeypatch, '--project-name', 'Demo', '--api-key', 'secret-value')

    assert result.exit_code == 0, result.output
    assert toml.load(cfg)['api_key'] == 'secret-value'
    assert '.gitignore' in result.output


def test_init_does_not_persist_a_key_from_the_environment(tmp_path, monkeypatch):
    result, cfg = _run(tmp_path, monkeypatch, '--project-name', 'Demo', env={'TS_API_KEY': 'from-env'})

    assert result.exit_code == 0, result.output
    assert 'api_key' not in toml.load(cfg)


@posix_only
def test_project_file_is_private(tmp_path, monkeypatch):
    result, cfg = _run(tmp_path, monkeypatch, '--api-key', 'secret-value')

    assert result.exit_code == 0, result.output
    assert _mode(cfg) == 0o600


@posix_only
def test_default_user_config_is_private(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, '--project-name', 'Demo')

    home_cfg = tmp_path / 'home' / '.ts-scan' / 'config'
    assert home_cfg.exists()
    assert _mode(home_cfg) == 0o600
    assert _mode(home_cfg.parent) == 0o700
