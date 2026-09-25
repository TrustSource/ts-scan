import json
from subprocess import CompletedProcess

from ts_scan.pm.swift import SwiftScanner


def test_accepts_requires_package_swift(tmp_path):
    scanner = SwiftScanner()

    assert not scanner.accepts(tmp_path)

    (tmp_path / 'Package.swift').write_text('// swift-tools-version:5.9\n')

    assert scanner.accepts(tmp_path)


def test_scan_parses_dependency_tree(tmp_path, monkeypatch):
    (tmp_path / 'Package.swift').write_text('// swift-tools-version:5.9\n')

    show_dependencies = {
        'name': 'MyPackage',
        'dependencies': [
            {
                'name': 'swift-argument-parser',
                'url': 'https://github.com/apple/swift-argument-parser',
                'version': '1.2.0',
                'dependencies': [],
            },
            {
                'name': 'swift-log',
                'url': 'https://github.com/apple/swift-log',
                'version': '1.5.3',
                'dependencies': [
                    {
                        'name': 'swift-argument-parser',
                        'url': 'https://github.com/apple/swift-argument-parser',
                        'version': '1.2.0',
                        'dependencies': [],
                    }
                ],
            },
        ],
    }

    scanner = SwiftScanner()
    monkeypatch.setattr(
        scanner, '_exec',
        lambda *args, **kwargs: CompletedProcess(args, 0, stdout=json.dumps(show_dependencies).encode('utf-8'))
    )

    scans = list(scanner.scan(tmp_path))

    assert len(scans) == 1

    scan = scans[0]
    assert scan.module == 'MyPackage'
    assert scan.moduleId == 'swift:MyPackage'

    root = scan.dependencies[0]
    assert root.package_files == [str(tmp_path.resolve())]
    assert {d.name for d in root.dependencies} == {'swift-argument-parser', 'swift-log'}

    arg_parser = next(d for d in root.dependencies if d.name == 'swift-argument-parser')
    assert arg_parser.versions == ['1.2.0']
    assert arg_parser.repoUrl == 'https://github.com/apple/swift-argument-parser'
    assert arg_parser.key == 'swift:swift-argument-parser'

    log = next(d for d in root.dependencies if d.name == 'swift-log')
    assert [d.name for d in log.dependencies] == ['swift-argument-parser']

    # The transitive occurrence of swift-argument-parser under swift-log resolves
    # to the same Dependency instance as the direct one.
    assert log.dependencies[0] is arg_parser


def test_scan_returns_no_scans_on_empty_output(tmp_path, monkeypatch):
    (tmp_path / 'Package.swift').write_text('// swift-tools-version:5.9\n')

    scanner = SwiftScanner()
    monkeypatch.setattr(
        scanner, '_exec',
        lambda *args, **kwargs: CompletedProcess(args, 0, stdout=b'')
    )

    assert list(scanner.scan(tmp_path)) == []


def test_scan_resets_processed_dependencies_between_calls(tmp_path, monkeypatch):
    first = {
        'name': 'First',
        'dependencies': [
            {'name': 'shared', 'url': 'https://example.com/first', 'version': '1.0.0', 'dependencies': []}
        ],
    }
    second = {
        'name': 'Second',
        'dependencies': [
            {'name': 'shared', 'url': 'https://example.com/second', 'version': '2.0.0', 'dependencies': []}
        ],
    }

    outputs = [first, second]

    scanner = SwiftScanner()
    monkeypatch.setattr(
        scanner, '_exec',
        lambda *args, **kwargs: CompletedProcess(args, 0, stdout=json.dumps(outputs.pop(0)).encode('utf-8'))
    )

    first_scan = list(scanner.scan(tmp_path))[0]
    second_scan = list(scanner.scan(tmp_path))[0]

    first_shared = first_scan.dependencies[0].dependencies[0]
    second_shared = second_scan.dependencies[0].dependencies[0]

    assert first_shared.versions == ['1.0.0']
    assert first_shared.repoUrl == 'https://example.com/first'
    assert second_shared.versions == ['2.0.0']
    assert second_shared.repoUrl == 'https://example.com/second'
