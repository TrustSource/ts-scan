import abc

from typing import List, Dict, Iterable
from dataclasses import dataclass, field, asdict

from ts_deepscan.scanner import Scan as DSScan
from ts_python_client.commands.ScanCommand import Scan


class DependencyScan(Scan, abc.ABC):
    def __init__(self):
        self.deepscans: Dict[str, DSScan] = {}

    def to_dict(self) -> dict:
        res = {
            'module': self.module,
            'moduleId': self.moduleId,
            'dependencies': [asdict(d) for d in self.dependencies],
        }

        if self.deepscans:
            res['deepscans'] = {k : d.to_dict() for k, d in self.deepscans.items()}

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
    def dependencies(self) -> Iterable['Dependency']:
        raise NotImplemented()

    def iterdeps(self) -> Iterable['Dependency']:
        deps = list(self.dependencies)
        while deps:
            d = deps.pop()
            deps.extend(d.dependencies)
            yield d


@dataclass
class Dependency:
    key: str
    name: str

    repoUrl: str = ''
    homepageUrl: str = ''
    description: str = ''
    checksum: str = ''
    private: bool = False

    versions: List[str] = field(default_factory=lambda: [])
    dependencies: List['Dependency'] = field(default_factory=lambda: [])
    licenses: List['License'] = field(default_factory=lambda: [])

    meta: Dict = field(default_factory=lambda: {})

    def __post_init__(self):
        self.__files = []

    @property
    def files(self):
        return self.__files


@dataclass
class License:
    name: str
    url: str = ''


