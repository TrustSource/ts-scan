import json
import typing as t

from pathlib import Path

from . import Dependency, DependencyScan, PackageManagerScanner


class SwiftScanner(PackageManagerScanner):
    """
    Scans Swift Package Manager projects using `swift package show-dependencies`.

    Ported from https://github.com/TrustSource/ts-spm, which resolved the same
    dependency graph for TrustSource before ts-scan became the single scanner.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__processed_deps: t.Dict[str, Dependency] = {}

    @staticmethod
    def name() -> str:
        return "Swift"

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'swift'

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and (path / 'Package.swift').exists()

    def scan(self, src: t.Union[str, Path]) -> t.Iterable[DependencyScan]:
        path = Path(src)

        result = self._exec('package', 'show-dependencies', '--format', 'json',
                            cwd=path, capture_output=True)

        stdout = result.stdout
        if not stdout:
            return []

        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8')

        data = json.loads(stdout)

        name = data.get('name', '')
        root = Dependency(key=f'swift:{name}', name=name, type='swift')
        root.package_files.append(str(path.resolve()))
        root.dependencies = [self.__create_dep(dep) for dep in data.get('dependencies', [])]

        return [DependencyScan.from_dep(root)]

    def __create_dep(self, data: dict) -> Dependency:
        name = data.get('name', '')
        key = f'swift:{name}'

        if dep := self.__processed_deps.get(key):
            return dep

        dep = Dependency(key=key, name=name, type='swift')
        self.__processed_deps[key] = dep

        if version := data.get('version'):
            dep.versions.append(version)

        if url := data.get('url'):
            dep.repoUrl = url

        dep.dependencies = [self.__create_dep(child) for child in data.get('dependencies', [])]

        return dep
