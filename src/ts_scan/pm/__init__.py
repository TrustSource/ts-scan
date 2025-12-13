import abc
import click
import typing as t
import shutil
import subprocess

from abc import ABC
from sys import platform
from pathlib import Path


class ExecutableNotFoundError(Exception):
    pass


class PackageFileNotFoundError(Exception):
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
        opts = {}

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
    def accepts(self, path: Path) -> bool:
        raise NotImplemented()

    @abc.abstractmethod
    def scan(self, src: t.Union[str, Path]) -> t.Optional['DependencyScan']:
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
            raise ExecutableNotFoundError(f'Cannot find {exec_path} executable.')


class PackageManagerScanner(Scanner, ABC):
    OptionsType = t.Dict[str, t.Dict[str, t.Any]]

    @classmethod
    def options(cls) -> OptionsType:
        return super().options() | {
            'ignore': {
                'default': False,
                'is_flag': True,
                'help': f'Ignores scanning {cls.name()} dependencies'
            }
        }


def get_license_from_text(text: str, as_lic_text_only=True) -> t.Optional[t.Tuple[dict, t.List[str]]]:
    import ts_deepscan.analyser.textutils
    from ..analyse import get_ds_dataset

    dataset = get_ds_dataset()

    if res := ts_deepscan.analyser.textutils.analyse_license_text(text,
                                                                  dataset=dataset,
                                                                  search_copyright=False):
        if (key := res.get('key')) and (score := res.get('score', 0)) and score >= 0.9:
            return res, [key]

    if not as_lic_text_only and (res := ts_deepscan.analyser.textutils.analyse_text(text,
                                                                                    timeout=10,
                                                                                    dataset=dataset,
                                                                                    search_copyright=False)):
        if 'licenses' in res:
            return res, res['licenses']

    return None
