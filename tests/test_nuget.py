import json
import shutil
from io import StringIO
from pathlib import Path

import ts_scan
from ts_scan.pm import Dependency, dump_scans
from ts_scan.pm.nuget import NugetScanner

EXAMPLE_SOLUTION = Path(__file__).parents[1] / 'examples' / 'nuget'


def test_solution_scan_preserves_projects_as_direct_dependencies(
    tmp_path, monkeypatch
):
    example = tmp_path / 'nuget-example'
    shutil.copytree(EXAMPLE_SOLUTION, example)
    app_file = example / 'Example.App' / 'Example.App.csproj'
    core_file = example / 'Legacy.Core' / 'Legacy.Core.csproj'
    shared_file = example / 'Shared' / 'Shared.csproj'

    def write_restore_data(
        project_file, project_name, lock_projects, asset_projects, direct_projects
    ):
        project_file.parent.joinpath('packages.lock.json').write_text(json.dumps({
            'version': 1,
            'dependencies': {
                'net8.0': {
                    name.casefold(): {'type': 'Project'}
                    for name in lock_projects
                },
            },
        }))

        assets_dir = project_file.parent / 'obj'
        assets_dir.mkdir(exist_ok=True)
        assets_dir.joinpath('project.assets.json').write_text(json.dumps({
            'libraries': {
                f'{name}/1.0.0': {
                    'type': 'project',
                    'msbuildProject': str(path),
                }
                for name, path in asset_projects.items()
            },
            'project': {
                'restore': {
                    'projectName': project_name,
                    'projectPath': str(project_file),
                    'frameworks': {
                        'net8.0': {
                            'projectReferences': {
                                str(path): {'projectPath': str(path)}
                                for path in direct_projects
                            },
                        },
                    },
                },
            },
        }))

    write_restore_data(
        app_file,
        'Example.App',
        ['Example.Core', 'Example.Shared'],
        {'Example.Core': core_file, 'Example.Shared': shared_file},
        [core_file],
    )
    write_restore_data(
        core_file,
        'Example.Core',
        ['Example.Shared'],
        {'Example.Shared': shared_file},
        [shared_file],
    )
    write_restore_data(shared_file, 'Example.Shared', [], {}, [])

    scanner = NugetScanner()
    monkeypatch.setattr(scanner, '_select_executable', lambda path: None)
    monkeypatch.setattr(scanner, '_find_global_packages_dir', lambda: tmp_path / 'cache')
    monkeypatch.setattr(scanner, '_exec', lambda *args, **kwargs: None)

    scan = next(iter(scanner.scan(example / 'ExampleSolution.sln')), None)

    assert scan is not None
    assert scan.module == 'ExampleSolution'
    assert scan.moduleId == 'nuget:ExampleSolution'
    assert [dep.name for dep in scan.dependencies] == [
        'Example.App',
        'Example.Core',
        'Example.Shared',
    ]
    assert [dep.meta['solution project name'] for dep in scan.dependencies] == [
        'Example.App',
        'Legacy.Core',
        'Shared',
    ]
    dependencies_by_project = {
        dep.name: [child.name for child in dep.dependencies]
        for dep in scan.dependencies
    }
    assert dependencies_by_project == {
        'Example.App': ['Example.Core', 'Example.Native'],
        'Example.Core': ['Example.Shared'],
        'Example.Shared': [],
    }
    native = next(
        dep
        for dep in scan.dependencies[0].dependencies
        if dep.key == 'lib:dll:Example.Native'
    )
    assert native.versions == ['2.1.0.0']
    assert native.meta['library_type'] == 'dll'
    assert native.meta['copy_local'] == 'true'


def test_solution_can_create_a_separate_scan_for_each_project(
    tmp_path, monkeypatch
):
    solution = tmp_path / 'Example.sln'
    solution.write_text('')
    projects = [
        Dependency(
            key='nuget:Example.App',
            name='Example.App',
            type='nuget',
            dependencies=[
                Dependency(key='nuget:Example.Core', name='Example.Core', type='nuget')
            ],
        ),
        Dependency(
            key='nuget:Example.Core',
            name='Example.Core',
            type='nuget',
        ),
    ]

    scanner = NugetScanner(separateProjectScans=True)
    monkeypatch.setattr(scanner, '_select_executable', lambda path: None)
    monkeypatch.setattr(scanner, '_find_global_packages_dir', lambda: tmp_path / 'cache')
    monkeypatch.setattr(scanner, '_process_solution_file', lambda path: projects)

    scans = list(scanner.scan(solution))

    assert [scan.module for scan in scans] == ['Example.App', 'Example.Core']
    assert [scan.moduleId for scan in scans] == [
        'nuget:Example.App',
        'nuget:Example.Core',
    ]
    assert [dep.name for dep in scans[0].dependencies] == ['Example.Core']
    assert scans[1].dependencies == []


def test_separate_project_scans_option_is_exposed():
    option = NugetScanner.options()['separateProjectScans']

    assert option['is_flag'] is True
    assert option['default'] is False


def test_do_scan_returns_all_solution_project_scans(tmp_path, monkeypatch):
    solution = tmp_path / 'Example.sln'
    solution.write_text('')
    projects = [
        Dependency(key='nuget:App', name='App', type='nuget'),
        Dependency(key='nuget:Library', name='Library', type='nuget'),
    ]

    monkeypatch.setattr(ts_scan, '__get_pm_scanner_classes', lambda: [NugetScanner])
    monkeypatch.setattr(NugetScanner, '_select_executable', lambda self, path: None)
    monkeypatch.setattr(
        NugetScanner,
        '_find_global_packages_dir',
        lambda self: tmp_path / 'cache',
    )
    monkeypatch.setattr(
        NugetScanner,
        '_process_solution_file',
        lambda self, path: projects,
    )

    scans = list(ts_scan.do_scan(
        [solution], nuget_separateProjectScans=True
    ))

    assert [scan.module for scan in scans] == ['App', 'Library']
    assert [scan.source for scan in scans] == [str(solution), str(solution)]

    output = StringIO()
    dump_scans(scans, output, 'ts')
    assert [entry['module'] for entry in json.loads(output.getvalue())] == [
        'App',
        'Library',
    ]


def test_single_project_scan_uses_nuget_project_name(tmp_path, monkeypatch):
    project_file = tmp_path / 'MediaBrowser.Common.csproj'
    project_file.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
    assets_dir = tmp_path / 'obj'
    assets_dir.mkdir()
    (assets_dir / 'project.assets.json').write_text(json.dumps({
        'libraries': {},
        'project': {
            'restore': {
                'projectName': 'Jellyfin.Common',
                'projectPath': str(project_file),
            },
        },
    }))

    scanner = NugetScanner()
    monkeypatch.setattr(scanner, '_select_executable', lambda path: None)
    monkeypatch.setattr(scanner, '_find_global_packages_dir', lambda: tmp_path / 'cache')
    monkeypatch.setattr(
        scanner,
        '_process_package',
        lambda path, **kwargs: [
            Dependency(key='nuget:Example', name='Example', type='nuget')
        ],
    )

    scan = next(iter(scanner.scan(project_file)), None)

    assert scan is not None
    assert scan.module == 'Jellyfin.Common'
    assert scan.moduleId == 'nuget:Jellyfin.Common'
    assert [dep.key for dep in scan.dependencies] == ['nuget:Example']


def test_external_file_references_are_library_dependencies(tmp_path):
    project_file = tmp_path / 'Example.csproj'
    library_dir = tmp_path / 'vendor'
    library_dir.mkdir()
    library_file = library_dir / 'Contoso.Interop.dll'
    library_file.write_bytes(b'not-a-real-assembly')
    project_file.write_text(
        '''<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup>
    <Reference Include="Contoso.Interop, Version=3.2.1.0, Culture=neutral, PublicKeyToken=abcdef">
      <HintPath>vendor\\Contoso.Interop.dll</HintPath>
      <Private>False</Private>
      <Aliases>global,contoso</Aliases>
      <SpecificVersion>True</SpecificVersion>
    </Reference>
    <Reference Include="System.Xml" />
    <ProjectReference Include="..\\Other\\Other.csproj" />
  </ItemGroup>
</Project>
'''
    )

    dependencies = NugetScanner._create_deps_from_external_references(project_file)

    assert len(dependencies) == 1
    dependency = dependencies[0]
    assert dependency.key == 'lib:dll:Contoso.Interop'
    assert dependency.name == 'Contoso.Interop'
    assert dependency.type == 'lib'
    assert dependency.namespace == 'dll'
    assert dependency.versions == ['3.2.1.0']
    assert dependency.package_files == [str(library_file.resolve())]
    assert dependency.meta == {
        'dependency_type': 'library',
        'reference_type': 'Reference',
        'library_type': 'dll',
        'include': (
            'Contoso.Interop, Version=3.2.1.0, Culture=neutral, '
            'PublicKeyToken=abcdef'
        ),
        'hint_path': 'vendor\\Contoso.Interop.dll',
        'source_project': str(project_file.resolve()),
        'assembly_identity': {
            'Version': '3.2.1.0',
            'Culture': 'neutral',
            'PublicKeyToken': 'abcdef',
        },
        'aliases': 'global,contoso',
        'copy_local': 'False',
        'specific_version': 'True',
        'resolved_path': str(library_file.resolve()),
    }


def test_external_reference_is_retained_without_nuget_lock_data(
    tmp_path, monkeypatch
):
    project_file = tmp_path / 'Example.csproj'
    project_file.write_text(
        '''<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Reference Include="native\\sqlite3.dll" />
  </ItemGroup>
</Project>
'''
    )

    scanner = NugetScanner()
    setattr(scanner, '_NugetScanner__path', project_file)
    setattr(scanner, '_NugetScanner__global_packages_dir', tmp_path / 'packages')
    monkeypatch.setattr(scanner, '_exec', lambda *args, **kwargs: None)
    monkeypatch.setattr(scanner, '_project_assets_files', lambda *args: [])

    dependencies = scanner._process_with_lock_file(project_file)

    assert [dependency.key for dependency in dependencies] == [
        'lib:dll:sqlite3'
    ]
    assert dependencies[0].meta['resolved_path'] == str(
        (tmp_path / 'native' / 'sqlite3.dll').resolve()
    )


def test_lockfile_includes_only_direct_project_references(tmp_path, monkeypatch):
    owner_dir = tmp_path / 'Owner'
    direct_dir = tmp_path / 'Direct.Project'
    transitive_dir = tmp_path / 'Transitive.Project'
    owner_dir.mkdir()
    direct_dir.mkdir()
    transitive_dir.mkdir()

    project_file = owner_dir / 'Owner.csproj'
    direct_file = direct_dir / 'Direct.Project.csproj'
    transitive_file = transitive_dir / 'Transitive.Project.csproj'
    for path in (project_file, direct_file, transitive_file):
        path.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')

    lockfile = owner_dir / 'packages.lock.json'
    lockfile.write_text(json.dumps({
        'version': 1,
        'dependencies': {
            'net8.0': {
                'Direct.Project': {'type': 'Project'},
                'Transitive.Project': {'type': 'Project'},
            },
        },
    }))

    assets_dir = owner_dir / 'obj'
    assets_dir.mkdir()
    (assets_dir / 'project.assets.json').write_text(json.dumps({
        'libraries': {
            'Direct.Project/1.0.0': {
                'type': 'project',
                'msbuildProject': '../Direct.Project/Direct.Project.csproj',
            },
            'Transitive.Project/1.0.0': {
                'type': 'project',
                'msbuildProject': '../Transitive.Project/Transitive.Project.csproj',
            },
        },
        'project': {
            'restore': {
                'projectName': 'Owner',
                'projectPath': str(project_file),
                'frameworks': {
                    'net8.0': {
                        'projectReferences': {
                            str(direct_file): {'projectPath': str(direct_file)},
                        },
                    },
                },
            },
        },
    }))

    scanner = NugetScanner()
    monkeypatch.setattr(scanner, '_process_package', lambda path: [])

    dependencies = scanner._create_deps_from_lockfile(
        lockfile, project_file=project_file, recurse_projects=False
    )

    assert [dep.name for dep in dependencies] == ['Direct.Project']
    assert dependencies[0].package_files == [str(direct_dir.resolve())]


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


def test_transitive_project_dependency_uses_nuget_assets_path(
    tmp_path, monkeypatch, capsys
):
    owner_dir = tmp_path / 'Emby.Photos'
    referenced_dir = tmp_path / 'MediaBrowser.Common'
    owner_dir.mkdir()
    referenced_dir.mkdir()

    project_file = owner_dir / 'Emby.Photos.csproj'
    project_file.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
    referenced_file = referenced_dir / 'MediaBrowser.Common.csproj'
    referenced_file.write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
        '<PackageId>Jellyfin.Common</PackageId>'
        '</PropertyGroup></Project>\n'
    )

    lockfile = owner_dir / 'packages.lock.json'
    lockfile.write_text(json.dumps({
        'version': 1,
        'dependencies': {
            'net10.0': {
                'jellyfin.common': {
                    'type': 'Project',
                },
            },
        },
    }))

    assets_dir = owner_dir / 'obj'
    assets_dir.mkdir()
    (assets_dir / 'project.assets.json').write_text(json.dumps({
        'libraries': {
            'Jellyfin.Common/12.0.0': {
                'type': 'project',
                'path': '../MediaBrowser.Common/MediaBrowser.Common.csproj',
                'msbuildProject': '../MediaBrowser.Common/MediaBrowser.Common.csproj',
            },
        },
        'project': {
            'restore': {
                'projectPath': str(project_file),
            },
        },
    }))

    scanner = NugetScanner()
    monkeypatch.setattr(scanner, '_process_package', lambda path, depth=0: [])

    dependencies = scanner._create_deps_from_lockfile(
        lockfile, project_file=project_file
    )

    assert len(dependencies) == 1
    assert dependencies[0].key == 'nuget:Jellyfin.Common'
    assert dependencies[0].package_files == [str(referenced_dir.resolve())]
    assert 'Could not find dependency location' not in capsys.readouterr().out


def test_project_reference_fallback_matches_package_id(
    tmp_path, monkeypatch, capsys
):
    owner_dir = tmp_path / 'Owner'
    referenced_dir = tmp_path / 'MediaBrowser.Controller'
    owner_dir.mkdir()
    referenced_dir.mkdir()

    project_file = owner_dir / 'Owner.csproj'
    project_file.write_text(
        '''<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <ProjectReference Include="..\\MediaBrowser.Controller\\MediaBrowser.Controller.csproj" />
  </ItemGroup>
</Project>
'''
    )
    (referenced_dir / 'MediaBrowser.Controller.csproj').write_text(
        '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><PackageId>Jellyfin.Controller</PackageId></PropertyGroup>
</Project>
'''
    )

    lockfile = owner_dir / 'packages.lock.json'
    lockfile.write_text(json.dumps({
        'version': 1,
        'dependencies': {
            'net10.0': {
                'Jellyfin.Controller': {
                    'type': 'Project',
                },
            },
        },
    }))

    # A damaged assets file must not prevent the XML fallback from working.
    assets_dir = owner_dir / 'obj'
    assets_dir.mkdir()
    (assets_dir / 'project.assets.json').write_text('{invalid json')

    scanner = NugetScanner()
    monkeypatch.setattr(scanner, '_process_package', lambda path, depth=0: [])

    dependencies = scanner._create_deps_from_lockfile(
        lockfile, project_file=project_file
    )

    assert dependencies[0].package_files == [str(referenced_dir.resolve())]
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
    monkeypatch.setattr(scanner, '_process_package', lambda path, **kwargs: [])

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
    monkeypatch.setattr(scanner, '_process_package', lambda path, depth=0, **kwargs: [])

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


def test_transitive_dependency_uses_exact_version_resolved_by_lockfile(tmp_path):
    lockfile = tmp_path / 'packages.lock.json'
    lockfile.write_text(json.dumps({
        'version': 1,
        'dependencies': {
            'net8.0': {
                'Parent.Package': {
                    'type': 'Direct',
                    'requested': '[1.0.0, )',
                    'resolved': '1.2.3',
                    'dependencies': {
                        'Child.Package': '[2.0.0, 3.0.0)',
                    },
                },
                'Child.Package': {
                    'type': 'Transitive',
                    'resolved': '2.4.1',
                },
                'Unrelated.Package': {
                    'type': 'Transitive',
                    'resolved': '9.9.9',
                },
            },
        },
    }))

    global_packages = tmp_path / 'NuGetCache'
    parent_dir = global_packages / 'parent.package' / '1.2.3'
    child_dir = global_packages / 'child.package' / '2.4.1'
    parent_dir.mkdir(parents=True)
    child_dir.mkdir(parents=True)

    parent_nuspec = '''<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
  <metadata>
    <dependencies>
      <group targetFramework="net8.0">
        <dependency id="child.package" version="[2.0.0, 3.0.0)" />
        <dependency id="Unrelated.Package" version="[9.0.0, 10.0.0)" />
      </group>
    </dependencies>
  </metadata>
</package>
'''
    child_nuspec = '''<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
  <metadata><dependencies /></metadata>
</package>
'''
    (parent_dir / 'Parent.Package.nuspec').write_text(parent_nuspec)
    (child_dir / 'Child.Package.nuspec').write_text(child_nuspec)

    scanner = NugetScanner()
    setattr(scanner, '_NugetScanner__global_packages_dir', global_packages)

    dependencies = scanner._create_deps_from_lockfile(lockfile)

    assert len(dependencies) == 1
    assert dependencies[0].key == 'nuget:Parent.Package'
    assert dependencies[0].versions == ['1.2.3']
    assert len(dependencies[0].dependencies) == 1
    child = dependencies[0].dependencies[0]
    assert child.key == 'nuget:Child.Package'
    assert child.versions == ['2.4.1']
