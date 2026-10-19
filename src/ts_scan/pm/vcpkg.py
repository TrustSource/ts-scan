"""Discover vcpkg installations and resolve missing manifest dependencies."""
import copy
import json
import os
import re
import shutil
import subprocess
import typing as t
from pathlib import Path

import click
from packageurl import PackageURL, normalize_qualifiers

from . import (Dependency, DependencyScan, ExecutableNotFoundError, License,
               LicenseKind, PackageManagerScanner)
from ..cli import msg


_NAME = r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?'
_SPEC = re.compile(rf'^({_NAME})(?:\[[a-z0-9, -]+\])?(?::({_NAME}))?(?:\s+\([^)]*\))?$')
Spec = t.Tuple[str, str]


def _paragraphs(text: str) -> t.List[t.Dict[str, str]]:
    """Parse vcpkg's control-file paragraphs, including continuation lines."""
    result: t.List[t.Dict[str, str]] = []
    fields: t.Dict[str, str] = {}
    last = None
    for line in text.splitlines() + ['']:
        if not line.strip():
            if fields:
                result.append(fields)
            fields, last = {}, None
        elif line.startswith('#'):
            continue
        elif line[0].isspace():
            if last is None:
                raise ValueError('Orphaned status continuation line')
            fields[last] += '\n' + line.strip()
        else:
            key, separator, value = line.partition(':')
            if not separator or not re.fullmatch(r'[A-Za-z0-9-]+', key) or key in fields:
                raise ValueError('Invalid or duplicate status field')
            fields[key], last = value.strip(), key
    return result


def _spec(value: str, default_triplet: t.Optional[str]) -> Spec:
    match = _SPEC.fullmatch(value.strip())
    if match is None:
        raise ValueError(f'Invalid vcpkg package specification: {value}')
    triplet = match[2] or default_triplet
    if triplet is None:
        raise ValueError(f'Specify --vcpkg:triplet or qualify root {value} with :triplet')
    return match[1], triplet


def _dependency_specs(value: str, triplet: str) -> t.Set[Spec]:
    # Older records can contain feature lists with commas inside brackets.
    specs: t.Set[Spec] = set()
    start = depth = 0
    for index, char in enumerate(value + ','):
        if char in '[(':
            depth += 1
        elif char in '])':
            depth -= 1
        elif char == ',' and depth == 0:
            token = value[start:index].strip()
            if token:
                specs.add(_spec(token, triplet))
            start = index + 1
        if depth < 0:
            raise ValueError('Invalid vcpkg dependency list')
    if depth:
        raise ValueError('Unbalanced vcpkg dependency list')
    return specs


class VcpkgScanner(PackageManagerScanner):
    def __init__(self, installedDir: t.Optional[Path] = None,
                 triplet: t.Optional[str] = None, roots: tuple = (),
                 noInstall: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.installed_dir = Path(installedDir).resolve() if installedDir is not None else None
        self.triplet = triplet
        self.roots = roots
        self.no_install = noInstall

    @staticmethod
    def name() -> str:
        return 'Vcpkg'

    @staticmethod
    def executable() -> str:
        return 'vcpkg'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'installedDir': {
                'type': click.Path(exists=True, file_okay=False, path_type=Path),
                'help': 'Read an existing vcpkg installation directory instead of automatic discovery/resolution'
            },
            'triplet': {'type': str, 'help': 'Select an installed target triplet'},
            'roots': {
                'type': str, 'multiple': True,
                'help': 'Scan the closure of an installed port[:triplet]; repeat for multiple roots'
            },
            'noInstall': {
                'default': False, 'is_flag': True,
                'help': 'Only discover existing package data; do not install missing manifest dependencies'
            },
        }

    @staticmethod
    def _has_database(path: Path) -> bool:
        updates = path / 'vcpkg' / 'updates'
        return (path / 'vcpkg' / 'status').is_file() or (
            updates.is_dir() and any(p.is_file() and p.name != 'incomplete' for p in updates.iterdir()))

    @staticmethod
    def _cmake_caches(project: Path) -> t.List[Path]:
        caches = {project / 'CMakeCache.txt', project / 'build' / 'CMakeCache.txt'}
        for pattern in ('build*/CMakeCache.txt', 'build/*/CMakeCache.txt',
                        'cmake-build*/CMakeCache.txt', 'out/build/*/CMakeCache.txt'):
            caches.update(project.glob(pattern))
        return sorted(path for path in caches if path.is_file())

    @staticmethod
    def _cache_values(path: Path) -> t.Dict[str, str]:
        values = {}
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith(('#', '//')):
                continue
            key, separator, value = line.partition('=')
            if separator:
                values[key.split(':', 1)[0]] = value
        return values

    def _find_root(self, project: Path, caches: t.List[Path]) -> t.Optional[Path]:
        if os.environ.get('VCPKG_ROOT'):
            return Path(os.environ['VCPKG_ROOT']).expanduser().resolve()
        candidates = []
        for cache in caches:
            toolchain = self._cache_values(cache).get('CMAKE_TOOLCHAIN_FILE')
            if toolchain:
                path = Path(toolchain)
                path = path if path.is_absolute() else cache.parent / path
                if path.name == 'vcpkg.cmake' and len(path.parents) >= 3:
                    candidates.append(path.resolve().parents[2])
        executable = shutil.which(str(self.executable_path or self.executable()))
        if executable:
            candidates.extend(Path(executable).resolve().parents)
        candidates.extend(parent / 'vcpkg' for parent in (project, *project.parents))
        candidates.extend((Path.home() / 'vcpkg', Path.home() / 'src' / 'vcpkg',
                           Path.home() / '.vcpkg'))
        return next((path for path in candidates if (path / '.vcpkg-root').is_file()), None)

    def _find_installation(self, project: Path) -> Path:
        if self.installed_dir is not None:
            return self.installed_dir
        configured = os.environ.get('VCPKG_INSTALLED_DIR')
        if configured:
            return Path(configured).expanduser().resolve()
        for path in (project, project / 'vcpkg_installed', project / 'installed'):
            if self._has_database(path):
                return path
        caches = self._cmake_caches(project)
        builds = set()
        for cache in caches:
            values = self._cache_values(cache)
            if self.triplet and values.get('VCPKG_TARGET_TRIPLET', self.triplet) != self.triplet:
                continue
            path = Path(values.get('VCPKG_INSTALLED_DIR', str(cache.parent / 'vcpkg_installed')))
            path = path if path.is_absolute() else cache.parent / path
            if self._has_database(path):
                builds.add(path.resolve())
        # Standard CMake build folders can have package data even without a cache.
        for pattern in ('build/vcpkg_installed', 'build*/vcpkg_installed',
                        'build/*/vcpkg_installed', 'cmake-build*/vcpkg_installed',
                        'out/build/*/vcpkg_installed'):
            for path in project.glob(pattern):
                if self._has_database(path) and (not self.triplet or (path / self.triplet).is_dir()):
                    builds.add(path.resolve())
        if len(builds) > 1:
            raise ValueError('Multiple vcpkg build installations found; select one with --vcpkg:installedDir')
        if builds:
            return next(iter(builds))
        # A manifest owns its installation. Do not substitute a shared classic
        # inventory for that project's dependencies.
        if not (project / 'vcpkg.json').is_file():
            root = self._find_root(project, caches)
            if root is not None and self._has_database(root / 'installed'):
                return root / 'installed'
        return project / 'vcpkg_installed'

    def _install_manifest(self, project: Path, installed: Path) -> None:
        args = ['install', '--x-manifest-root=' + str(project),
                '--x-install-root=' + str(installed), '--disable-metrics']
        if self.triplet:
            args.append('--triplet=' + self.triplet)
        root = self._find_root(project, self._cmake_caches(project))
        if root is not None:
            args.append('--vcpkg-root=' + str(root))
        msg.info('Resolving and installing vcpkg manifest dependencies...')
        executable = root / ('vcpkg.exe' if os.name == 'nt' else 'vcpkg') if root else None
        if executable is not None and executable.is_file():
            self._exec(*args, cwd=project, capture_output=True, executable_override=str(executable))
        else:
            self._exec(*args, cwd=project, capture_output=True)

    def accepts(self, path: Path) -> bool:
        if path.is_file():
            return path.name == 'vcpkg.json'
        if not path.is_dir():
            return False
        if (self.installed_dir is not None
                or (path / 'vcpkg.json').is_file()
                or (path / 'vcpkg' / 'status').is_file()
                or (path / 'vcpkg' / 'updates').is_dir()
                or (path / 'vcpkg_installed' / 'vcpkg').is_dir()
                or (path / 'installed' / 'vcpkg').is_dir()):
            return True
        for cache in self._cmake_caches(path):
            values = self._cache_values(cache)
            if 'VCPKG_INSTALLED_DIR' in values or 'vcpkg.cmake' in values.get('CMAKE_TOOLCHAIN_FILE', ''):
                return True
        return any(self._has_database(candidate) for pattern in (
            'build*/vcpkg_installed', 'build/*/vcpkg_installed',
            'cmake-build*/vcpkg_installed', 'out/build/*/vcpkg_installed')
                   for candidate in path.glob(pattern))

    def scan(self, src: t.Union[str, Path]) -> t.Iterable[DependencyScan]:
        source = Path(src).resolve()
        project = source if source.is_dir() else source.parent
        try:
            if self.triplet is not None and not re.fullmatch(_NAME, self.triplet):
                raise ValueError('Invalid vcpkg triplet')
            installed = self._find_installation(project)
            if (not self._has_database(installed) and self.installed_dir is None
                    and not self.no_install and (project / 'vcpkg.json').is_file()):
                self._install_manifest(project, installed)
            records = self._database(installed)
            packages, edges = self._packages(records)
            selected = sorted(spec for spec in packages if self.triplet is None or spec[1] == self.triplet)
            if self.triplet is not None and not selected:
                raise ValueError(f'No installed packages found for triplet {self.triplet}')
            if self.roots:
                selected = list(dict.fromkeys(_spec(value, self.triplet) for value in self.roots))
                for spec in selected:
                    if spec not in packages:
                        raise ValueError(f'Root {spec[0]}:{spec[1]} is not installed')
                    if self.triplet is not None and spec[1] != self.triplet:
                        raise ValueError('Root triplet conflicts with --vcpkg:triplet')
            manifest = project / 'vcpkg.json'
            data = json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
            if not isinstance(data, dict):
                raise ValueError('Invalid vcpkg project manifest')
            name = data.get('name') or project.name
            if not isinstance(name, str):
                raise ValueError('Invalid project name')
            scope = 'roots' if self.roots else 'inventory'
            module_id = f'vcpkg:{name}:{scope}' + (f':{self.triplet}' if self.triplet else '')
            root = Dependency(name=name, type='generic', key=module_id)
            root.package_files = [str(project)]
            root.meta['vcpkg'] = {
                'scope': scope, 'installed_dir': str(installed),
                'triplet': self.triplet, 'roots': [f'{n}:{tr}' for n, tr in selected],
                'manifest': data, 'warnings': []
            }
            warnings: t.List[str] = root.meta['vcpkg']['warnings']
            enriched: t.Dict[Spec, Dependency] = {}

            def warn(message: str):
                if message not in warnings:
                    warnings.append(message)
                    msg.warn(message)

            def build(spec: Spec, ancestors: t.Set[Spec]) -> Dependency:
                if spec not in enriched:
                    enriched[spec] = copy.deepcopy(packages[spec])
                    self._enrich(enriched[spec], installed, spec, warn)
                dep = copy.deepcopy(enriched[spec])
                for child in sorted(edges[spec]):
                    if child not in packages:
                        raise ValueError(f'Missing installed dependency {child[0]}:{child[1]}')
                    if child in ancestors:
                        warn(f'vcpkg dependency cycle at {child[0]}:{child[1]}; cyclic edge omitted')
                        continue
                    dep.dependencies.append(build(child, ancestors | {child}))
                return dep

            root.dependencies = [build(spec, {spec}) for spec in selected]
            root.meta['vcpkg']['metadata_complete'] = not warnings
            if scope == 'inventory':
                msg.info('Scanning a vcpkg installed-package inventory; project usage is not inferred.')
            return [DependencyScan.from_dep(root)]
        except (OSError, ValueError, ExecutableNotFoundError, subprocess.CalledProcessError) as err:
            detail = str(err)
            if isinstance(err, subprocess.CalledProcessError):
                output = err.stderr or err.stdout
                if output:
                    detail = output.decode('utf-8', errors='replace') if isinstance(output, bytes) else output
            msg.warn(f'Vcpkg scan incomplete: {detail}. No resolved scan was produced.')
            return []

    @staticmethod
    def _database(installed: Path) -> t.Dict[t.Tuple[str, str, str], t.Dict[str, str]]:
        status = installed / 'vcpkg' / 'status'
        updates = installed / 'vcpkg' / 'updates'
        files = ([status] if status.is_file() else [])
        if updates.is_dir():
            files.extend(sorted(path for path in updates.iterdir()
                                if path.is_file() and path.name != 'incomplete'))
        if not files:
            raise ValueError(f'No vcpkg status database or completed updates found in {installed}')
        records = {}
        for path in files:
            for fields in _paragraphs(path.read_text(encoding='utf-8')):
                name, triplet = fields.get('Package', ''), fields.get('Architecture', '')
                if not re.fullmatch(_NAME, name) or not re.fullmatch(_NAME, triplet):
                    raise ValueError(f'Invalid package/triplet in {path}')
                state = fields.get('Status', '').split()
                if (len(state) != 3 or state[0] not in ('install', 'hold', 'deinstall', 'purge')
                        or state[1] != 'ok' or state[2] not in ('installed', 'not-installed', 'half-installed')):
                    raise ValueError(f'Invalid Status field in {path}')
                feature = fields.get('Feature', '')
                if feature and not re.fullmatch(_NAME, feature):
                    raise ValueError(f'Invalid Feature field in {path}')
                records[name, triplet, '' if feature == 'core' else feature] = fields
        return records

    @staticmethod
    def _packages(records: t.Dict[t.Tuple[str, str, str], t.Dict[str, str]]):
        groups: t.Dict[Spec, t.List[t.Dict[str, str]]] = {}
        for (name, triplet, _), fields in records.items():
            if fields['Status'].split() == ['install', 'ok', 'installed']:
                groups.setdefault((name, triplet), []).append(fields)
        packages: t.Dict[Spec, Dependency] = {}
        edges: t.Dict[Spec, t.Set[Spec]] = {}
        for spec, group in groups.items():
            core = next((fields for fields in group if fields.get('Feature', '') in ('', 'core')), None)
            if core is None or not core.get('Version'):
                raise ValueError(f'Missing installed core/version for {spec[0]}:{spec[1]}')
            port_version = core.get('Port-Version', '0')
            if not port_version.isdigit():
                raise ValueError('Invalid vcpkg Port-Version')
            features = sorted(fields['Feature'] for fields in group if fields.get('Feature') not in (None, '', 'core'))
            qualifiers = {'triplet': spec[1]}
            if int(port_version):
                qualifiers['port_version'] = str(int(port_version))
            if features:
                qualifiers['features'] = ','.join(features)
            dep = Dependency.create_from_purl(PackageURL(type='vcpkg', name=spec[0],
                                                        version=core['Version'], qualifiers=qualifiers))
            if dep is None:
                raise ValueError('Invalid vcpkg package identity')
            dep.description = core.get('Description', '')
            dep.meta['vcpkg'] = {'triplet': spec[1], 'features': features,
                                 'port_version': int(port_version), 'abi': core.get('Abi', '')}
            packages[spec] = dep
            edges[spec] = set().union(*(_dependency_specs(fields.get('Depends', ''), spec[1]) for fields in group))
            edges[spec].discard(spec)
        return packages, edges

    @staticmethod
    def _enrich(dep: Dependency, installed: Path, spec: Spec, warn: t.Callable[[str], None]):
        share = installed / spec[1] / 'share' / spec[0]
        path = share / 'vcpkg.spdx.json'
        dep.meta['vcpkg']['copyright_file'] = str(share / 'copyright') if (share / 'copyright').is_file() else None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not isinstance(data.get('packages'), list):
                raise ValueError('Invalid SPDX packages')
            ports = [pkg for pkg in data['packages'] if isinstance(pkg, dict) and pkg.get('SPDXID') == 'SPDXRef-port']
            if len(ports) != 1 or ports[0].get('name') != dep.name:
                raise ValueError('Missing or mismatched SPDX port record')
            port = ports[0]
            version = dep.version
            if version is None:
                raise ValueError('Missing installed package version')
            expected = version + (f"#{dep.meta['vcpkg']['port_version']}" if dep.meta['vcpkg']['port_version'] else '')
            if port.get('versionInfo') != expected:
                raise ValueError('SPDX port version does not match installed database')
            refs = port.get('externalRefs', [])
            if not isinstance(refs, list):
                raise ValueError('Invalid SPDX external references')
            purls = [PackageURL.from_string(ref['referenceLocator']) for ref in refs
                     if isinstance(ref, dict) and ref.get('referenceType') == 'purl']
            if len(purls) > 1:
                raise ValueError('Ambiguous SPDX port PURL')
            if purls:
                purl = purls[0]
                qualifiers = normalize_qualifiers(purl.qualifiers, encode=None) or {}
                if (purl.type != 'vcpkg' or purl.namespace or purl.name != dep.name
                        or purl.version != dep.version
                        or int(qualifiers.get('port_version', '0')) != dep.meta['vcpkg']['port_version']
                        or qualifiers.get('triplet', spec[1]) != spec[1]):
                    raise ValueError('SPDX port PURL does not match installed database')
                dep.qualifiers.update(qualifiers)
                # The database is authoritative for installed features and target triplet.
                dep.qualifiers['triplet'] = spec[1]
                if dep.meta['vcpkg']['features']:
                    dep.qualifiers['features'] = ','.join(dep.meta['vcpkg']['features'])
                else:
                    dep.qualifiers.pop('features', None)
                identity = Dependency.create_from_purl(dep.purl)
                if identity is not None:
                    dep.key = identity.key
            else:
                warn(f'vcpkg metadata incomplete for {dep.name}:{spec[1]}: SPDX port has no PURL')
            dep.homepageUrl = port.get('homepage') or ''
            dep.description = port.get('description') or port.get('summary') or dep.description
            license_text = port.get('licenseConcluded')
            kind = LicenseKind.EFFECTIVE
            if not license_text or license_text in ('NONE', 'NOASSERTION'):
                license_text, kind = port.get('licenseDeclared'), LicenseKind.DECLARED
            if isinstance(license_text, str) and license_text not in ('', 'NONE', 'NOASSERTION'):
                dep.licenses = [License(name=license_text, kind=kind)]
            dep.meta['vcpkg']['spdx_file'] = str(path)
            dep.meta['vcpkg']['port_download_location'] = port.get('downloadLocation')
            dep.meta['vcpkg']['external_refs'] = refs
            dep.meta['vcpkg']['sources'] = [pkg for pkg in data['packages']
                                           if isinstance(pkg, dict) and str(pkg.get('SPDXID', '')).startswith('SPDXRef-resource')]
        except (OSError, ValueError, KeyError, TypeError) as err:
            warn(f'vcpkg metadata incomplete for {dep.name}:{spec[1]}: {err}')
