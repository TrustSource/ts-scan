import abc
import click
import typing as t
import shutil
import subprocess

from sys import platform
from pathlib import Path
from dataclasses import dataclass, field, asdict, InitVar
from packageurl import PackageURL

from ts_deepscan.scanner import Scan as DSScan
from ts_python_client.commands.ScanCommand import Scan


class ExecutableNotFoundError(Exception):
    pass


class Scanner(abc.ABC):
    OptionsType = t.Dict[str, t.Dict[str, t.Any]]

    def __init__(self, verbose=False, ignore=False, executable: t.Optional[Path] = None,
                 forward: t.Optional[tuple] = None):
        self.verbose = verbose
        self.ignore = ignore
        self.executable_path = executable

        self.__forward = [arg for fwd in forward for arg in fwd.split(',')] if forward else []

    @staticmethod
    @abc.abstractmethod
    def name() -> str:
        raise NotImplemented()

    @staticmethod
    def executable() -> t.Optional[str]:
        return None

    @classmethod
    def options(cls) -> OptionsType:
        opts = {
            'ignore': {
                'default': False,
                'is_flag': True,
                'help': f'Ignores scanning {cls.name()} dependencies'
            }
        }

        if cls.executable():
            opts['executable'] = {
                'type': click.Path(path_type=Path),
                'required': False,
                'help': f'A path to the {cls.name()} executable'
            }
            opts['forward'] = {
                'type': str,
                'required': False,
                'multiple': True,
                'help': f'Forward parameters to the {cls.name()} executable'
            }

        return opts

    @abc.abstractmethod
    def scan(self, path: Path) -> t.Optional['DependencyScan']:
        raise NotImplemented()

    def _exec(self, *args, capture_output=False, **kwargs) -> subprocess.CompletedProcess:
        exec_path = self.executable_path if self.executable_path else self.__class__.executable()

        if cmd := shutil.which(exec_path):
            return subprocess.run(
                [cmd] + list(args) + self.__forward,
                shell=(platform == 'win32'),
                check=True,
                capture_output=capture_output or not self.verbose,
                **kwargs
            )

        else:
            raise ExecutableNotFoundError(f'An executable {exec_path} could not be found')


@dataclass
class DependencyScan(Scan):
    module: str
    moduleId: str
    dependencies: t.List['Dependency'] = field(default_factory=lambda: [])

    tag: t.Optional[str] = None
    branch: t.Optional[str] = None

    deepscans: t.Dict[str, DSScan] = field(default_factory=lambda: {})

    @staticmethod
    def from_dict(d) -> 'DependencyScan':
        from dacite import from_dict
        return from_dict(data_class=DependencyScan, data=d)

    def to_dict(self) -> dict:
        return asdict(self, dict_factory=_dataclass_dict_factory)

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

    purl_type: InitVar[str]
    purl_namespace: InitVar[t.Optional[str]] = None

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
    files: InitVar[t.List[Path]] = None
    license_file: InitVar[t.Optional[Path]] = None

    def __post_init__(self, purl_type, purl_namespace, files, license_file):
        self.purl_type = purl_type
        self.purl_namespace = purl_namespace

        self.files = files if files else []
        self.license_file = license_file

    @property
    def purl(self):
        return PackageURL(type=self.purl_type, namespace=self.purl_namespace, name=self.name)

    def to_dict(self):
        return asdict(self, dict_factory=_dataclass_dict_factory)


@dataclass
class License:
    name: str
    url: str = ''


def _dataclass_dict_factory(d):
    return {k: v for (k, v) in d if v is not None}
