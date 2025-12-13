import toml
import requests
import typing as t

from pathlib import Path
from collections import defaultdict

from ts_scan_core import DependencyScan, Dependency, License
from . import PackageManagerScanner, PackageFileNotFoundError


class CargoScanner(PackageManagerScanner):

    def __init__(self, enableMetadataRetrieval=False, **kwargs):
        super().__init__(**kwargs)

        self.enableMetadataRetrieval = enableMetadataRetrieval

        self.__processed_deps = set()

    @staticmethod
    def name() -> str:
        return "Cargo"

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'cargo'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'enableMetadataRetrieval': {
                'default': False,
                'is_flag': True,
                'help': 'Enable retrieving package metadata from the crates.io online registry'
            }
        }

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and (path / 'Cargo.toml').exists()

    def scan(self, path: Path) -> t.Optional[DependencyScan]:
        if root := CargoDependency.load_from_package(path):

            args = ['generate-lockfile']
            self._exec(*args, cwd=path)

            lockfile_path = path / "Cargo.lock"
            if lockfile_path.exists():
                with lockfile_path.open() as fp:
                    lockfile = toml.load(fp)

                lockfile_map = defaultdict(dict)
                for pkg in lockfile.get('package', []):
                    lockfile_map[pkg['name']][pkg['version']] = pkg

                # Do not load metadata for the root package
                self.load_from_lockfile(lockfile_map, root, load_metadata=False)

            return DependencyScan.from_dep(root)

        return None

    def load_from_lockfile(self,
                           lockfile: t.Dict[str, dict],
                           pkg: 'CargoDependency',
                           load_metadata: bool = True):

        pkg_lock = lockfile[pkg.name]

        if len(pkg_lock) == 1:
            pkg_lock = pkg_lock.get(next(iter(pkg_lock)))
        elif v := pkg.version:
            pkg_lock = pkg_lock.get(v)
        else:
            return

        pkg_key = f"{pkg_lock['name']}:{pkg_lock['version']}"
        if pkg_key in self.__processed_deps:
            return

        self.__processed_deps.add(pkg_key)

        if (ver := pkg_lock.get('version')) and ver not in pkg.versions:
            pkg.versions.append(ver)

        if checksum := pkg_lock.get('checksum'):
            pkg.checksum = checksum

        deps = []

        for dep_entry in pkg_lock.get('dependencies', []):
            dep_entry = dep_entry.split(' ')

            dep = CargoDependency(dep_entry[0])

            if len(dep_entry) > 1:
                dep.versions.append(dep_entry[1])

            deps.append(dep)
            self.load_from_lockfile(lockfile, dep)

        pkg.dependencies = deps

        if load_metadata and self.enableMetadataRetrieval:
            pkg.load_from_registry()


class CargoDependency(Dependency):
    def __init__(self, name: str):
        super().__init__(key="cargo:" + name, name=name, type='cargo')

    def load_from_dict(self, data: dict):
        if repo := data.get('repository'):
            self.repoUrl = repo

        if desc := data.get('description'):
            self.description = desc

        if (version := data.get('version')) and version not in self.versions:
            self.versions.append(version)

        if lic := data.get('license'):
            self.licenses.append(License(name=lic))

        if homepage := data.get('homepage'):
            self.homepageUrl = homepage

    def load_from_registry(self):
        base_url = f"https://crates.io/api/v1/crates/{self.name}"

        if ver := self.version:
            url = f"{base_url}/{ver}"

            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                self.load_from_dict(data.get("version", data))
            except:
                pass

    @staticmethod
    def load_from_package(path: Path) -> t.Optional['CargoDependency']:
        pkg_path = path / 'Cargo.toml'

        if not pkg_path.exists():
            raise PackageFileNotFoundError()

        with pkg_path.open() as fp:
            pkg = toml.load(fp)

        if root := pkg.get('package'):
            dep = CargoDependency(root.get('name'))
            dep.load_from_dict(root)

            if (workspace := pkg.get('workspace')) and (workspace_pkg := workspace.get('package')):
                dep.load_from_dict(workspace_pkg)

            return dep

        return None
