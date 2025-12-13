import json
import typing as t

from enum import Enum
from pathlib import Path
from packageurl import PackageURL

from dataclasses import dataclass, field
from dataclasses_json import config, dataclass_json
from typing_extensions import TextIO


class LicenseKind(str, Enum):
    DECLARED = 'declared'
    EFFECTIVE = 'effective'


@dataclass_json
@dataclass
class License:
    name: str
    url: str = ''
    kind: LicenseKind = LicenseKind.DECLARED


@dataclass_json
@dataclass
class CryptoAlgorithm:
    algorithm: str
    strength: str


@dataclass_json
@dataclass
class Dependency:
    name: str
    type: str

    key: str = field(default=None, metadata=config(exclude=lambda v: v is None))

    namespace: str = ''

    repoUrl: str = ''
    homepageUrl: str = ''
    description: str = ''
    checksum: str = ''
    private: bool = False

    versions: t.List[str] = field(default_factory=lambda: [])
    dependencies: t.List['Dependency'] = field(default_factory=lambda: [])
    licenses: t.List['License'] = field(default_factory=lambda: [])

    meta: t.Dict = field(default_factory=lambda: {})

    package_files: t.List[str] = field(default_factory=lambda: [])
    license_file: t.Optional[str] = None

    crypto_algorithms: t.List['CryptoAlgorithm'] = field(default_factory=lambda: [])

    def __post_init__(self):
        if self.key is None:
            self.key = f'{self.type}:{self.name}'

    @property
    def version(self) -> t.Optional[str]:
        return self.versions[0] if len(self.versions) == 1 else None

    @property
    def purl(self):
        return PackageURL(type=self.type,
                          namespace=self.namespace,
                          name=self.name,
                          version=self.version)

    @staticmethod
    def create_from_purl(purl: t.Union[str, PackageURL],
                         versions_override: t.Optional[t.List[str]] = None) -> t.Optional['Dependency']:
        if type(purl) is str:
            try:
                _purl = PackageURL.from_string(purl)
            except ValueError:
                return None
        elif isinstance(purl, PackageURL):
            _purl: PackageURL = purl
        else:
            return None
            
        key = Dependency._map_purl_type(_purl.type)
        if _purl.namespace:
            key += ':' + _purl.namespace
            ns = _purl.namespace
        else:
            ns = ''

        key += ':' + _purl.name

        versions = [_purl.version] if _purl.version else []

        if versions_override:
            versions = versions_override

        return Dependency(key=key,
                          name=_purl.name,
                          type=_purl.type,
                          namespace=ns,
                          versions=versions,
                          meta={'purl': _purl.to_string()})
    
    def add_crypto_algorithm(self, algorithm: str, strength: str):
        if next((a for a in self.crypto_algorithms if
                 a.algorithm == algorithm and a.strength == strength), None) is None:
            self.crypto_algorithms.append(CryptoAlgorithm(algorithm=algorithm, strength=strength))

    @staticmethod
    def _map_purl_type(ty: str):
        # TrustSource key mapping
        if ty == 'maven':
            return 'mvn'
        else:
            return ty


@dataclass_json
@dataclass
class DependencyScan:
    module: str
    moduleId: str
    dependencies: t.List['Dependency'] = field(default_factory=lambda: [])

    source: t.Optional[str] = field(default=None, metadata=config(exclude=lambda f: f is None))

    tag: t.Optional[str] = field(default=None, metadata=config(exclude=lambda f: f is None))
    branch: t.Optional[str] = field(default=None, metadata=config(exclude=lambda f: f is None))

    deepscans: t.Dict[str, t.Any] = field(default_factory=lambda: {})

    @staticmethod
    def from_dep(dep: 'Dependency') -> 'DependencyScan':
        module_id = dep.key
        if dep.version:
            module_id += ':' + dep.version
        return DependencyScan(module=dep.name, moduleId=module_id, dependencies=[dep])

    def iterdeps(self) -> t.Iterable['Dependency']:
        deps = list(self.dependencies)
        while deps:
            d = deps.pop()
            deps.extend(d.dependencies)
            yield d

    def iterdeps_once(self) -> t.Iterable['Dependency']:
        visited = set()
        for dep in self.iterdeps():
            if dep.purl not in visited:
                visited.add(dep.purl)
                yield dep

    def as_purls_dict(self) -> t.Dict[str, 'Dependency']:
        return {dep.purl.to_string(): dep for dep in self.iterdeps_once()}


def dump_scans(scans: t.List[DependencyScan], fp: TextIO, fmt: str):
    # noinspection PyProtectedMember
    from dataclasses_json.core import _ExtendedEncoder

    if not scans:
        return

    if fmt == 'ts':
        # noinspection PyUnresolvedReferences
        scans = [s.to_dict() for s in scans]
        # noinspection PyTypeChecker
        json.dump(scans, fp, cls=_ExtendedEncoder, indent=2)

    elif fmt in ['spdx-tag', 'spdx-json', 'spdx-yaml', 'spdx-xml']:
        from .spdx import export_scan
        export_scan(scans[0], fp, fmt)

    elif fmt in ['cyclonedx-json', 'cyclonedx-xml']:
        from .cyclonedx import export_scan
        export_scan(scans[0], fp, fmt)

    else:
        raise ValueError(f'Unsupported output format: {fmt}')


def load_scans(path: Path, fmt: str) -> t.List[DependencyScan]:
    if fmt == 'ts':
        with path.open('r') as fp:
            data = json.load(fp)
            if type(data) is list:
                # noinspection PyUnresolvedReferences
                return [DependencyScan.from_dict(d) for d in data]
            else:
                # noinspection PyUnresolvedReferences
                return [DependencyScan.from_dict(data)]

    elif fmt in ['spdx-tag', 'spdx-json', 'spdx-yaml', 'spdx-xml']:
        from .spdx import import_scan
        return [import_scan(path, fmt)]

    elif fmt in ['cyclonedx-json', 'cyclonedx-xml']:
        from .cyclonedx import import_scan
        return [import_scan(path, fmt)]

    else:
        raise ValueError(f'Unsupported input format: {fmt}')
