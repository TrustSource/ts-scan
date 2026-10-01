import json
import shutil

from pathlib import Path

from ts_scan.pm import ExecutableNotFoundError
from ts_scan.pm.composer import ComposerScanner


EXAMPLE = Path(__file__).parents[1] / 'examples' / 'composer'


def _keys(dep):
    return [d.key for d in dep.dependencies]


def test_accepts_directories_containing_a_composer_manifest(tmp_path):
    scanner = ComposerScanner()

    assert scanner.accepts(tmp_path) is False

    manifest = tmp_path / 'composer.json'
    manifest.write_text('{"name": "acme/app"}')

    assert scanner.accepts(tmp_path) is True
    assert scanner.accepts(manifest) is False


def test_scan_resolves_the_locked_dependency_graph():
    scan = ComposerScanner().scan(EXAMPLE)[0]

    assert scan.module == 'acme/inventory-app'
    assert scan.moduleId == 'composer:acme/inventory-app'

    root = scan.dependencies[0]
    assert root.licenses[0].name == 'Apache-2.0'

    # 'php' and 'ext-json' are platform requirements and excluded by default,
    # 'psr/log-implementation' is provided by monolog and attached only once
    assert _keys(root) == ['composer:monolog/monolog', 'composer:acme/legacy-mailer']

    monolog = root.dependencies[0]
    assert monolog.namespace == 'monolog'
    assert monolog.name == 'monolog'
    assert monolog.versions == ['3.5.0']
    assert monolog.purl.to_string() == 'pkg:composer/monolog/monolog@3.5.0'
    assert [lic.name for lic in monolog.licenses] == ['MIT']
    assert monolog.repoUrl == 'https://github.com/Seldaek/monolog.git'
    assert monolog.meta['constraint'] == '^3.5'
    assert monolog.meta['reference'] == 'c915e2634718dbc8a4a15c61b0e62e7a44e14448'

    assert _keys(monolog) == ['composer:psr/log']
    assert monolog.dependencies[0].versions == ['3.0.0']


def test_scan_reports_abandoned_packages(capsys):
    scan = ComposerScanner().scan(EXAMPLE)[0]

    mailer = scan.dependencies[0].dependencies[1]

    assert mailer.meta['abandoned'] == 'acme/mailer'
    assert mailer.checksum == '1122334455667788990011223344556677889900'
    assert 'abandoned' in capsys.readouterr().out


def test_scan_excludes_development_dependencies_unless_requested():
    root = ComposerScanner().scan(EXAMPLE)[0].dependencies[0]
    assert 'composer:phpunit/phpunit' not in _keys(root)

    root = ComposerScanner(includeDevDependencies=True).scan(EXAMPLE)[0].dependencies[0]
    assert 'composer:phpunit/phpunit' in _keys(root)

    phpunit = next(d for d in root.dependencies if d.key == 'composer:phpunit/phpunit')
    diff = phpunit.dependencies[0]

    assert diff.key == 'composer:sebastian/diff'
    # Composer's 'v' prefix is stripped, the lockfile notation is kept in the metadata
    assert diff.versions == ['5.1.0']
    assert diff.meta['lockVersion'] == 'v5.1.0'


def test_scan_includes_platform_packages_on_demand():
    root = ComposerScanner(includePlatformPackages=True).scan(EXAMPLE)[0].dependencies[0]

    assert _keys(root)[:2] == ['composer:php', 'composer:ext-json']

    php, extension = root.dependencies[0], root.dependencies[1]

    assert php.meta == {'platform': True, 'constraint': '>=8.1'}
    assert [lic.name for lic in php.licenses] == ['PHP-3.01']
    assert php.versions == []

    assert extension.meta['platform'] is True
    assert [lic.name for lic in extension.licenses] == ['PHP-3.01']


def test_scan_records_installed_package_files(tmp_path):
    example = tmp_path / 'composer'
    shutil.copytree(EXAMPLE, example)

    vendor = example / 'vendor' / 'monolog' / 'monolog'
    vendor.mkdir(parents=True)

    root = ComposerScanner().scan(example)[0].dependencies[0]

    assert root.package_files == [str(example.resolve())]
    assert root.dependencies[0].package_files == [str(vendor.resolve())]


def test_scan_falls_back_to_the_manifest_without_a_lockfile(tmp_path, monkeypatch, capsys):
    manifest = {
        'name': 'acme/app',
        'version': 'v2.1.0',
        'require': {'php': '>=8.2', 'monolog/monolog': '^3.5'}
    }
    (tmp_path / 'composer.json').write_text(json.dumps(manifest))

    scanner = ComposerScanner()

    def executable_not_found(*args, **kwargs):
        raise ExecutableNotFoundError('Cannot find composer executable.')

    monkeypatch.setattr(scanner, '_exec', executable_not_found)

    scan = scanner.scan(tmp_path)[0]
    root = scan.dependencies[0]

    assert scan.moduleId == 'composer:acme/app'
    assert root.versions == ['2.1.0']
    assert _keys(root) == ['composer:monolog/monolog']

    monolog = root.dependencies[0]
    assert monolog.versions == []
    assert monolog.meta == {'constraint': '^3.5', 'resolved': False}

    assert 'Cannot find the composer executable' in capsys.readouterr().out


def test_scan_generates_a_lockfile_when_composer_is_available(tmp_path, monkeypatch):
    manifest = {'name': 'acme/app', 'require': {'psr/log': '^3.0'}}
    (tmp_path / 'composer.json').write_text(json.dumps(manifest))

    lockfile = {
        'packages': [{'name': 'psr/log', 'version': '3.0.0', 'license': ['MIT']}],
        'packages-dev': []
    }

    executed = []

    def write_lockfile(*args, **kwargs):
        executed.append(args)
        (tmp_path / 'composer.lock').write_text(json.dumps(lockfile))

    scanner = ComposerScanner()
    monkeypatch.setattr(scanner, '_exec', write_lockfile)

    root = scanner.scan(tmp_path)[0].dependencies[0]

    assert executed[0] == ('update', '--no-install', '--no-scripts', '--no-interaction')
    assert _keys(root) == ['composer:psr/log']
    assert root.dependencies[0].versions == ['3.0.0']


def test_scan_reports_requirements_missing_from_the_lockfile(tmp_path, capsys):
    (tmp_path / 'composer.json').write_text(
        json.dumps({'name': 'acme/app', 'require': {'acme/ghost': '^1.0'}}))
    (tmp_path / 'composer.lock').write_text(
        json.dumps({'packages': [], 'packages-dev': []}))

    root = ComposerScanner().scan(tmp_path)[0].dependencies[0]

    assert root.dependencies == []
    assert 'acme/ghost' in capsys.readouterr().out


def test_scan_attaches_locked_packages_without_declared_requirements(tmp_path):
    (tmp_path / 'composer.json').write_text(json.dumps({'name': 'acme/app'}))
    (tmp_path / 'composer.lock').write_text(json.dumps({
        'packages': [{'name': 'psr/log', 'version': '3.0.0'}],
        'packages-dev': []
    }))

    root = ComposerScanner().scan(tmp_path)[0].dependencies[0]

    assert _keys(root) == ['composer:psr/log']


def test_scan_handles_cyclic_requirements(tmp_path):
    (tmp_path / 'composer.json').write_text(
        json.dumps({'name': 'acme/app', 'require': {'acme/one': '^1.0'}}))
    (tmp_path / 'composer.lock').write_text(json.dumps({
        'packages': [
            {'name': 'acme/one', 'version': '1.0.0', 'require': {'acme/two': '^1.0'}},
            {'name': 'acme/two', 'version': '1.0.0', 'require': {'acme/one': '^1.0'}}
        ],
        'packages-dev': []
    }))

    root = ComposerScanner().scan(tmp_path)[0].dependencies[0]

    one = root.dependencies[0]
    assert one.key == 'composer:acme/one'
    assert _keys(one) == ['composer:acme/two']
    assert one.dependencies[0].dependencies == []


def test_module_name_is_taken_from_the_directory_without_a_package_name(tmp_path):
    project = tmp_path / 'inventory'
    project.mkdir()
    (project / 'composer.json').write_text(json.dumps({'require': {}}))
    (project / 'composer.lock').write_text(json.dumps({'packages': [], 'packages-dev': []}))

    scan = ComposerScanner().scan(project)[0]

    assert scan.module == 'inventory'
    assert scan.moduleId == 'composer:inventory'
