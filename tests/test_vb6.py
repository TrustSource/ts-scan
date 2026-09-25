import shutil
from pathlib import Path

import ts_scan

from ts_scan.pm.vb6 import VB6Scanner


EXAMPLE = Path(__file__).parents[1] / 'examples' / 'vb6'


def test_accepts_vb6_projects_and_groups(tmp_path):
    scanner = VB6Scanner()

    assert scanner.accepts(tmp_path) is False
    project = tmp_path / 'Example.VBP'
    project.write_text('Type=Exe\nName="Example"\n')
    assert scanner.accepts(project) is True
    assert scanner.accepts(tmp_path) is True
    group = tmp_path / 'Example.VBG'
    group.write_text('VBG=VBG\nProject=Example.VBP\n')
    assert scanner.accepts(group) is True


def test_group_scan_maps_projects_and_external_libraries(tmp_path):
    example = tmp_path / 'vb6'
    shutil.copytree(EXAMPLE, example)
    scanner = VB6Scanner()

    scan = scanner.scan(example / 'LegacySuite.vbg')[0]

    assert scan.module == 'LegacySuite'
    assert scan.moduleId == 'vb:LegacySuite'
    assert [dependency.key for dependency in scan.dependencies] == [
        'vb:InventoryCore',
        'vb:InventoryApp',
    ]
    assert scan.dependencies[0].versions == ['1.2.0']
    app = scan.dependencies[1]
    assert app.versions == ['3.0.5']
    assert [dependency.key for dependency in app.dependencies] == [
        'vb:InventoryCore',
        'lib:dll:LegacyReports',
        'lib:ocx:MSCOMCTL',
        'lib:dll:user32',
        'lib:dll:MSVBVM60',
    ]

    project_reference = app.dependencies[0]
    assert project_reference.meta['dependency_type'] == 'project'
    assert project_reference.meta['reference']['guid'] == (
        '{11111111-1111-4111-8111-111111111111}'
    )

    reports = app.dependencies[1]
    assert reports.namespace == 'dll'
    assert reports.versions == ['4.0']
    assert reports.meta['references'][0]['display_name'] == 'Legacy Reports API'

    native = app.dependencies[3]
    assert native.meta['references'] == [{
        'reference_type': 'declare',
        'path': 'user32.dll',
        'source_file': str((example / 'Inventory.App' / 'NativeApi.bas').resolve()),
        'procedure': 'MessageBox',
        'procedure_type': 'function',
        'scope': 'public',
        'alias': 'MessageBoxA',
    }]


def test_existing_relative_library_is_added_to_package_files(tmp_path):
    project = tmp_path / 'Example.vbp'
    library = tmp_path / 'vendor' / 'Legacy.dll'
    library.parent.mkdir()
    library.write_bytes(b'fixture')
    project.write_text(
        'Type=Exe\n'
        'Reference=*\\G{AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}'
        '#2.5#0#vendor\\Legacy.dll#Legacy API\n'
        'Name="Example"\n'
    )

    scan = VB6Scanner().scan(project)[0]

    assert [dependency.key for dependency in scan.dependencies] == [
        'lib:dll:Legacy',
        'lib:dll:MSVBVM60',
    ]
    assert scan.dependencies[0].package_files == [str(library.resolve())]
    assert scan.dependencies[0].meta['resolved_path'] == str(library.resolve())


def test_single_project_discovers_referenced_vb6_project():
    scan = VB6Scanner().scan(
        EXAMPLE / 'Inventory.App' / 'Inventory.App.vbp'
    )[0]

    assert scan.moduleId == 'vb:InventoryApp'
    assert scan.dependencies[0].key == 'vb:InventoryCore'


def test_vb6_scanner_is_registered():
    scanner_classes = ts_scan.__get_pm_scanner_classes()

    assert VB6Scanner in scanner_classes


def test_runtime_is_added_as_implicit_dependency_for_compiled_outputs(tmp_path):
    project = tmp_path / 'Example.vbp'
    project.write_text('Type=OleDll\nName="Example"\n')

    scan = VB6Scanner().scan(project)[0]

    runtime = scan.dependencies[-1]
    assert runtime.key == 'lib:dll:MSVBVM60'
    assert runtime.versions == ['6.0']
    assert runtime.description == 'Microsoft Visual Basic 6.0 Runtime'
    assert runtime.meta['dependency_type'] == 'runtime'
    assert runtime.meta['implicit'] is True
    assert runtime.meta['catalog']['category'] == 'runtime'


def test_runtime_can_be_excluded_and_is_skipped_for_unknown_project_types(tmp_path):
    project = tmp_path / 'Example.vbp'
    project.write_text('Type=Exe\nName="Example"\n')
    assert VB6Scanner(excludeRuntime=True).scan(project)[0].dependencies == []

    project.write_text('Name="Example"\n')
    assert VB6Scanner().scan(project)[0].dependencies == []


def test_catalogue_enriches_well_known_libraries_only():
    scan = VB6Scanner().scan(
        EXAMPLE / 'Inventory.App' / 'Inventory.App.vbp'
    )[0]
    by_key = {dependency.key: dependency for dependency in scan.dependencies}

    common_controls = by_key['lib:ocx:MSCOMCTL']
    assert common_controls.description == 'Microsoft Windows Common Controls 6.0 (SP6)'
    assert common_controls.meta['catalog']['vendor'] == 'Microsoft'
    assert common_controls.meta['catalog']['category'] == 'activex-control'
    assert 'CVE-2012-0158' in common_controls.meta['catalog']['advisories']

    user32 = by_key['lib:dll:user32']
    assert user32.meta['catalog']['category'] == 'windows-system'

    legacy_reports = by_key['lib:dll:LegacyReports']
    assert legacy_reports.description == ''
    assert 'catalog' not in legacy_reports.meta


def test_vb6_options_expose_runtime_switch():
    assert 'excludeRuntime' in VB6Scanner.options()
    assert 'ignore' in VB6Scanner.options()
