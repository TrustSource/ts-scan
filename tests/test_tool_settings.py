import json
import os
import stat
import sys

import pytest
import toml
from click.testing import CliRunner

from ts_scan import api as api_module
from ts_scan.api import DEFAULT_BASE_URL, TrustSourceAPI, normalize_base_url
from ts_scan.cli import cli, start  # noqa: F401  (start() registers the sub-commands)
from ts_scan.cli.upload import _app_base_url
import ts_scan.cli.configure  # noqa: F401
import ts_scan.cli.init  # noqa: F401
import ts_scan.cli.upload  # noqa: F401

posix_only = pytest.mark.skipif(sys.platform == 'win32', reason='POSIX file modes')

USER_KEY = 'user-key-from-tool-config'


class _Response:
    ok = True
    text = '{}'

    def __bool__(self):
        return True

    def json(self):
        return {}


@pytest.fixture
def requests_post(monkeypatch):
    calls = []

    def _post(url, headers=None, **kwargs):
        calls.append({'url': url, 'api_key': headers.get('x-api-key')})
        return _Response()

    monkeypatch.setattr(api_module.requests, 'post', _post)
    return calls


@pytest.fixture
def tool_config(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    for name in list(os.environ):
        if name.startswith('TS_'):
            monkeypatch.delenv(name)

    cfg_path = tmp_path / 'config'
    cfg_path.write_text(toml.dumps({'default': {'api_key': USER_KEY}}))
    return cfg_path


def _scanned_repo(tmp_path, proj_cfg: dict):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'tsproject.toml').write_text(toml.dumps(proj_cfg))

    scan_path = tmp_path / 'scan.json'
    scan_path.write_text(json.dumps({'module': 'm', 'moduleId': 'pypi:m', 'source': str(repo),
                                     'dependencies': []}))
    return scan_path


def _upload(tool_config, scan_path, *args, env=None):
    return CliRunner().invoke(cli, ['--config', str(tool_config), 'upload', '--project-name', 'p', *args,
                                    str(scan_path)], env=env)


@pytest.mark.parametrize('base_url, expected', [
    ('https://api.trustsource.io', 'https://api.trustsource.io/v2'),
    ('https://api.trustsource.io/', 'https://api.trustsource.io/v2'),
    ('https://api.trustsource.io/v2', 'https://api.trustsource.io/v2'),
    ('https://api.trustsource.io/v2/', 'https://api.trustsource.io/v2'),
    ('https://ts.example.test/api', 'https://ts.example.test/api/v2'),
])
def test_base_url_gets_the_api_version_exactly_once(base_url, expected):
    assert normalize_base_url(base_url) == expected


@pytest.mark.parametrize('base_url', ['https://api.trustsource.io', 'https://api.trustsource.io/v2'])
def test_api_paths_carry_no_version(requests_post, base_url):
    TrustSourceAPI(base_url, 'key').upload_scan({})

    assert requests_post[0]['url'] == 'https://api.trustsource.io/v2/core/scans'


def test_app_link_drops_the_api_version():
    assert _app_base_url('https://api.trustsource.io/v2') == 'https://app.trustsource.io'


def test_project_config_cannot_redirect_the_api_endpoint(tmp_path, tool_config, requests_post):
    scan_path = _scanned_repo(tmp_path, {'base_url': 'https://attacker.example.test',
                                         'api_key': 'attacker-key'})

    result = _upload(tool_config, scan_path)

    assert result.exit_code == 0, result.output
    assert requests_post == [{'url': f'{DEFAULT_BASE_URL}/core/scans', 'api_key': USER_KEY}]
    assert "Ignoring 'base_url'" in result.output
    assert "Ignoring 'api_key'" in result.output


def test_project_config_still_sets_the_project_name(tmp_path, tool_config, monkeypatch):
    payloads = []
    monkeypatch.setattr(TrustSourceAPI, 'upload_scan', lambda self, data: payloads.append(data) or {})
    scan_path = _scanned_repo(tmp_path, {'project_name': 'from-project'})

    result = CliRunner().invoke(cli, ['--config', str(tool_config), 'upload', str(scan_path)])

    assert result.exit_code == 0, result.output
    assert payloads[0]['project'] == 'from-project'


@pytest.mark.parametrize('how', ['option', 'environment', 'tool_config'])
def test_base_url_from_startup_sources_is_used(tmp_path, tool_config, requests_post, how):
    scan_path = _scanned_repo(tmp_path, {'base_url': 'https://attacker.example.test'})
    url = 'https://api.staging.example.test'

    if how == 'option':
        result = _upload(tool_config, scan_path, '--base-url', url)
    elif how == 'environment':
        result = _upload(tool_config, scan_path, env={'TS_UPLOAD_BASE_URL': url})
    else:
        tool_config.write_text(toml.dumps({'default': {'api_key': USER_KEY, 'base_url': url}}))
        result = _upload(tool_config, scan_path)

    assert result.exit_code == 0, result.output
    assert requests_post[0]['url'] == f'{url}/v2/core/scans'


@pytest.mark.parametrize('key', ['node_executable', 'maven_executable', 'node_forward', 'pypi_forward',
                                 'output_path', 'node_enableLifecycleScripts'])
def test_project_config_cannot_set_options_which_run_programs_or_write_files(tmp_path, monkeypatch, key):
    from ts_scan.cli import _load_project_config, msg

    monkeypatch.setattr(msg, 'warn', lambda text: None)
    (tmp_path / 'tsproject.toml').write_text(toml.dumps({key: 'x', 'pypi_extras': 'dev'}))

    assert _load_project_config(tmp_path) == {'pypi_extras': 'dev'}


@pytest.mark.parametrize('value', ['https://${TOKEN}@x/simple', '$HOME/x', ['https://a', 'https://$TOKEN@b']])
def test_project_config_cannot_reference_environment_variables(tmp_path, monkeypatch, value):
    from ts_scan.cli import _load_project_config, msg

    monkeypatch.setattr(msg, 'warn', lambda text: None)
    (tmp_path / 'tsproject.toml').write_text(toml.dumps({'pypi_indexUrl': value, 'project_name': 'p'}))

    assert _load_project_config(tmp_path) == {'project_name': 'p'}


@posix_only
def test_scanning_a_repository_does_not_run_its_executable(tmp_path, tool_config):
    import ts_scan.cli.scan  # noqa: F401

    marker = tmp_path / 'executed'
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'package.json').write_text('{"name": "x", "version": "1.0.0"}')
    script = repo / 'evil.sh'
    script.write_text(f'#!/bin/sh\ntouch {marker}\nexit 1\n')
    script.chmod(0o755)
    (repo / 'tsproject.toml').write_text(toml.dumps({'node_executable': str(script),
                                                     'output_path': str(tmp_path / 'overwritten')}))

    result = CliRunner().invoke(cli, ['--config', str(tool_config), 'scan', '-o', str(tmp_path / 'scan.json'),
                                      str(repo)])

    assert result.exit_code == 0, result.output
    assert not marker.exists()
    assert not (tmp_path / 'overwritten').exists()


def test_init_no_longer_accepts_tool_settings(tmp_path, tool_config):
    project = tmp_path / 'project'
    project.mkdir()

    result = CliRunner().invoke(cli, ['--config', str(tool_config), 'init', '--api-key', 'k', str(project)])

    assert result.exit_code == 2
    assert not (project / 'tsproject.toml').exists()


def _configure(tool_config, *args, env=None):
    return CliRunner().invoke(cli, ['--config', str(tool_config), *args], env=env)


def test_configure_updates_the_profile_and_keeps_others(tool_config):
    tool_config.write_text(toml.dumps({'default': {'api_key': USER_KEY, 'project_name': 'p'},
                                       'dev': {'api_key': 'dev-key'}}))

    result = _configure(tool_config, 'configure', '--base-url', 'https://api.dev.example.test')

    assert result.exit_code == 0, result.output
    assert toml.load(tool_config) == {
        'default': {'api_key': USER_KEY, 'project_name': 'p', 'base_url': 'https://api.dev.example.test'},
        'dev': {'api_key': 'dev-key'},
    }


def test_configure_creates_a_new_profile(tool_config):
    result = _configure(tool_config, '-p', 'staging', 'configure', '--api-key', 'staging-key')

    assert result.exit_code == 0, result.output
    assert toml.load(tool_config)['staging'] == {'api_key': 'staging-key'}


def test_configure_does_not_persist_a_key_from_the_environment(tool_config):
    result = _configure(tool_config, 'configure', '--base-url', 'https://x.example.test',
                        env={'TS_CONFIGURE_API_KEY': 'from-env'})

    assert result.exit_code == 0, result.output
    assert toml.load(tool_config)['default']['api_key'] == USER_KEY


def test_configure_without_options_shows_the_masked_profile(tool_config):
    result = _configure(tool_config, 'configure')

    assert result.exit_code == 0, result.output
    assert 'user-***' in result.output
    assert USER_KEY not in result.output


@posix_only
def test_configure_keeps_the_config_private(tool_config):
    tool_config.chmod(0o644)

    result = _configure(tool_config, 'configure', '--api-key', 'new-key')

    assert result.exit_code == 0, result.output
    assert stat.S_IMODE(os.stat(tool_config).st_mode) == 0o600
    assert toml.load(tool_config)['default']['api_key'] == 'new-key'
