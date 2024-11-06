import json
import typing as t

from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from enum import Enum

from defusedxml import ElementTree

from . import Scanner, Dependency, DependencyScan, License, GenericScan


class ProjectType(Enum):
    NUSPEC = 1
    PACKAGE_REFERENCE = 2
    PACKAGES_CONFIG = 3
    SOLUTION = 4


class NugetScanner(Scanner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__path = None
        self.__processed_deps = set()
        self.__module = None
        self.__module_id = None
        self.__global_packages_dir = None
        self.__n_fail = 0

    @staticmethod
    def name() -> str:
        return "NuGet"

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'nuget'

    def scan(self, path: Path) -> t.Optional[DependencyScan]:
        self.__path = path
        self.__global_packages_dir = self._find_global_packages_dir()

        if deps := self._process_package(self.__path):
            return GenericScan(module='', moduleId='', deps=deps)
        else:
            return None

    def _process_package(self, path: Path, depth: int = 0) -> t.List[Dependency]:
        deps = []

        if pt := self._determine_project_type(path):
            # print(f"Processing dependency at: {' ' * depth}{path}")
            ptype, files = pt

            if ptype is ProjectType.PACKAGE_REFERENCE or ptype is ProjectType.PACKAGES_CONFIG:
                # run nuget restore with option to create a lock file
                deps = self._process_with_lock_file(files[0], depth=depth)

            elif ptype is ProjectType.NUSPEC:
                # parse nuspec file
                deps = self._create_deps_from_nuspec(files[0], depth=depth)

            elif ptype is ProjectType.SOLUTION:
                # extract projects from solution file, process them recursively
                deps = self._process_solution_file(files[0], depth=depth)

        return deps

    @staticmethod
    def _determine_project_type(path: Path) -> t.Optional[t.Tuple[ProjectType, t.List[Path]]]:
        if files := list(path.glob('*.nuspec')):
            return ProjectType.NUSPEC, files

        elif files := list(path.glob('*.*proj')):
            return ProjectType.PACKAGE_REFERENCE, files

        elif files := list(path.glob('packages.config')):
            return ProjectType.PACKAGES_CONFIG, files

        elif files := list(path.glob('*.sln')):
            return ProjectType.SOLUTION, files

        else:
            return None

    def _process_solution_file(self, solution: Path, depth: int = 0) -> t.List[Dependency]:
        with open(solution, "r") as f:
            projects = [line for line in f if line.strip().startswith("Project(")]

        # discard first Project line as it refers to itself
        # projects = projects[1:]

        projects = [p.split("=")[-1].strip() for p in projects]
        _, paths = zip(*[p.split(",")[:2] for p in projects])

        paths = [Path(PureWindowsPath(p.strip(' "')).as_posix()) for p in paths]
        paths = [p.parent for p in paths]

        deps = []
        for path in paths:
            deps.extend(self._process_package(solution.parent / path, depth=depth))

        return deps

    def _process_with_lock_file(self, project_file: Path, depth: int = 0) -> t.List[Dependency]:
        with TemporaryDirectory() as temp_dir:
            _ = self._exec("restore", str(project_file),
                           "-UseLockFile",
                           "-PackagesDirectory", temp_dir,
                           cwd=self.__path)

        lockfile = project_file.parent / "packages.lock.json"

        if not lockfile.exists():
            raise FileNotFoundError("No lockfile was generated, something must have gone wrong")

        return self._create_deps_from_lockfile(lockfile, depth=depth)

    def _create_deps_from_lockfile(self, lockfile: Path, depth: int = 0) -> t.List[Dependency]:
        with open(lockfile, "r") as f:
            lock_dict = json.load(f)

        deps = []

        for net_target, net_target_dict in lock_dict["dependencies"].items():
            for dep_name, dep_dict in net_target_dict.items():
                if (dep_type := dep_dict["type"].lower()) in ("direct", "project"):

                    dep = Dependency(key=f"nuget:{dep_name}", name=dep_name, purl_type='nuget')

                    dep.meta[".NET target"] = net_target
                    dep.meta["dependency type"] = dep_type

                    dep_id = None
                    candidates = []

                    if dep_type == "direct":
                        dep_version = dep_dict["resolved"].lower()
                        dep.versions.append(dep_version)

                        # find package in global-packages
                        candidates = self._find_in_global_packages(dep_name, dep_version)

                        dep_id = dep.key + ":" + dep_version

                    elif dep_type == "project":
                        # dependency folder should be on the same level as project folder (i.e. sibling folder)
                        candidates = [d for d in lockfile.parent.parent.glob('*') if d.name.lower() == dep_name.lower()]

                        dep_id = dep.key

                    if dep_id and dep_id not in self.__processed_deps:
                        self.__processed_deps.add(dep_id)

                        if candidates:
                            dep_dir = candidates[0]

                            dep_files = dep_dir.rglob('**')
                            dep_files = [p for p in dep_files if Path(p).is_file()]
                            dep.files.extend(dep_files)

                            # recursively create dependencies of dependency
                            dep.dependencies = self._process_package(Path(dep_dir), depth=depth + 1)

                        else:
                            self.__n_fail += 1
                            print(f"Could not find dependency location for {dep.name}")
                            print(f"Origin: {lockfile}")

                    deps.append(dep)

        return deps

    def _create_deps_from_nuspec(self, nuspec: Path, depth: int = 0) -> t.List[Dependency]:
        ns = {"nuget": "http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"}
        tree = ElementTree.parse(nuspec)

        deps = []

        for xml_target in tree.findall("*/nuget:dependencies/nuget:group", namespaces=ns):
            target = xml_target.get("targetFramework")

            for xml_dep in xml_target.findall("nuget:dependency", namespaces=ns):
                name = xml_dep.get("id")
                version = xml_dep.get("version")

                dep_key = "nuget:" + name
                dep_id = dep_key + ":" + version

                dep = Dependency(dep_key, name, purl_type='nuget')
                dep.versions.append(version)

                if not dep_id in self.__processed_deps:
                    self.__processed_deps.add(dep_id)

                    dep.meta[".NET Target"] = target
                    dep.meta["dependency type"] = "direct"

                    if candidates := self._find_in_global_packages(name, version):
                        dep_dir = candidates[0]

                        dep_files = dep_dir.rglob('**')
                        dep_files = [p for p in dep_files if Path(p).is_file()]
                        dep.files.extend(dep_files)

                        if dep_nuspec := list(dep_dir.glob('*.nuspec')):
                            meta = self._metadata_from_nuspec(dep_nuspec[0])

                            dep.licenses.append(License("", meta["licenseUrl"]))
                            dep.homepageUrl = meta["projectUrl"]
                            dep.description = meta["description"]
                            dep.meta["copyright"] = meta["copyright"]

                        dep.dependencies = self._process_package(dep_dir, depth=depth + 1)

                deps.append(dep)

        return deps

    def _find_global_packages_dir(self) -> Path:
        proc = self._exec('locals', 'global-packages', '-list', capture_output=True, cwd=self.__path)

        result = proc.stdout.decode("utf-8")
        result = Path(result.split("global-packages: ")[1].strip())

        return result

    def _find_in_global_packages(self, name: str, version: str) -> t.List[Path]:
        """Finds all subfolders of the global-packages directory that match <name>/<version>/ (case in-sensitive)."""

        candidates = self.__global_packages_dir.glob('*/*')
        candidates = [Path(str(d).lower()) for d in candidates]
        candidates = [d for d in candidates if d.parts[-2] == name.lower() and d.parts[-1] == version.lower()]

        return candidates

    @staticmethod
    def _metadata_from_nuspec(nuspec: Path) -> t.Dict:
        ns = {"nuget": "http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"}
        tree = ElementTree.parse(nuspec)
        return_dict = {}

        for tag in ("authors", "licenseUrl", "projectUrl", "description", "copyright"):
            element = tree.find(f"*/nuget:{tag}", namespaces=ns)

            return_dict[tag] = element.text if element is not None else ""

        return return_dict
