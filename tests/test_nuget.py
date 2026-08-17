import json

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
