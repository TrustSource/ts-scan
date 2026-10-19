import io
import json
import shutil
from subprocess import CalledProcessError, CompletedProcess
from pathlib import Path

import pytest
from click.testing import CliRunner

from ts_scan import process_scan
from ts_scan.cli import cli
from ts_scan.cli import scan as scan_cli
from ts_scan.pm import Dependency, dump_scans, load_scans, LicenseKind
from ts_scan.pm.vcpkg import VcpkgScanner


EXAMPLE = Path(__file__).parents[1] / 'examples' / 'vcpkg'


@pytest.fixture
def project(tmp_path):
    shutil.copytree(EXAMPLE, tmp_path / 'project')
    return tmp_path / 'project'


def scanner(project, **kwargs):
    return VcpkgScanner(installedDir=project / 'installed', **kwargs)


def root(project, **kwargs):
    return list(scanner(project, **kwargs).scan(project))[0].dependencies[0]


def by_name(dep, name):
    return next(child for child in dep.dependencies if child.name == name)


def test_detection_and_default_installation_location(project, tmp_path):
    s = VcpkgScanner()
    assert not s.accepts(tmp_path)
    assert s.accepts(project)
    assert s.accepts(project / 'vcpkg.json')
    assert s.accepts(project / 'installed')
    (project / 'installed').rename(project / 'vcpkg_installed')
    assert list(s.scan(project))


def test_pending_updates_features_cross_triplet_edges_and_scope(project):
    dep = root(project, triplet='arm64-linux', roots=('curl', 'libpng'))
    assert dep.meta['vcpkg']['scope'] == 'roots'
    assert dep.meta['vcpkg']['metadata_complete'] is True
    assert [child.name for child in dep.dependencies] == ['curl', 'libpng']
    curl = by_name(dep, 'curl')
    assert curl.meta['vcpkg']['features'] == ['ssl']
    assert {child.name for child in curl.dependencies} == {'libpng', 'zlib', 'vcpkg-cmake'}
    zlib = by_name(curl, 'zlib')
    assert zlib.versions == ['1.3.1']
    assert zlib.qualifiers['port_version'] == '1'
    assert by_name(zlib, 'vcpkg-cmake').qualifiers['triplet'] == 'x64-linux'
    assert by_name(by_name(curl, 'libpng'), 'zlib').version == '1.3.1'
    assert 'abi-zlib' == zlib.meta['vcpkg']['abi']
    assert not zlib.checksum


def test_inventory_includes_unrelated_ports_but_excludes_removed_packages(project):
    dep = root(project, triplet='arm64-linux')
    assert dep.meta['vcpkg']['scope'] == 'inventory'
    assert {child.name for child in dep.dependencies} == {'curl', 'libpng', 'zlib', 'fmt'}
    assert 'vcpkg-cmake' in {child.name for child in by_name(dep, 'curl').dependencies}


def test_spdx_enrichment_preserves_license_expression_and_registry(project):
    lib = root(project, triplet='arm64-linux', roots=('libpng',)).dependencies[0]
    assert lib.version == '1.6.44'
    assert lib.qualifiers['port_version'] == '2'
    assert lib.qualifiers['repository_url'] == 'https://example.invalid/private-vcpkg'
    assert lib.licenses[0].name == 'MIT AND BSD-3-Clause'
    assert lib.licenses[0].kind == LicenseKind.EFFECTIVE
    assert lib.meta['vcpkg']['sources'][0]['SPDXID'] == 'SPDXRef-resource-0'
    assert 'abi' not in lib.purl.to_string()


def test_updates_only_database_and_no_database_mutations(project):
    installed = project / 'installed'
    db = installed / 'vcpkg'
    (db / 'updates/0000000000').write_bytes((db / 'status').read_bytes())
    (db / 'status').unlink()
    before = {path: path.read_bytes() for path in installed.rglob('*') if path.is_file()}
    assert root(project).meta['vcpkg']['metadata_complete']
    after = {path: path.read_bytes() for path in installed.rglob('*') if path.is_file()}
    assert before == after


def test_latest_feature_update_removes_its_dependencies(project):
    db = project / 'installed/vcpkg/updates'
    (db / '0000000003').write_text(
        'Package: curl\nFeature: ssl\nArchitecture: arm64-linux\nMulti-Arch: same\n'
        'Status: deinstall ok not-installed\nDepends: libpng\n')
    curl = root(project, triplet='arm64-linux', roots=('curl',)).dependencies[0]
    assert curl.meta['vcpkg']['features'] == []
    assert 'libpng' not in {d.name for d in curl.dependencies}


def test_cycles_are_reported_and_shared_branches_remain(project, capsys):
    path = project / 'installed/vcpkg/updates/0000000001'
    path.write_text(path.read_text().replace('Depends: vcpkg-cmake:x64-linux', 'Depends: curl'))
    dep = root(project, triplet='arm64-linux', roots=('curl',))
    assert len(list(dep.dependencies[0].dependencies)) == 3
    assert list(dep.dependencies[0].dependencies)
    assert 'cycle' in capsys.readouterr().out
    assert dep.meta['vcpkg']['metadata_complete'] is False


@pytest.mark.parametrize('change', ['missing', 'malformed', 'stale', 'mismatched'])
def test_unavailable_spdx_keeps_resolved_graph_with_warning(project, change, capsys):
    path = project / 'installed/arm64-linux/share/libpng/vcpkg.spdx.json'
    if change == 'missing':
        path.unlink()
    elif change == 'malformed':
        path.write_text('{')
    else:
        data = json.loads(path.read_text())
        data['packages'][0]['versionInfo' if change == 'stale' else 'name'] = 'wrong'
        path.write_text(json.dumps(data))
    dep = root(project, triplet='arm64-linux', roots=('libpng',))
    assert dep.dependencies[0].version == '1.6.44'
    assert by_name(dep.dependencies[0], 'zlib').version == '1.3.1'
    assert not dep.dependencies[0].licenses
    assert dep.meta['vcpkg']['metadata_complete'] is False
    assert 'metadata incomplete' in capsys.readouterr().out


@pytest.mark.parametrize('kwargs', [
    {'triplet': 'arm64-linux', 'roots': ('unknown',)},
    {'roots': ('curl',)},
    {'triplet': 'arm64-linux', 'roots': ('curl:x64-linux',)},
    {'triplet': '../bad'},
    {'triplet': 'x64-windows'},
])
def test_invalid_or_uninstalled_root_is_reported(project, kwargs, capsys):
    assert list(scanner(project, **kwargs).scan(project)) == []
    assert 'incomplete' in capsys.readouterr().out


def test_missing_dependency_does_not_produce_resolved_scan(project, capsys):
    path = project / 'installed/vcpkg/status'
    path.write_text(path.read_text().replace('Depends: zlib\n', 'Depends: unknown\n'))
    assert list(scanner(project, triplet='arm64-linux', roots=('libpng',)).scan(project)) == []
    assert 'Missing installed dependency' in capsys.readouterr().out


@pytest.mark.parametrize('contents', [
    'Package: zlib\nPackage: curl\n',
    ' broken continuation\n',
    'Package: zlib\nArchitecture: arm64-linux\nStatus: broken\n',
    'Package: zlib\nArchitecture: arm64-linux\nStatus: install ok installed\nFeature: ssl\n',
])
def test_invalid_database_does_not_produce_scan(project, contents, capsys):
    shutil.rmtree(project / 'installed/vcpkg/updates')
    (project / 'installed/vcpkg/status').write_text(contents)
    assert list(scanner(project).scan(project)) == []
    assert 'incomplete' in capsys.readouterr().out


def test_no_install_override_does_not_trigger_resolution(tmp_path, capsys):
    (tmp_path / 'vcpkg.json').write_text('{"dependencies":["zlib"]}')
    assert list(VcpkgScanner(noInstall=True).scan(tmp_path)) == []
    assert 'No vcpkg status database' in capsys.readouterr().out


def test_example_scans_without_any_vcpkg_options(project, monkeypatch):
    s = VcpkgScanner()

    def unexpected(*args, **kwargs):
        pytest.fail('Existing local package data should not invoke vcpkg')

    monkeypatch.setattr(s, '_exec', unexpected)
    scan = list(s.scan(project))[0]
    assert scan.dependencies[0].meta['vcpkg']['installed_dir'] == str(project / 'installed')
    assert scan.dependencies[0].meta['vcpkg']['metadata_complete']


@pytest.mark.parametrize('build', ['build', 'build/debug', 'cmake-build-debug', 'out/build/default'])
def test_discovers_standard_cmake_build_folders(project, build):
    destination = project / build / 'vcpkg_installed'
    destination.parent.mkdir(parents=True, exist_ok=True)
    (project / 'installed').rename(destination)
    scan = list(VcpkgScanner().scan(project))[0]
    assert scan.dependencies[0].meta['vcpkg']['installed_dir'] == str(destination)


def test_cmake_cache_resolves_custom_install_directory(project):
    installed = project / 'custom-libraries'
    (project / 'installed').rename(installed)
    build = project / 'build'
    build.mkdir()
    (build / 'CMakeCache.txt').write_text('VCPKG_INSTALLED_DIR:PATH=../custom-libraries\n')
    scan = list(VcpkgScanner().scan(project))[0]
    assert scan.dependencies[0].meta['vcpkg']['installed_dir'] == str(installed)


def test_installed_directory_environment_is_respected(project, monkeypatch):
    monkeypatch.setenv('VCPKG_INSTALLED_DIR', str(project / 'installed'))
    assert list(VcpkgScanner().scan(project))


def test_classic_vcpkg_root_discovery(project, monkeypatch):
    (project / 'vcpkg.json').unlink()
    checkout = project / 'checkout'
    checkout.mkdir()
    (project / 'installed').rename(checkout / 'installed')
    monkeypatch.setenv('VCPKG_ROOT', str(checkout))
    scan = list(VcpkgScanner().scan(project))[0]
    assert scan.dependencies[0].meta['vcpkg']['installed_dir'] == str(checkout / 'installed')


def test_ambiguous_builds_report_override_instead_of_guessing(project, capsys):
    for build in ('build/debug', 'build/release'):
        shutil.copytree(project / 'installed', project / build / 'vcpkg_installed')
    shutil.rmtree(project / 'installed')
    assert list(VcpkgScanner().scan(project)) == []
    assert 'Multiple vcpkg build installations' in capsys.readouterr().out


def test_missing_packages_are_installed_with_discovered_toolchain_root(project, monkeypatch):
    snapshot = project / 'installed'
    # Keep fixture data outside discovery locations until our simulated install.
    snapshot.rename(project / 'snapshot')
    checkout = project / 'tools' / 'vcpkg'
    (checkout / 'scripts/buildsystems').mkdir(parents=True)
    (checkout / '.vcpkg-root').touch()
    toolchain = checkout / 'scripts/buildsystems/vcpkg.cmake'
    toolchain.touch()
    (project / 'build').mkdir()
    (project / 'build/CMakeCache.txt').write_text(f'CMAKE_TOOLCHAIN_FILE:FILEPATH={toolchain}\n')
    monkeypatch.delenv('VCPKG_ROOT', raising=False)
    s = VcpkgScanner(triplet='arm64-linux', roots=('curl',))
    calls = []

    def install(*args, **kwargs):
        calls.append((args, kwargs))
        shutil.copytree(project / 'snapshot', project / 'vcpkg_installed')
        return CompletedProcess(args, 0)

    monkeypatch.setattr(s, '_exec', install)
    assert list(s.scan(project))
    args, kwargs = calls[0]
    assert args[0] == 'install'
    assert '--x-manifest-root=' + str(project) in args
    assert '--x-install-root=' + str(project / 'vcpkg_installed') in args
    assert '--vcpkg-root=' + str(checkout) in args
    assert '--triplet=arm64-linux' in args
    assert kwargs == {'cwd': project, 'capture_output': True}


def test_explicit_snapshot_is_not_replaced_or_installed(project, monkeypatch, capsys):
    s = VcpkgScanner(installedDir=project / 'missing')
    monkeypatch.setattr(s, '_exec', lambda *args, **kwargs: pytest.fail('Explicit snapshot must be read-only'))
    assert list(s.scan(project)) == []
    assert 'No vcpkg status database' in capsys.readouterr().out


def test_install_failure_reports_vcpkg_diagnostic(project, monkeypatch, capsys):
    shutil.rmtree(project / 'installed')
    s = VcpkgScanner()

    def fail(*args, **kwargs):
        raise CalledProcessError(1, args, stderr=b'Could not detect vcpkg-root; configure VCPKG_ROOT')

    monkeypatch.setattr(s, '_exec', fail)
    assert list(s.scan(project)) == []
    assert 'Could not detect vcpkg-root' in capsys.readouterr().out


def test_empty_scanner_does_not_report_success(project, monkeypatch, capsys):
    import ts_scan
    monkeypatch.setattr(ts_scan, '__get_pm_scanner_classes', lambda: [VcpkgScanner])
    monkeypatch.setattr(VcpkgScanner, 'scan', lambda self, src: [])
    assert list(ts_scan.do_scan([project])) == []
    output = capsys.readouterr().out
    assert 'No dependency scan was produced' in output
    assert 'Dependency scan completed' not in output


def test_cli_default_command_works_without_flags(project, tmp_path):
    output = tmp_path / 'scan.json'
    result = CliRunner().invoke(cli, ['scan', str(project), '-o', str(output)])
    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text())[0]['dependencies'][0]['meta']['vcpkg']['metadata_complete']


def test_cli_registration_and_root_selection(project, tmp_path):
    output = tmp_path / 'scan.json'
    result = CliRunner().invoke(cli, ['scan', str(project), '--vcpkg:installedDir', str(project / 'installed'),
                                     '--vcpkg:triplet', 'arm64-linux', '--vcpkg:roots', 'curl', '-o', str(output)])
    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text())[0]['moduleId'] == 'vcpkg:sample-app:roots:arm64-linux'


@pytest.mark.parametrize('fmt', ['ts', 'cyclonedx-json', 'spdx-json'])
def test_export_import_preserves_variants_versions_and_full_license(project, tmp_path, fmt):
    scan = list(scanner(project, triplet='arm64-linux', roots=('curl',)).scan(project))[0]
    process_scan(scan)
    original = scan.as_purls_dict()
    output = io.StringIO()
    dump_scans([scan], output, fmt)
    path = tmp_path / 'scan.json'
    path.write_text(output.getvalue())
    restored = load_scans(path, fmt)[0].as_purls_dict()
    assert set(restored) == set(original)
    purl = next(value for value in original if value.startswith('pkg:vcpkg/libpng@'))
    assert restored[purl].licenses[0].name == 'MIT AND BSD-3-Clause'


def test_import_native_vcpkg_spdx_uses_port_version_and_concluded_license(project):
    path = project / 'installed/arm64-linux/share/libpng/vcpkg.spdx.json'
    scan = load_scans(path, 'spdx-json')[0]
    dep = next(scan.iterdeps())
    assert dep.version == '1.6.44'
    assert dep.qualifiers['port_version'] == '2'
    assert dep.licenses[0].name == 'MIT AND BSD-3-Clause'
    assert dep.licenses[0].kind == LicenseKind.EFFECTIVE


def test_plain_purl_compatibility_and_qualified_identity():
    dep = Dependency.create_from_purl('pkg:pypi/requests@2.32.3')
    assert dep.key == 'pypi:requests'
    assert 'qualifiers' not in dep.to_dict()
    linux = Dependency.create_from_purl('pkg:vcpkg/zlib@1.3.1?triplet=x64-linux')
    windows = Dependency.create_from_purl('pkg:vcpkg/zlib@1.3.1?triplet=x64-windows')
    assert linux.key != windows.key
