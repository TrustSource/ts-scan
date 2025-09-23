import json
import requests
import typing as t

from semantic_version import Version, NpmSpec

from pathlib import Path

from . import PackageManagerScanner, DependencyScan, Dependency, License
from ..cli import msg


class NodeScanner(PackageManagerScanner):
    def __init__(self,
                 enableMetadataRetrieval=False,
                 enableLifecycleScripts=False,
                 includeDevDependencies=False,
                 **kwargs):

        super().__init__(**kwargs)

        self.enableMetadataRetrieval = enableMetadataRetrieval
        self.enableLifecycleScripts = enableLifecycleScripts
        self.includeDevDependencies = includeDevDependencies

        self.__path = None
        self.__abs_module_path = None

        self.__lookup = {}
        self.__failed_requests = 0
        self.__lockfile_content = {}
        self.__processed_deps = set()

    @staticmethod
    def name() -> str:
        return "Node"

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'npm'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'enableMetadataRetrieval': {
                'default': False,
                'is_flag': True,
                'help': 'Enable retrieving package metadata from the NPMJS online registry'
            },
            'enableLifecycleScripts': {
                'default': False,
                'is_flag': True,
                'help': 'Enable running lifecycle scripts during install (may be a security risk)'
            },
            'includeDevDependencies': {
                'default': False,
                'is_flag': True,
                'help': 'Include development dependencies in the scan results'
            },
        }

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and (path / 'package.json').exists()

    def scan(self, path: Path) -> t.Optional[DependencyScan]:
        self.__path = path
        self.__abs_module_path = path.resolve().absolute()

        args = ['install']

        if not self.enableLifecycleScripts:
            args.append('--ignore-scripts')

        if not self.includeDevDependencies:
            args.append('--omit=dev')

        self._exec(*args, cwd=self.__path)
        lock_file = self.__path / "package-lock.json"

        if not lock_file.exists():
            return None

        with lock_file.open() as lockfile:
            self.__lockfile_content = json.load(lockfile)

        # extract root
        root = self.__lockfile_content['packages'].pop('', None)

        # first build dictionary that is indexable by name
        self.__lookup = self._dict_from_lock(self.__lockfile_content)

        # then traverse graph as described in lockfile
        pkgs = self.__lockfile_content['packages'].keys()

        deps = []
        for pkg_path in pkgs:
            if pkg_dep := self._dep_from_lock(self.__lockfile_content, pkg_path):
                deps.append(pkg_dep)

        module = ''
        moduleId = ''

        if root and (module := root.get('name')):
            dep = NodeDependency(module)
            moduleId = dep.key

            if version := root.get('version'):
                dep.versions.append(version)
                moduleId += ':' + version

            dep.package_files.append(str(path))
            dep.load_from_package()

            dep.dependencies = deps
            deps = [dep]

        return DependencyScan(module=module, moduleId=moduleId, dependencies=deps)

    @staticmethod
    def _dep_name_from_path(package_path: str) -> str:
        return package_path.split("node_modules/")[-1]

    @staticmethod
    def _dict_from_lock(lock: dict) -> dict:
        deps_dict = {}

        for dep_path, dep_dict in lock["packages"].items():
            name = NodeScanner._dep_name_from_path(dep_path)
            version = dep_dict["version"]

            deps_dict.setdefault(name, {})
            deps_dict[name][version] = dep_dict
            deps_dict[name][version]["_path"] = dep_path

        return deps_dict

    def _dep_from_lock(self, lock: dict, package_path: str = "") -> t.Optional[Dependency]:
        pkg = lock["packages"][package_path]

        if not self.includeDevDependencies and pkg.get('dev', False):
            return None

        name = pkg.get("name")
        if not name:
            name = NodeScanner._dep_name_from_path(package_path)

        version = pkg["version"]

        dep = NodeDependency(name)
        dep.versions.append(version)

        if name + version not in self.__processed_deps:
            self.__processed_deps.add(name + version)

            pkg_files_path = self.__abs_module_path / package_path
            dep.package_files.append(str(pkg_files_path))

            dep.load_from_package()

            # msg.info(f"Getting metadata for {name} {version}...")
            if self.enableMetadataRetrieval and (meta := self._metadata_from_registry(name, version)):
                dep.licenses = meta.licenses
                dep.description = meta.description
                dep.homepageUrl = meta.homepageUrl
                dep.repoUrl = meta.repoUrl

            # msg.good(" Success!")
            # else:
            #   msg.fail(" Failed!")

            for dep_name, dep_version_range in pkg.get("dependencies", {}).items():
                dep_path = None

                # find appropriate dependency version
                if dep_lookup := self.__lookup.get(dep_name):
                    for dep_version, dep_version_dict in dep_lookup.items():
                        dep_path = dep_version_dict["_path"]

                        if dep_version_range == "latest":
                            break

                        try:
                            range_spec = NpmSpec(dep_version_range)

                        except ValueError:
                            range_spec = NpmSpec("")

                        if Version(dep_version) in range_spec:
                            break
                else:
                    msg.warn(f"Dependency '{dep_name}' not found in lockfile")

                if dep_path and (_dep := self._dep_from_lock(self.__lockfile_content, dep_path)):
                    dep.dependencies.append(_dep)

        return dep

    def _metadata_from_registry(self, name: str, version: str) -> t.Optional[Dependency]:
        template = "https://registry.npmjs.org/{}/{}"

        try:
            result = requests.get(template.format(name, version))

            if result.status_code != 200:
                raise requests.ConnectionError()

            meta = json.loads(result.text)

        except requests.ConnectionError:
            self.__failed_requests += 1
            return None

        dep = Dependency(key=f"npm:{name}", name=name, type='npm')

        dep.versions.append(meta.get("version", ""))

        dep.description = meta.get("description", "")
        dep.homepageUrl = meta.get("homepage", "")
        dep.repoUrl = meta.get("repository", {}).get("url", "")

        dep.licenses.append(License(meta.get("license")))

        return dep


class NodeDependency(Dependency):
    def __init__(self, name: str):
        super().__init__(key="npm:" + name, name=name, type='npm')

    def package_file(self) -> t.Optional[Path]:
        for p in self.package_files:
            path = Path(p) / 'package.json'
            if path.exists():
                return path
        return None

    def load_from_package(self):
        pkg_path = self.package_file()
        if not pkg_path:
            return

        with pkg_path.open() as fp:
            pkg_data = json.load(fp)

        if scripts := pkg_data.get('scripts'):
            lifecycle_scripts = [s for s in scripts if s in ('preinstall', 'install', 'postinstall')]
            if len(lifecycle_scripts) > 0:
                self.meta['lifecycleScripts'] = True
                msg.warn(
                    f"{self.purl}: package contains lifecycle scripts {lifecycle_scripts}.This may be a security risk.")
