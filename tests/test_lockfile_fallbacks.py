import json
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess

from ts_scan.pm.cargo import CargoScanner
from ts_scan.pm.golang import GolangScanner
from ts_scan.pm.node import NodeScanner
from ts_scan.pm.nuget import NugetScanner


def test_nuget_returns_no_dependencies_when_restore_creates_no_lockfile(
    tmp_path, monkeypatch, capsys
):
    project_file = tmp_path / 'Empty.csproj'
    project_file.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
    scanner = NugetScanner()
    setattr(scanner, '_NugetScanner__path', project_file)
    setattr(scanner, '_NugetScanner__global_packages_dir', tmp_path / 'packages')
    setattr(scanner, '_NugetScanner__using_dotnet_sdk', True)
    monkeypatch.setattr(scanner, '_exec', lambda *args, **kwargs: CompletedProcess([], 0))

    assert scanner._process_with_lock_file(project_file) == []
    output = capsys.readouterr().out
    assert 'did not generate packages.lock.json' in output
    assert 'without resolved dependencies' in output


def test_nuget_returns_no_dependencies_when_restore_fails_without_a_lockfile(
    tmp_path, monkeypatch, capsys
):
    project_file = tmp_path / 'Empty.csproj'
    project_file.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
    scanner = NugetScanner()
    setattr(scanner, '_NugetScanner__path', project_file)
    setattr(scanner, '_NugetScanner__global_packages_dir', tmp_path / 'packages')

    def fail_restore(*args, **kwargs):
        raise CalledProcessError(1, ['nuget', 'restore'])

    monkeypatch.setattr(
        scanner,
        '_exec',
        fail_restore,
    )

    assert scanner._process_with_lock_file(project_file) == []
    assert 'did not generate packages.lock.json' in capsys.readouterr().out


def test_nuget_uses_project_assets_when_restore_creates_no_lockfile(
    tmp_path, monkeypatch, capsys
):
    solution = tmp_path / 'Logging.sln'
    solution.write_text(
        'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = '
        '"Logging", "Logging.csproj", '
        '"{11111111-1111-1111-1111-111111111111}"\n'
    )
    project_file = tmp_path / 'Logging.csproj'
    project_file.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
    assets_dir = tmp_path / 'obj'
    assets_dir.mkdir()
    assets_file = assets_dir / 'project.assets.json'
    assets_file.write_text(json.dumps({
        'version': 3,
        'targets': {
            'net8.0': {
                'NLog/5.3.0': {
                    'type': 'package',
                    'dependencies': {},
                },
            },
        },
        'libraries': {
            'NLog/5.3.0': {
                'type': 'package',
                'path': 'nlog/5.3.0',
            },
        },
        'project': {
            'frameworks': {
                'net8.0': {
                    'dependencies': {
                        'NLog': {'target': 'Package', 'version': '[5.3.0, )'},
                    },
                },
            },
            'restore': {
                'projectName': 'Logging',
                'projectPath': str(project_file),
            },
        },
    }))
    scanner = NugetScanner()
    monkeypatch.setattr(scanner, '_select_executable', lambda path: None)
    monkeypatch.setattr(
        scanner, '_find_global_packages_dir', lambda: tmp_path / 'packages'
    )
    monkeypatch.setattr(scanner, '_exec', lambda *args, **kwargs: CompletedProcess([], 0))

    scan = next(iter(scanner.scan(solution)))

    assert scan.module == 'Logging'
    assert [dep.name for dep in scan.dependencies] == ['Logging']
    dependencies = scan.dependencies[0].dependencies
    assert [(dep.name, dep.versions) for dep in dependencies] == [('NLog', ['5.3.0'])]
    output = capsys.readouterr().out
    assert 'Using resolved' in output
    assert 'dependencies from' in output
    assert 'project.assets.json' in output


def test_nuget_uses_default_package_cache_when_executable_returns_no_location(
    tmp_path, monkeypatch, capsys
):
    project_file = tmp_path / 'Logging.csproj'
    project_file.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
    scanner = NugetScanner(executable=tmp_path / 'no-op')
    setattr(scanner, '_NugetScanner__path', project_file)
    monkeypatch.delenv('NUGET_PACKAGES', raising=False)
    monkeypatch.setattr(
        scanner,
        '_exec',
        lambda *args, **kwargs: CompletedProcess([], 0, stdout=b''),
    )

    packages = scanner._find_global_packages_dir()

    assert packages == Path.home() / '.nuget' / 'packages'
    assert 'Could not determine the NuGet global-packages directory' in capsys.readouterr().out


def test_node_returns_manifest_only_scan_when_install_creates_no_lockfile(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / 'package.json').write_text(json.dumps({
        'name': 'empty-node-project',
        'version': '1.2.3',
    }))
    scanner = NodeScanner()
    monkeypatch.setattr(scanner, '_exec', lambda *args, **kwargs: CompletedProcess([], 0))

    scans = list(scanner.scan(tmp_path))

    assert len(scans) == 1
    assert scans[0].module == 'empty-node-project'
    assert scans[0].dependencies[0].dependencies == []
    output = capsys.readouterr().out
    assert 'did not generate package-lock.json' in output
    assert 'without resolved dependencies' in output


def test_cargo_returns_manifest_only_scan_when_no_lockfile_is_generated(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / 'Cargo.toml').write_text(
        '[package]\nname = "empty-cargo-project"\nversion = "1.2.3"\n'
    )
    scanner = CargoScanner()
    monkeypatch.setattr(scanner, '_exec', lambda *args, **kwargs: CompletedProcess([], 0))

    scans = list(scanner.scan(tmp_path))

    assert len(scans) == 1
    assert scans[0].module == 'empty-cargo-project'
    assert scans[0].dependencies[0].dependencies == []
    output = capsys.readouterr().out
    assert 'did not generate Cargo.lock' in output
    assert 'resolved dependencies' in output


def test_go_reports_missing_sum_and_still_returns_scan(tmp_path, monkeypatch, capsys):
    (tmp_path / 'go.mod').write_text('module example.com/empty\n\ngo 1.22\n')
    scanner = GolangScanner()
    monkeypatch.setattr(scanner, '_exec', lambda *args, **kwargs: CompletedProcess([], 0))

    scans = list(scanner.scan(tmp_path))

    assert len(scans) == 1
    assert scans[0].module == 'example.com/empty'
    assert scans[0].dependencies[0].dependencies == []
    output = capsys.readouterr().out
    assert 'did not generate go.sum' in output
    assert 'resolved dependencies' in output
