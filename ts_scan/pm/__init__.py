import abc
import json
import click
import typing as t
import shutil
import subprocess

from sys import platform
from pathlib import Path
from packageurl import PackageURL

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json

from ts_deepscan.scanner import Scan as DSScan
from typing_extensions import TextIO


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


@dataclass_json
@dataclass
class DependencyScan:
    module: str
    moduleId: str
    dependencies: t.List['Dependency'] = field(default_factory=lambda: [])

    tag: t.Optional[str] = None
    branch: t.Optional[str] = None

    deepscans: t.Dict[str, DSScan] = field(default_factory=lambda: {})

    def iterdeps(self) -> t.Iterable['Dependency']:
        deps = list(self.dependencies)
        while deps:
            d = deps.pop()
            deps.extend(d.dependencies)
            yield d


@dataclass_json
@dataclass
class Dependency:
    key: str
    name: str
    type: str

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

    @property
    def purl(self):
        return PackageURL(type=self.type,
                          namespace=self.namespace,
                          name=self.name,
                          version=self.versions[0] if self.versions else None)


@dataclass_json
@dataclass
class License:
    name: str
    url: str = ''


def dump_scans(scans: t.List[DependencyScan], fp: TextIO, fmt: str):
    # noinspection PyProtectedMember
    from dataclasses_json.core import _ExtendedEncoder
    if fmt == 'ts':
        scans = [s.to_dict() for s in scans]
        # noinspection PyTypeChecker
        json.dump(scans, fp, cls=_ExtendedEncoder, indent=2)
    else:
        raise NotImplemented(f'No dump/load for the "{fmt}" format')


def load_scans(fp: TextIO, fmt: str) -> t.List[DependencyScan]:
    if fmt == 'ts':
        data = json.load(fp)
        if type(data) is list:
            # noinspection PyUnresolvedReferences
            return [DependencyScan.from_dict(d) for d in data]
        else:
            # noinspection PyUnresolvedReferences
            return [DependencyScan.from_dict(data)]
    else:
        raise NotImplemented(f'No dump/load for the "{fmt}" format')
