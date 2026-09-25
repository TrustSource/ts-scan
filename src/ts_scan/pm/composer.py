import json
import re
import typing as t

from pathlib import Path

import requests

from . import (Dependency,
               DependencyScan,
               ExecutableNotFoundError,
               License,
               PackageFileNotFoundError,
               PackageManagerScanner)

from ..cli import msg

PHP_LICENSE = ('PHP-3.01', 'https://www.php.net/license/3_01.txt')
PHP_HOMEPAGE_URL = 'https://www.php.net/'
PHP_REPO_URL = 'https://github.com/php/php-src'

COMPOSER_HOMEPAGE_URL = 'https://getcomposer.org/'
COMPOSER_REPO_URL = 'https://github.com/composer/composer'

_PHP_RUNTIME_RE = re.compile(r'^php(?:-(?:64bit|ipv6|zts|debug))?$', re.IGNORECASE)
_HHVM_RE = re.compile(r'^hhvm$', re.IGNORECASE)
_COMPOSER_API_RE = re.compile(r'^composer(?:-(?:plugin|runtime)-api)?$', re.IGNORECASE)
_EXTENSION_RE = re.compile(r'^ext-(.+)$', re.IGNORECASE)
_LIBRARY_RE = re.compile(r'^lib-(.+)$', re.IGNORECASE)


def is_platform_package(name: str) -> bool:
    """Whether a requirement refers to the runtime platform instead of a Packagist package."""
    return bool(_PHP_RUNTIME_RE.match(name)
                or _HHVM_RE.match(name)
                or _COMPOSER_API_RE.match(name)
                or _EXTENSION_RE.match(name)
                or _LIBRARY_RE.match(name))


def platform_metadata(name: str) -> t.Dict[str, t.Any]:
    """Licenses and URLs for platform packages, which carry no metadata of their own."""
    if _PHP_RUNTIME_RE.match(name):
        return {
            'licenses': [License(name=PHP_LICENSE[0], url=PHP_LICENSE[1])],
            'homepageUrl': PHP_HOMEPAGE_URL,
            'repoUrl': PHP_REPO_URL
        }

    if _HHVM_RE.match(name):
        return {
            'licenses': [License(name=PHP_LICENSE[0], url=PHP_LICENSE[1])],
            'homepageUrl': 'https://hhvm.com/',
            'repoUrl': 'https://github.com/facebook/hhvm'
        }

    if _COMPOSER_API_RE.match(name):
        return {
            'licenses': [License(name='MIT')],
            'homepageUrl': COMPOSER_HOMEPAGE_URL,
            'repoUrl': COMPOSER_REPO_URL
        }

    if extension := _EXTENSION_RE.match(name):
        return {
            'licenses': [License(name=PHP_LICENSE[0], url=PHP_LICENSE[1])],
            'homepageUrl': f'https://www.php.net/manual/en/book.{extension.group(1).lower()}.php',
            'repoUrl': f'{PHP_REPO_URL}/tree/master/ext/{extension.group(1).lower()}'
        }

    return {}


def normalize_version(version: str) -> str:
    """Strip Composer's optional 'v' prefix so versions match the registry's own notation."""
    if len(version) > 1 and version[0] in 'vV' and version[1].isdigit():
        return version[1:]
    return version


class ComposerScanner(PackageManagerScanner):
    """Scan PHP projects by resolving the dependency graph stored in composer.lock."""

    def __init__(self,
                 includeDevDependencies: bool = False,
                 includePlatformPackages: bool = False,
                 enableMetadataRetrieval: bool = False,
                 **kwargs):

        super().__init__(**kwargs)

        self.includeDevDependencies = includeDevDependencies
        self.includePlatformPackages = includePlatformPackages
        self.enableMetadataRetrieval = enableMetadataRetrieval

        self.__vendor_path: t.Optional[Path] = None
        self.__packages: t.Dict[str, dict] = {}
        self.__provided_by: t.Dict[str, str] = {}
        self.__cache: t.Dict[str, 'ComposerDependency'] = {}
        self.__missing: t.Set[str] = set()

    @staticmethod
    def name() -> str:
        return "Composer"

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'composer'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'includeDevDependencies': {
                'default': False,
                'is_flag': True,
                'help': 'Include Composer development dependencies in the scan results'
            },
            'includePlatformPackages': {
                'default': False,
                'is_flag': True,
                'help': 'Include platform requirements (php, ext-*, lib-*, composer-*) in the scan results'
            },
            'enableMetadataRetrieval': {
                'default': False,
                'is_flag': True,
                'help': 'Enable retrieving package metadata from the Packagist online registry'
            }
        }

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and (path / 'composer.json').exists()

    def scan(self, src: t.Union[str, Path]) -> t.Iterable[DependencyScan]:
        path = Path(src)

        manifest_path = path / 'composer.json'
        if not manifest_path.exists():
            raise PackageFileNotFoundError()

        manifest = self._load_json(manifest_path)
        if manifest is None:
            return []

        self.__vendor_path = path / manifest.get('config', {}).get('vendor-dir', 'vendor')

        lock_path = path / 'composer.lock'

        if not lock_path.exists() and not self._create_lockfile(lock_path, path):
            return [self._scan_from_manifest(path, manifest)]

        lock = self._load_json(lock_path)
        if lock is None:
            return [self._scan_from_manifest(path, manifest)]

        return [self._scan_from_lockfile(path, manifest, lock)]

    def _create_lockfile(self, lock_path: Path, path: Path) -> bool:
        args = ['update', '--no-install', '--no-scripts', '--no-interaction']

        try:
            return self._exec_to_generate_lockfile(lock_path, *args, cwd=path)
        except ExecutableNotFoundError:
            msg.warn('Cannot find the composer executable. '
                     'Continuing with the dependencies declared in composer.json.')
            return False

    @staticmethod
    def _load_json(path: Path) -> t.Optional[dict]:
        try:
            with path.open(encoding='utf-8') as fp:
                return json.load(fp)
        except (OSError, json.JSONDecodeError) as err:
            msg.warn(f'Cannot read {path.name}: {err}')
            return None

    def _scan_from_lockfile(self, path: Path, manifest: dict, lock: dict) -> DependencyScan:
        self.__packages = {}
        self.__provided_by = {}
        self.__cache = {}
        self.__missing = set()

        for pkg in lock.get('packages', []):
            if name := pkg.get('name'):
                self.__packages[name.lower()] = pkg

        dev_packages = {}
        for pkg in lock.get('packages-dev', []):
            if name := pkg.get('name'):
                dev_packages[name.lower()] = pkg

        if self.includeDevDependencies:
            self.__packages.update(dev_packages)

        # 'replace' and 'provide' let a package stand in for requirements
        # that are never locked under their own name (e.g. psr/log-implementation)
        for name, pkg in self.__packages.items():
            for relation in ('replace', 'provide'):
                for provided in pkg.get(relation, {}):
                    self.__provided_by.setdefault(provided.lower(), name)

        root = self._create_root(path, manifest)

        requirements = dict(manifest.get('require', {}))
        if self.includeDevDependencies:
            requirements.update(manifest.get('require-dev', {}))

        if requirements:
            for name, constraint in requirements.items():
                if dep := self._create_dependency(name, constraint, set()):
                    _add_dependency(root, dep)
        else:
            # An application without declared requirements still ships everything
            # the lockfile resolved, so attach the locked packages directly.
            for name in self.__packages:
                if dep := self._create_dependency(name, None, set()):
                    _add_dependency(root, dep)

        if self.__missing:
            msg.warn(f'Requirements not found in composer.lock: {", ".join(sorted(self.__missing))}')

        return _scan_from_root(root)

    def _scan_from_manifest(self, path: Path, manifest: dict) -> DependencyScan:
        self.__cache = {}

        root = self._create_root(path, manifest)

        requirements = dict(manifest.get('require', {}))
        if self.includeDevDependencies:
            requirements.update(manifest.get('require-dev', {}))

        for name, constraint in requirements.items():
            if is_platform_package(name):
                if platform_dep := self._create_platform_dependency(name, constraint):
                    _add_dependency(root, platform_dep)
                continue

            dep = ComposerDependency(name)
            dep.meta['constraint'] = constraint
            dep.meta['resolved'] = False

            self._load_installed_package(dep)

            if self.enableMetadataRetrieval:
                dep.load_from_registry()

            _add_dependency(root, dep)

        return _scan_from_root(root)

    def _create_root(self, path: Path, manifest: dict) -> 'ComposerDependency':
        root = ComposerDependency(manifest.get('name') or path.name)

        if version := manifest.get('version'):
            root.versions.append(normalize_version(str(version)))

        root.description = manifest.get('description', '')
        root.homepageUrl = manifest.get('homepage', '')

        for lic in _as_list(manifest.get('license')):
            root.licenses.append(License(name=lic))

        root.package_files.append(str(path.resolve()))

        return root

    def _create_dependency(self,
                           name: str,
                           constraint: t.Optional[str],
                           ancestors: t.Set[str]) -> t.Optional['ComposerDependency']:

        key = name.lower()

        if is_platform_package(key):
            return self._create_platform_dependency(name, constraint)

        pkg = self.__packages.get(key)

        if pkg is None and (provider := self.__provided_by.get(key)):
            pkg = self.__packages.get(provider)
            key = provider

        if pkg is None:
            self.__missing.add(name)
            return None

        if cached := self.__cache.get(key):
            return cached

        dep = ComposerDependency(pkg.get('name', name))
        dep.load_from_lock(pkg)

        if constraint:
            dep.meta['constraint'] = constraint

        self.__cache[key] = dep

        self._load_installed_package(dep)

        if self.enableMetadataRetrieval and not dep.licenses:
            dep.load_from_registry()

        for req_name, req_constraint in pkg.get('require', {}).items():
            if req_name.lower() in ancestors:
                continue

            if child := self._create_dependency(req_name, req_constraint, ancestors | {key}):
                _add_dependency(dep, child)

        return dep

    def _create_platform_dependency(self,
                                    name: str,
                                    constraint: t.Optional[str]) -> t.Optional['ComposerDependency']:
        if not self.includePlatformPackages:
            return None

        key = name.lower()

        if cached := self.__cache.get(key):
            return cached

        dep = ComposerDependency(key)

        for attr, value in platform_metadata(key).items():
            setattr(dep, attr, value)

        dep.meta['platform'] = True

        if constraint:
            dep.meta['constraint'] = constraint

            # An exact requirement such as '8.2.10' is also the resolved version
            if re.fullmatch(r'\d+(?:\.\d+){0,3}', constraint):
                dep.versions.append(constraint)

        self.__cache[key] = dep

        return dep

    def _load_installed_package(self, dep: 'ComposerDependency'):
        if self.__vendor_path is None:
            return

        pkg_path = self.__vendor_path / dep.full_name
        if pkg_path.is_dir():
            dep.package_files.append(str(pkg_path.resolve()))


class ComposerDependency(Dependency):
    def __init__(self, name: str):
        vendor, _, package = name.partition('/')

        super().__init__(key=f'composer:{name}',
                         name=package if package else vendor,
                         namespace=vendor if package else '',
                         type='composer')

    @property
    def full_name(self) -> str:
        return f'{self.namespace}/{self.name}' if self.namespace else self.name

    def load_from_lock(self, pkg: dict):
        if version := pkg.get('version'):
            normalized = normalize_version(str(version))
            self.versions.append(normalized)

            if normalized != version:
                self.meta['lockVersion'] = version

        self.description = pkg.get('description', '')
        self.homepageUrl = pkg.get('homepage', '')

        for lic in _as_list(pkg.get('license')):
            self.licenses.append(License(name=lic))

        if source := pkg.get('source'):
            self.repoUrl = source.get('url', '')

            if reference := source.get('reference'):
                self.meta['reference'] = reference

        if dist := pkg.get('dist'):
            if shasum := dist.get('shasum'):
                self.checksum = shasum

            if not self.repoUrl:
                self.repoUrl = dist.get('url', '')

        if pkg_type := pkg.get('type'):
            self.meta['packageType'] = pkg_type

        if (abandoned := pkg.get('abandoned')) not in (None, False):
            self.meta['abandoned'] = abandoned
            replacement = f", use '{abandoned}' instead" if isinstance(abandoned, str) else ''
            msg.warn(f'{self.full_name}: package is abandoned{replacement}.')

    def load_from_registry(self):
        """Fill in metadata from Packagist for packages resolved without a lockfile entry."""
        if not self.namespace:
            return

        url = f'https://repo.packagist.org/p2/{self.full_name}.json'

        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            releases = resp.json().get('packages', {}).get(self.full_name, [])
        except (requests.RequestException, ValueError):
            return

        if not releases:
            return

        release = releases[0]

        if version := self.version:
            release = next((r for r in releases
                            if normalize_version(str(r.get('version', ''))) == version), release)
        elif version := release.get('version'):
            self.versions.append(normalize_version(str(version)))

        if not self.description:
            self.description = release.get('description', '')

        if not self.homepageUrl:
            self.homepageUrl = release.get('homepage', '') or ''

        if not self.repoUrl and (source := release.get('source')):
            self.repoUrl = source.get('url', '')

        if not self.licenses:
            for lic in _as_list(release.get('license')):
                self.licenses.append(License(name=lic))


def _scan_from_root(root: 'ComposerDependency') -> DependencyScan:
    # The module keeps the fully qualified 'vendor/package' name, the version is
    # deliberately left out of the module id so that mutes survive version bumps.
    return DependencyScan(module=root.full_name, moduleId=root.key, dependencies=[root])


def _add_dependency(parent: Dependency, dep: Dependency):
    """Attach a dependency once, even if several requirements resolve to it."""
    if not any(existing.key == dep.key for existing in parent.dependencies):
        parent.dependencies.append(dep)


def _as_list(value: t.Union[str, t.List[str], None]) -> t.List[str]:
    if not value:
        return []
    return [value] if isinstance(value, str) else [v for v in value if v]
