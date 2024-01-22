import abc
import typing as t

from pathlib import Path
from dataclasses import dataclass, field, asdict

from ts_deepscan.scanner import Scan as DSScan
from ts_python_client.commands.ScanCommand import Scan


class DependencyScan(Scan, abc.ABC):
    def __init__(self):
        self.deepscans: t.Dict[str, DSScan] = {}

        self.tag: t.Optional[str] = None
        self.branch: t.Optional[str] = None

    def to_dict(self) -> dict:
        res = {
            'module': self.module,
            'moduleId': self.moduleId,
            'dependencies': [d.to_dict() for d in self.dependencies],
        }

        if self.tag:
            res['tag'] = self.tag

        if self.branch:
            res['branch'] = self.branch

        if self.deepscans:
            res['deepscans'] = {k: d.to_dict() for k, d in self.deepscans.items()}

        return res

    @property
    @abc.abstractmethod
    def module(self) -> str:
        raise NotImplemented()

    @property
    @abc.abstractmethod
    def moduleId(self) -> str:
        raise NotImplemented()

    @property
    @abc.abstractmethod
    def dependencies(self) -> t.Iterable['Dependency']:
        raise NotImplemented()

    def iterdeps(self) -> t.Iterable['Dependency']:
        deps = list(self.dependencies)
        while deps:
            d = deps.pop()
            deps.extend(d.dependencies)
            yield d


@dataclass
class Dependency:
    key: str
    name: str

    # purl components
    purl_type: str
    purl_namespace: str = ''

    repoUrl: str = ''
    homepageUrl: str = ''
    description: str = ''
    checksum: str = ''
    private: bool = False

    versions: t.List[str] = field(default_factory=lambda: [])
    dependencies: t.List['Dependency'] = field(default_factory=lambda: [])
    licenses: t.List['License'] = field(default_factory=lambda: [])

    meta: t.Dict = field(default_factory=lambda: {})

    # Excluded from serialisation
    files: t.List[Path] = field(default_factory=lambda: [])
    license_file: t.Optional[Path] = None

    @staticmethod
    def dict_factory(d):
        exclude = ('purl_type', 'purl_namespace', 'files', 'license_file')
        return {k: v for (k, v) in d if ((v is not None) and (k not in exclude))}

    def to_dict(self):
        return asdict(self, dict_factory=Dependency.dict_factory)


@dataclass
class License:
    name: str
    url: str = ''
