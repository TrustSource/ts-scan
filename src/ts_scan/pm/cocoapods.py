import re
import typing as t
import yaml

from pathlib import Path

from . import Dependency, DependencyScan, PackageManagerScanner


class CocoaPodsScanner(PackageManagerScanner):
    """
    Scans CocoaPods projects using the resolved `Podfile.lock`.

    The lockfile already contains the fully resolved dependency graph
    (PODS section) together with checksums (SPEC CHECKSUMS), so no `pod`
    executable needs to be invoked.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__processed_deps: t.Dict[str, Dependency] = {}

    @staticmethod
    def name() -> str:
        return "CocoaPods"

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and (path / 'Podfile.lock').exists()

    def scan(self, src: t.Union[str, Path]) -> t.Iterable[DependencyScan]:
        path = Path(src)
        lockfile_path = path / 'Podfile.lock'

        with lockfile_path.open() as fp:
            lockfile = yaml.safe_load(fp)

        if not lockfile:
            return []

        pods = self.__parse_pods(lockfile.get('PODS', []) or [])
        checksums = lockfile.get('SPEC CHECKSUMS', {}) or {}

        root = Dependency(key=f'cocoapods:{path.name}', name=path.name, type='cocoapods')
        root.package_files.append(str(lockfile_path.resolve()))

        root.dependencies = [
            self.__create_dep(_pod_name(entry), pods, checksums)
            for entry in (lockfile.get('DEPENDENCIES', []) or [])
        ]

        return [DependencyScan.from_dep(root)]

    def __create_dep(self, name: str, pods: t.Dict[str, dict], checksums: t.Dict[str, str]) -> Dependency:
        key = f'cocoapods:{name}'

        if dep := self.__processed_deps.get(key):
            return dep

        dep = Dependency(key=key, name=name, type='cocoapods')
        self.__processed_deps[key] = dep

        pod = pods.get(name)
        if pod is None:
            return dep

        if version := pod.get('version'):
            dep.versions.append(version)

        if checksum := checksums.get(name):
            dep.checksum = checksum

        dep.dependencies = [self.__create_dep(child, pods, checksums) for child in pod.get('deps', [])]

        return dep

    @staticmethod
    def __parse_pods(entries: t.List[t.Any]) -> t.Dict[str, dict]:
        pods: t.Dict[str, dict] = {}

        for entry in entries:
            if isinstance(entry, dict):
                (line, deps), = entry.items()
            else:
                line, deps = entry, []

            name, version = _pod_name_and_version(line)
            pods[name] = {
                'version': version,
                'deps': [_pod_name(dep) for dep in (deps or [])],
            }

        return pods


_POD_LINE_RE = re.compile(r'^(?P<name>.+?)(?:\s*\((?P<version>.+)\))?$')


def _pod_name_and_version(line: str) -> t.Tuple[str, t.Optional[str]]:
    m = _POD_LINE_RE.match(line.strip())
    if not m:
        return line.strip(), None

    return m.group('name').strip(), (m.group('version') or None)


def _pod_name(line: str) -> str:
    return _pod_name_and_version(line)[0]
