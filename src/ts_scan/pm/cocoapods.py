import re
import typing as t
import yaml

from collections import deque
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
        self.__processed_deps = {}

        with lockfile_path.open() as fp:
            lockfile = yaml.safe_load(fp)

        if not lockfile:
            return []

        pods = self.__parse_pods(lockfile.get('PODS', []) or [])
        checksums = lockfile.get('SPEC CHECKSUMS', {}) or {}
        declared_root_names = [_dependency_name(entry) for entry in (lockfile.get('DEPENDENCIES', []) or [])]
        root_names = _resolved_declared_root_names(declared_root_names, pods) or _resolved_root_names(pods)

        root = Dependency(key=f'cocoapods:{path.name}', name=path.name, type='cocoapods')
        root.package_files.append(str(lockfile_path.resolve()))

        root.dependencies = [self.__create_dep(name, pods, checksums) for name in root_names]

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


def _dependency_name(entry: t.Any) -> str:
    if isinstance(entry, dict):
        (line, _), = entry.items()
    else:
        line = entry
    return _pod_name(line)


def _resolved_root_names(pods: t.Dict[str, dict]) -> t.List[str]:
    incoming = {name: 0 for name in pods.keys()}

    for pod in pods.values():
        for child in pod.get('deps', []):
            if child in incoming:
                incoming[child] += 1

    return [name for name, count in incoming.items() if count == 0]


def _resolved_declared_root_names(declared: t.List[str], pods: t.Dict[str, dict]) -> t.List[str]:
    if not pods:
        return declared

    roots = set(_resolved_root_names(pods))
    parents: t.Dict[str, t.List[str]] = {name: [] for name in pods.keys()}
    for parent_name, pod in pods.items():
        for child_name in pod.get('deps', []):
            if child_name in parents and parent_name not in parents[child_name]:
                parents[child_name].append(parent_name)

    resolved: t.List[str] = []
    for name in declared:
        if name not in pods or name in roots:
            resolved_name = name
        else:
            resolved_name = _resolve_to_declared_root(name, roots, parents)
        if resolved_name not in resolved:
            resolved.append(resolved_name)

    return resolved


def _resolve_to_declared_root(
    name: str,
    roots: t.Set[str],
    parents: t.Dict[str, t.List[str]],
) -> str:
    queue = deque(parents.get(name, []))
    visited = {name}

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        if current in roots:
            return current
        queue.extend(parents.get(current, []))

    return name
