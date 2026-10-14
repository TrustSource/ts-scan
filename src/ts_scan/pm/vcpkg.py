"""Read vcpkg installation snapshots without invoking vcpkg or modifying its database."""
import copy
import json
import re
import typing as t
from pathlib import Path

import click
from packageurl import PackageURL

from . import Dependency, DependencyScan, License, LicenseKind, PackageManagerScanner
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
                 triplet: t.Optional[str] = None, roots: tuple = (), **kwargs):
        super().__init__(**kwargs)
        self.installed_dir = Path(installedDir).resolve() if installedDir is not None else None
        self.triplet = triplet
        self.roots = roots

    @staticmethod
    def name() -> str:
        return 'Vcpkg'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'installedDir': {
                'type': click.Path(exists=True, file_okay=False, path_type=Path),
                'help': 'vcpkg installation directory; defaults to <source>/vcpkg_installed'
            },
            'triplet': {'type': str, 'help': 'Select an installed target triplet'},
            'roots': {
                'type': str, 'multiple': True,
                'help': 'Scan the closure of an installed port[:triplet]; repeat for multiple roots'
            }
        }

    def accepts(self, path: Path) -> bool:
        if path.is_file():
            return path.name == 'vcpkg.json'
        return path.is_dir() and (self.installed_dir is not None
                                 or (path / 'vcpkg.json').is_file()
                                 or (path / 'vcpkg' / 'status').is_file()
                                 or (path / 'vcpkg' / 'updates').is_dir()
                                 or (path / 'vcpkg_installed' / 'vcpkg').is_dir())

    def scan(self, src: t.Union[str, Path]) -> t.Iterable[DependencyScan]:
        source = Path(src).resolve()
        project = source if source.is_dir() else source.parent
        installed = self.installed_dir or (
            project if (project / 'vcpkg').is_dir() else project / 'vcpkg_installed')
        try:
            if self.triplet is not None and not re.fullmatch(_NAME, self.triplet):
                raise ValueError('Invalid vcpkg triplet')
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
        except (OSError, ValueError) as err:
            msg.warn(f'Vcpkg scan incomplete: {err}. No resolved scan was produced. '
                     'Use an installation snapshot from a completed build.')
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
            expected = dep.version + (f"#{dep.meta['vcpkg']['port_version']}" if dep.meta['vcpkg']['port_version'] else '')
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
                qualifiers = purl.qualifiers or {}
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
