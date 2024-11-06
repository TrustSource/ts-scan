import abc
import click
import typing as t
import shutil
import subprocess

from sys import platform
from pathlib import Path
from dataclasses import dataclass, field, asdict

from ts_deepscan.scanner import Scan as DSScan
from ts_python_client.commands.ScanCommand import Scan


class ExecutableNotFoundError(Exception):
    pass


class Scanner(abc.ABC):
    OptionsType = t.Dict[str, t.Dict[str, t.Any]]

    def __init__(self, verbose=False, ignore=False, executable: t.Optional[Path] = None, forward: t.Optional[tuple] = None):
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


class GenericScan(DependencyScan):
    def __init__(self, module: str, moduleId: str, deps: t.List['Dependency']):
        super().__init__()

        self.__module = module
        self.__module_id = moduleId
        self.__dependencies = deps

    @property
    def module(self) -> str:
        """returns the module name, i.e. maven artifact id"""
        return self.__module

    @property
    def moduleId(self) -> str:
        """returns the module id, i.e. maven key group_id:artifact_id"""
        return self.__module_id

    @property
    def dependencies(self) -> t.Iterable['Dependency']:
        return self.__dependencies


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
