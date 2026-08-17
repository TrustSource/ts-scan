import json
from pathlib import Path

from ts_scan.pm.nuget import NugetScanner


def test_project_dependency_uses_project_reference_path(tmp_path, monkeypatch, capsys):
    console_dir = tmp_path / 'TS-NetCore-Scanner.ConsoleApp'
    engine_dir = tmp_path / 'TS-NetCore-Scanner.Engine'
    console_dir.mkdir()
    engine_dir.mkdir()

    (console_dir / 'TS.NetCore.Scanner.ConsoleApp.csproj').write_text(
        '''<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <ProjectReference Include="..\\TS-NetCore-Scanner.Engine\\TS-NetCore-Scanner.Engine.csproj" />
  </ItemGroup>
</Project>
'''
    )
    (engine_dir / 'TS-NetCore-Scanner.Engine.csproj').write_text(
        '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <AssemblyName>TS.NetCore.Scanner.Engine</AssemblyName>
  </PropertyGroup>
</Project>
'''
    )

    lockfile = console_dir / 'packages.lock.json'
    lockfile.write_text(json.dumps({
        'version': 1,
        'dependencies': {
            'net8.0': {
                'TS.NetCore.Scanner.Engine': {
                    'type': 'Project',
                },
            },
        },
    }))

    scanner = NugetScanner()
    monkeypatch.setattr(scanner, '_process_package', lambda path, depth=0: [])

    dependencies = scanner._create_deps_from_lockfile(lockfile)

    assert len(dependencies) == 1
    assert dependencies[0].package_files == [str(engine_dir)]
    assert 'Could not find dependency location' not in capsys.readouterr().out


def test_global_package_lookup_preserves_actual_path_casing(tmp_path):
    global_packages = tmp_path / 'NuGetCache'
    package_dir = global_packages / 'Newtonsoft.Json' / '13.0.3'
    package_dir.mkdir(parents=True)

    scanner = NugetScanner()
    setattr(scanner, '_NugetScanner__global_packages_dir', global_packages)

    candidates = scanner._find_in_global_packages('newtonsoft.json', '13.0.3')

    assert candidates == [package_dir]
    assert candidates[0].exists()


def test_sdk_project_prefers_dotnet_when_nuget_is_also_installed(tmp_path, monkeypatch):
    project_file = tmp_path / 'Example.csproj'
    project_file.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
    scanner = NugetScanner()

    monkeypatch.setattr(
        'ts_scan.pm.nuget.shutil.which',
        lambda executable: f'/usr/local/bin/{executable}',
    )
    monkeypatch.setattr(scanner, '_find_global_packages_dir', lambda: tmp_path / 'packages')
    monkeypatch.setattr(scanner, '_process_package', lambda path: [])

    scanner.scan(project_file)

    assert scanner.executable_path == Path('/usr/local/bin/dotnet')
    assert getattr(scanner, '_NugetScanner__using_dotnet_sdk') is True


def test_packages_config_prefers_nuget(tmp_path, monkeypatch):
    packages_config = tmp_path / 'packages.config'
    packages_config.write_text('<packages />\n')
    (tmp_path / 'Legacy.csproj').write_text('<Project />\n')
    scanner = NugetScanner()

    monkeypatch.setattr(
        'ts_scan.pm.nuget.shutil.which',
        lambda executable: f'/usr/local/bin/{executable}',
    )
    monkeypatch.setattr(scanner, '_find_global_packages_dir', lambda: tmp_path / 'packages')
    monkeypatch.setattr(scanner, '_process_package', lambda path: [])

    scanner.scan(tmp_path)

    assert scanner.executable_path == Path('/usr/local/bin/nuget')
    assert getattr(scanner, '_NugetScanner__using_dotnet_sdk') is False


def test_restore_uses_the_cache_searched_for_dependency_locations(tmp_path, monkeypatch):
    project_file = tmp_path / 'Example.csproj'
    project_file.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
    lockfile = tmp_path / 'packages.lock.json'
    lockfile.write_text(json.dumps({
        'version': 1,
        'dependencies': {
            'net8.0': {
                'Newtonsoft.Json': {
                    'type': 'Direct',
                    'resolved': '13.0.3',
                },
            },
        },
    }))

    global_packages = tmp_path / 'NuGetCache'
    package_dir = global_packages / 'newtonsoft.json' / '13.0.3'
    package_dir.mkdir(parents=True)
    scanner = NugetScanner()
    setattr(scanner, '_NugetScanner__path', project_file)
    setattr(scanner, '_NugetScanner__global_packages_dir', global_packages)
    setattr(scanner, '_NugetScanner__using_dotnet_sdk', True)
    executed = []

    def record_exec(*args, **kwargs):
        executed.append((args, kwargs))

    monkeypatch.setattr(scanner, '_exec', record_exec)
    monkeypatch.setattr(scanner, '_process_package', lambda path, depth=0: [])

    dependencies = scanner._process_with_lock_file(project_file)

    assert executed == [((
        'restore',
        str(project_file),
        '--use-lock-file',
        '--packages',
        str(global_packages),
    ), {'cwd': tmp_path})]
    assert dependencies[0].package_files == [str(package_dir)]
    assert package_dir.exists()
