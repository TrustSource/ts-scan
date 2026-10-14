import io
import json
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess

import pytest
from click.testing import CliRunner

from ts_scan import process_scan
from ts_scan.cli import cli
from ts_scan.cli import scan as scan_cli
from ts_scan.pm import Dependency, DependencyScan, ExecutableNotFoundError, dump_scans, load_scans
from ts_scan.pm.conan import ConanScanner


EXAMPLE = Path(__file__).parents[1] / 'examples' / 'conan'


def graph():
    return json.loads((EXAMPLE / 'graph.json').read_text())


def scan_data(tmp_path, data, **kwargs):
    path = tmp_path / 'graph.json'
    path.write_text(json.dumps(data))
    return list(ConanScanner(graphFile=path, **kwargs).scan(tmp_path))


@pytest.mark.parametrize('recipe', ['conanfile.py', 'conanfile.txt'])
def test_detection(tmp_path, recipe):
    scanner = ConanScanner()
    assert not scanner.accepts(tmp_path)
    manifest = tmp_path / recipe
    manifest.touch()
    assert scanner.accepts(tmp_path)
    assert scanner.accepts(manifest)
    assert not scanner.accepts(tmp_path / 'graph.json')


def test_graph_preserves_direct_edges_shared_dependencies_and_metadata(tmp_path):
    scan = scan_data(tmp_path, graph())[0]
    assert scan.module == tmp_path.name
    assert scan.moduleId == 'conan:' + tmp_path.name
    root = scan.dependencies[0]
    assert [d.name for d in root.dependencies] == ['zlib', 'mylib']
    zlib, mylib = root.dependencies
    assert [d.name for d in zlib.dependencies] == ['helper']
    assert [d.name for d in mylib.dependencies] == ['zlib']
    assert mylib.dependencies[0].dependencies[0].name == 'helper'
    assert zlib.versions == ['1.3.1']
    assert zlib.licenses[0].name == 'Zlib'
    assert zlib.homepageUrl == 'https://zlib.net'
    assert zlib.meta['conan']['package_id'] == 'binary-zlib'
    assert zlib.qualifiers['arch'] == 'x86_64'
    assert mylib.purl.to_string() == 'pkg:conan/mylib@1.0?channel=stable&rrev=recipe-mylib&user=acme'


def test_build_and_test_dependencies_are_independent_options(tmp_path):
    for kwargs, expected in [
        ({'includeBuildDependencies': True}, ['zlib', 'mylib', 'cmake']),
        ({'includeTestDependencies': True}, ['zlib', 'mylib', 'catch2']),
    ]:
        root = scan_data(tmp_path, graph(), **kwargs)[0].dependencies[0]
        assert [d.name for d in root.dependencies] == expected


def test_cycle_is_reported_without_truncating_shared_branches(tmp_path, capsys):
    data = graph()
    data['graph']['nodes']['5']['dependencies']['1'] = {'direct': True}
    scan = scan_data(tmp_path, data)[0]
    assert len(list(scan.iterdeps())) == 6
    assert 'cycle' in capsys.readouterr().out


@pytest.mark.parametrize('data', [
    {}, {'graph': {'nodes': []}},
    {'graph': {'nodes': {'0': {'dependencies': {'1': {'direct': True}}}}}},
    {'graph': {'nodes': {'0': {'dependencies': []}}}},
])
def test_malformed_graph_produces_no_scan(tmp_path, data, capsys):
    assert scan_data(tmp_path, data) == []
    assert 'incomplete' in capsys.readouterr().out


def test_invalid_json_produces_no_scan(tmp_path, capsys):
    path = tmp_path / 'graph.json'
    path.write_text('{')
    assert list(ConanScanner(graphFile=path).scan(tmp_path)) == []
    assert 'incomplete' in capsys.readouterr().out


def test_resolver_captures_json_and_honors_existing_lock(tmp_path, monkeypatch):
    (tmp_path / 'conanfile.py').touch()
    (tmp_path / 'conan.lock').write_text('{}')
    scanner = ConanScanner(verbose=True)
    calls = []

    def execute(*args, **kwargs):
        calls.append((args, kwargs))
        return CompletedProcess(args, 0, stdout=json.dumps(graph()).encode())

    monkeypatch.setattr(scanner, '_exec', execute)
    assert len(list(scanner.scan(tmp_path))) == 1
    args, kwargs = calls[0]
    assert args == ('graph', 'info', str(tmp_path), '--format=json',
                    '--lockfile=' + str(tmp_path / 'conan.lock'))
    assert kwargs == {'cwd': tmp_path, 'capture_output': True}


@pytest.mark.parametrize('error', [ExecutableNotFoundError('conan'), CalledProcessError(1, 'conan')])
def test_resolution_failure_does_not_claim_complete_scan(tmp_path, monkeypatch, error, capsys):
    scanner = ConanScanner()

    def execute(*args, **kwargs):
        raise error

    monkeypatch.setattr(scanner, '_exec', execute)
    assert list(scanner.scan(tmp_path)) == []
    assert 'incomplete' in capsys.readouterr().out


def test_forwarded_build_arguments_reach_subprocess(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr('ts_scan.pm.shutil.which', lambda value: '/bin/conan')

    def run(args, **kwargs):
        calls.append(args)
        return CompletedProcess(args, 0, stdout=json.dumps(graph()).encode())

    monkeypatch.setattr('ts_scan.pm.subprocess.run', run)
    scanner = ConanScanner(forward=('-pr:h=release,-pr:b=tools', '-o=*:shared=True'))
    assert list(scanner.scan(tmp_path))
    assert calls[0][-3:] == ['-pr:h=release', '-pr:b=tools', '-o=*:shared=True']


def test_registration_and_graph_file_cli(tmp_path):
    result = CliRunner().invoke(cli, ['scan', '--conan:graphFile', str(EXAMPLE / 'graph.json'),
                                     '-o', str(tmp_path / 'scan.json'), str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / 'scan.json').exists()
    assert json.loads((tmp_path / 'scan.json').read_text())[0]['moduleId'] == 'conan:' + tmp_path.name


def test_skipped_edges_are_excluded_even_with_build_and_test_enabled(tmp_path):
    data = graph()
    data['graph']['nodes']['0']['dependencies']['3']['skip'] = True
    scan = scan_data(tmp_path, data, includeBuildDependencies=True, includeTestDependencies=True)[0]
    assert [d.name for d in scan.dependencies[0].dependencies] == ['zlib', 'mylib', 'catch2']


def test_reference_only_identity_and_package_variants(tmp_path):
    data = graph()
    node = data['graph']['nodes']['2']
    for field in ('name', 'version', 'user', 'channel'):
        node.pop(field)
    node['settings'] = {'arch': 'armv8'}
    data['graph']['nodes']['6'] = dict(node, settings={'arch': 'x86_64'}, dependencies={})
    data['graph']['nodes']['0']['dependencies']['6'] = {'direct': True}
    root = scan_data(tmp_path, data)[0].dependencies[0]
    first, second = root.dependencies[1:]
    assert first.name == second.name == 'mylib'
    assert first.versions == second.versions == ['1.0']
    assert first.qualifiers['user'] == 'acme'
    assert first.key != second.key
    assert first.purl != second.purl


def test_module_identity_does_not_depend_on_build_settings(tmp_path):
    data = graph()
    data['graph']['nodes']['0'].update(name='app', version='1.0', settings={'os': 'Linux'})
    first = scan_data(tmp_path, data)[0]
    data['graph']['nodes']['0']['settings']['os'] = 'Windows'
    second = scan_data(tmp_path, data)[0]
    assert first.moduleId == second.moduleId == 'conan:app'


@pytest.mark.parametrize('fmt', ['ts', 'cyclonedx-json', 'spdx-json'])
def test_qualifiers_survive_processing_export_and_import(tmp_path, fmt):
    stable = Dependency.create_from_purl('pkg:conan/mylib@1.0?channel=stable&user=acme')
    testing = Dependency.create_from_purl('pkg:conan/mylib@1.0?channel=testing&user=acme')
    assert stable is not None and testing is not None
    assert stable.key != testing.key
    scan = process_scan(DependencyScan(module='app', moduleId='conan:app', dependencies=[stable, testing]))
    output = io.StringIO()
    dump_scans([scan], output, fmt)
    path = tmp_path / ('scan.' + ('json' if fmt != 'ts' else 'ts.json'))
    path.write_text(output.getvalue())
    restored = load_scans(path, fmt)[0]
    assert {dep.purl.to_string() for dep in restored.iterdeps()} == {
        stable.purl.to_string(), testing.purl.to_string()}
    assert stable.meta['purl'] == stable.purl.to_string()


def test_plain_purl_identity_is_unchanged():
    dep = Dependency.create_from_purl('pkg:pypi/requests@2.32.3')
    assert dep is not None
    assert dep.key == 'pypi:requests'
    assert dep.purl.to_string() == 'pkg:pypi/requests@2.32.3'
    assert 'qualifiers' not in dep.to_dict()
