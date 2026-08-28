import json
import os
import shutil
import typing as t
import re

from pathlib import Path, PureWindowsPath
from enum import Enum

from defusedxml import ElementTree

from . import PackageManagerScanner, Dependency, DependencyScan, License
from ..cli import msg

LockedDependency = t.Tuple[str, str, t.AbstractSet[str]]


class ProjectType(Enum):
    NUSPEC = 1
    PACKAGE_REFERENCE = 2
    PACKAGES_CONFIG = 3
    SOLUTION = 4


class NugetScanner(PackageManagerScanner):
    def __init__(self, separateProjectScans: bool = False, **kwargs):
        super().__init__(**kwargs)

        self.separateProjectScans = separateProjectScans
        self.__path = None
        self.__processed_deps = set()
        self.__module = None
        self.__module_id = None
        self.__global_packages_dir = None
        self.__n_fail = 0
        self.__using_dotnet_sdk = False

    @staticmethod
    def name() -> str:
        return "NuGet"

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'nuget'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'separateProjectScans': {
                'default': False,
                'is_flag': True,
                'help': 'Create a separate module scan for every project in a solution'
            }
        }

    def accepts(self, path: Path) -> bool:
        return self._determine_project_type(path) is not None

    def scan(self, src: t.Union[str, Path]) -> t.Iterable[DependencyScan]:
        path = Path(src)
        self._select_executable(path)

        self.__path = path
        self.__global_packages_dir = self._find_global_packages_dir()

        project_type = self._determine_project_type(path)
        if project_type is None:
            return []

        kind, files = project_type
        source_file = files[0]
        self.__processed_deps = set()

        if kind is ProjectType.SOLUTION:
            module = source_file.stem
            dependencies = self._process_solution_file(source_file)
        else:
            dependencies = self._process_package(source_file)
            if kind is ProjectType.PACKAGE_REFERENCE:
                module = self._project_name(source_file)
            elif kind is ProjectType.NUSPEC:
                module = self._nuspec_name(source_file)
            else:
                module = source_file.parent.name

        scan = DependencyScan(
            module=module,
            moduleId=f'nuget:{module}',
            dependencies=dependencies,
        )

        if (
            not self.separateProjectScans
            or project_type[0] is not ProjectType.SOLUTION
        ):
            return [scan]

        return [
            DependencyScan(
                module=project.name,
                moduleId=project.key,
                dependencies=project.dependencies,
            )
            for project in scan.dependencies
        ]

    def _select_executable(self, path: Path) -> None:
        if self.executable_path is not None:
            self.__using_dotnet_sdk = Path(self.executable_path).name.casefold() in (
                'dotnet', 'dotnet.exe'
            )
            return

        project_type = self._determine_project_type(path)
        requires_nuget = (
            project_type is not None and project_type[0] is ProjectType.PACKAGES_CONFIG
        ) or (
            path.is_dir() and (path / 'packages.config').is_file()
        ) or (
            path.is_file()
            and path.suffix in ('.csproj', '.vbproj', '.fsproj', '.proj')
            and (path.parent / 'packages.config').is_file()
        )
        dotnet = shutil.which('dotnet')
        nuget = shutil.which('nuget')

        if dotnet and not requires_nuget:
            self.executable_path = Path(dotnet)
            self.__using_dotnet_sdk = True
        elif nuget:
            self.executable_path = Path(nuget)
            self.__using_dotnet_sdk = False
        elif dotnet:
            self.executable_path = Path(dotnet)
            self.__using_dotnet_sdk = True

    def _process_package(
        self,
        path: Path,
        depth: int = 0,
        locked_dependencies: t.Optional[t.Mapping[str, LockedDependency]] = None,
        dependency_names: t.Optional[t.AbstractSet[str]] = None,
        recurse_projects: bool = True,
    ) -> t.List[Dependency]:
        deps = []

        if pt := self._determine_project_type(path):
            # print(f"Processing dependency at: {' ' * depth}{path}")
            ptype, files = pt

            if ptype is ProjectType.PACKAGE_REFERENCE or ptype is ProjectType.PACKAGES_CONFIG:
                # run nuget restore with option to create a lock file
                deps = self._process_with_lock_file(
                    files[0], depth=depth, recurse_projects=recurse_projects
                )

            elif ptype is ProjectType.NUSPEC:
                # parse nuspec file
                deps = self._create_deps_from_nuspec(
                    files[0],
                    depth=depth,
                    locked_dependencies=locked_dependencies,
                    dependency_names=dependency_names,
                )

            elif ptype is ProjectType.SOLUTION:
                # extract projects from solution file, process them recursively
                deps = self._process_solution_file(files[0], depth=depth)

        return deps

    @staticmethod
    def _determine_project_type(path: Path) -> t.Optional[t.Tuple[ProjectType, t.List[Path]]]:
        if path.is_file():
            if path.suffix == '.nuspec':
                return ProjectType.NUSPEC, [path]
            elif path.suffix in ('.csproj', '.vbproj', '.fsproj', '.proj'):
                return ProjectType.PACKAGE_REFERENCE, [path]
            elif path.name == 'packages.config':
                return ProjectType.PACKAGES_CONFIG, [path]
            elif path.suffix == '.sln':
                return ProjectType.SOLUTION, [path]
            else:
                return None
        else:
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

    SLN_PROJECT_RE = re.compile(
        r'^Project\("\s*({[A-F0-9\-]+})\s*"\)\s*=\s*"(.*?)"\s*,\s*"(.*?)"\s*,\s*"{[A-F0-9\-]+}"',
        re.IGNORECASE | re.MULTILINE
    )

    SLN_FOLDER_TYPE_GUIDS = [
        '{2150E333-8FDC-42A3-9474-1A3956D46DE8}',
        '{66A26720-8FB5-11D2-AA7E-00C04F688DDE}'
    ]

    def _process_solution_file(self, solution: Path, depth: int = 0) -> t.List[Dependency]:
        with open(solution, "r") as f:
            content = f.read()

        # Extract (project_name, project_file_location)
        projects = [
            (m.group(2), m.group(3))
            for m in self.SLN_PROJECT_RE.finditer(content)
            if m.group(1).upper() not in self.SLN_FOLDER_TYPE_GUIDS
        ]

        deps = []
        for solution_project_name, project_path in projects:
            relative_path = Path(PureWindowsPath(project_path).as_posix())
            project_file = solution.parent / relative_path
            if not project_file.is_file():
                continue

            # Each solution project is an independent graph root. Project references
            # remain visible as direct edges, but are not recursively expanded here
            # because every solution project is represented at the solution root.
            self.__processed_deps = set()
            project_dependencies = self._process_package(
                project_file,
                depth=depth + 1,
                recurse_projects=False,
            )
            project_name = self._project_name(project_file)
            project = Dependency(
                key=f'nuget:{project_name}',
                name=project_name,
                type='nuget',
                dependencies=project_dependencies,
            )
            project.package_files.append(str(project_file.parent.resolve()))
            project.meta['dependency_type'] = 'project'
            project.meta['solution project name'] = solution_project_name
            deps.append(project)

        return deps

    def _process_with_lock_file(
        self,
        project_file: Path,
        depth: int = 0,
        recurse_projects: bool = True,
    ) -> t.List[Dependency]:
        assert self.__path is not None
        assert self.__global_packages_dir is not None
        working_dir = self.__path if self.__path.is_dir() else self.__path.parent
        lockfile = project_file.parent / "packages.lock.json"

        if not self._exec_to_generate_lockfile(
            lockfile,
            "restore",
            str(project_file),
            "--use-lock-file" if self.__using_dotnet_sdk else "-UseLockFile",
            "--packages" if self.__using_dotnet_sdk else "-PackagesDirectory",
            str(self.__global_packages_dir),
            cwd=working_dir,
            report_missing=False,
        ):
            assets_dependencies = self._create_deps_from_project_assets(
                project_file,
                depth=depth,
                recurse_projects=recurse_projects,
            )
            if assets_dependencies is not None:
                return assets_dependencies

            self._report_missing_lockfile(lockfile)
            return []

        return self._create_deps_from_lockfile(
            lockfile,
            depth=depth,
            project_file=project_file,
            recurse_projects=recurse_projects,
        )

    def _create_deps_from_lockfile(
        self,
        lockfile: Path,
        depth: int = 0,
        project_file: t.Optional[Path] = None,
        recurse_projects: bool = True,
    ) -> t.List[Dependency]:
        with open(lockfile, "r") as f:
            lock_dict = json.load(f)

        return self._create_deps_from_lock_data(
            lock_dict,
            lockfile,
            depth=depth,
            project_file=project_file,
            recurse_projects=recurse_projects,
        )

    def _create_deps_from_lock_data(
        self,
        lock_dict: t.Mapping[str, t.Any],
        lockfile: Path,
        depth: int = 0,
        project_file: t.Optional[Path] = None,
        recurse_projects: bool = True,
    ) -> t.List[Dependency]:

        deps = []
        direct_project_names = self._direct_project_names(lockfile, project_file)

        dependencies = lock_dict.get("dependencies", {})
        if not isinstance(dependencies, dict):
            return deps

        for net_target, net_target_dict in dependencies.items():
            if not isinstance(net_target_dict, dict):
                continue
            locked_dependencies = {
                name.casefold(): (
                    name,
                    dep["resolved"],
                    frozenset(
                        child_name.casefold()
                        for child_name in dep.get("dependencies", {})
                    ),
                )
                for name, dep in net_target_dict.items()
                if isinstance(dep.get("resolved"), str)
            }

            for dep_name, dep_dict in net_target_dict.items():
                if (dep_type := dep_dict["type"].lower()) in ("direct", "project"):

                    if (
                        dep_type == 'project'
                        and direct_project_names is not None
                        and dep_name.casefold() not in direct_project_names
                    ):
                        continue

                    output_name = (
                        self._project_dependency_name(
                            lockfile, dep_name, project_file=project_file
                        )
                        if dep_type == 'project'
                        else dep_name
                    )
                    dep = Dependency(
                        key=f"nuget:{output_name}", name=output_name, type='nuget'
                    )

                    dep.meta["target"] = net_target
                    dep.meta["dependency_type"] = dep_type

                    dep_id = None
                    candidates = []

                    if dep_type == "direct":
                        dep_version = dep_dict["resolved"]
                        dep.versions.append(dep_version)

                        # find package in global-packages
                        candidates = self._find_in_global_packages(dep_name, dep_version)

                        dep_id = dep.key + ":" + dep_version

                    elif dep_type == "project":
                        candidates = self._find_project_reference_candidates(
                            lockfile, dep_name, project_file=project_file
                        )

                        if not candidates:
                            # Retain compatibility with projects whose generated lock file has no
                            # corresponding ProjectReference in the project file.
                            candidates = [
                                d for d in lockfile.parent.parent.glob('*')
                                if d.name.casefold() == dep_name.casefold()
                            ]

                        dep_id = dep.key

                    if dep_id and dep_id not in self.__processed_deps:
                        self.__processed_deps.add(dep_id)

                        if candidates:
                            dep_dir = candidates[0]
                            dep.package_files.append(str(dep_dir))

                            # recursively create dependencies of dependency
                            if dep_type == "direct":
                                dep.dependencies = self._process_package(
                                    dep_dir,
                                    depth=depth + 1,
                                    locked_dependencies=locked_dependencies,
                                    dependency_names=locked_dependencies[
                                        dep_name.casefold()
                                    ][2],
                                )
                            elif recurse_projects:
                                dep.dependencies = self._process_package(
                                    dep_dir, depth=depth + 1
                                )

                        else:
                            self.__n_fail += 1
                            print(f"Could not find dependency location for {dep.name}")
                            print(f"Origin: {lockfile}")

                    deps.append(dep)

        return deps

    def _create_deps_from_project_assets(
        self,
        project_file: Path,
        depth: int = 0,
        recurse_projects: bool = True,
    ) -> t.Optional[t.List[Dependency]]:
        lockfile = project_file.parent / 'packages.lock.json'
        for assets_file in self._project_assets_files(lockfile, project_file):
            loaded = self._load_project_assets(assets_file, project_file)
            if loaded is None:
                continue

            assets, _ = loaded
            lock_data = self._lock_data_from_project_assets(assets)
            if lock_data is None:
                continue

            msg.info(
                f'NuGet did not generate {lockfile.name}. '
                f'Using resolved dependencies from {assets_file}.'
            )
            return self._create_deps_from_lock_data(
                lock_data,
                lockfile,
                depth=depth,
                project_file=project_file,
                recurse_projects=recurse_projects,
            )

        return None

    @staticmethod
    def _lock_data_from_project_assets(
        assets: t.Mapping[str, t.Any],
    ) -> t.Optional[t.Dict[str, t.Any]]:
        targets = assets.get('targets')
        if not isinstance(targets, dict):
            return None

        direct_package_names = set()
        project = assets.get('project', {})
        frameworks = project.get('frameworks', {}) if isinstance(project, dict) else {}
        if isinstance(frameworks, dict):
            for framework in frameworks.values():
                declared = (
                    framework.get('dependencies', {})
                    if isinstance(framework, dict)
                    else {}
                )
                if isinstance(declared, dict):
                    direct_package_names.update(
                        str(name).casefold() for name in declared
                    )

        dependencies = {}
        for target_name, target in targets.items():
            if not isinstance(target_name, str) or not isinstance(target, dict):
                continue

            target_dependencies = {}
            for identity, target_entry in target.items():
                if not isinstance(identity, str) or not isinstance(target_entry, dict):
                    continue
                if '/' not in identity:
                    continue

                name, version = identity.rsplit('/', 1)
                dependency_type = str(target_entry.get('type', '')).casefold()
                if dependency_type == 'project':
                    lock_type = 'Project'
                elif dependency_type == 'package':
                    lock_type = (
                        'Direct'
                        if name.casefold() in direct_package_names
                        else 'Transitive'
                    )
                else:
                    continue

                dependency = {
                    'type': lock_type,
                    'dependencies': target_entry.get('dependencies', {}),
                }
                if dependency_type == 'package':
                    dependency['resolved'] = version
                target_dependencies[name] = dependency

            dependencies[target_name] = target_dependencies

        return {'dependencies': dependencies}

    @staticmethod
    def _project_names(project_file: Path) -> t.Set[str]:
        names = {project_file.stem.casefold()}
        tree = ElementTree.parse(project_file)

        for element in tree.iter():
            if (
                element.tag.rsplit('}', 1)[-1]
                in ('AssemblyName', 'PackageId', 'Name')
                and element.text
            ):
                names.add(element.text.strip().casefold())

        return names

    def _project_name(self, project_file: Path) -> str:
        lockfile = project_file.parent / 'packages.lock.json'
        for assets_file in self._project_assets_files(lockfile, project_file):
            loaded = self._load_project_assets(assets_file, project_file)
            if loaded is None:
                continue

            assets, _ = loaded
            project = assets.get('project', {})
            restore = project.get('restore', {}) if isinstance(project, dict) else {}
            name = restore.get('projectName') if isinstance(restore, dict) else None
            if isinstance(name, str) and name.strip():
                return name.strip()

        tree = ElementTree.parse(project_file)
        declared_names = {}
        for element in tree.iter():
            tag = element.tag.rsplit('}', 1)[-1]
            if tag in ('PackageId', 'AssemblyName', 'Name') and element.text:
                value = element.text.strip()
                if value and '$(' not in value:
                    declared_names.setdefault(tag, value)

        for tag in ('PackageId', 'AssemblyName', 'Name'):
            if name := declared_names.get(tag):
                return name
        return project_file.stem

    @staticmethod
    def _nuspec_name(nuspec: Path) -> str:
        ns = {"nuget": "http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"}
        tree = ElementTree.parse(nuspec)
        element = tree.find('*/nuget:id', namespaces=ns)
        if element is not None and element.text and element.text.strip():
            return element.text.strip()
        return nuspec.stem

    @staticmethod
    def _path_from_msbuild(value: str) -> Path:
        return Path(PureWindowsPath(value).as_posix())

    @classmethod
    def _resolve_msbuild_path(cls, value: str, project_dir: Path) -> Path:
        path = cls._path_from_msbuild(value)
        if not path.is_absolute():
            path = project_dir / path
        return path.resolve()

    @classmethod
    def _load_project_assets(
        cls,
        assets_file: Path,
        project_file: t.Optional[Path],
    ) -> t.Optional[t.Tuple[t.Dict, Path]]:
        try:
            with assets_file.open('r') as fp:
                assets = json.load(fp)
        except (OSError, ValueError):
            return None

        if not isinstance(assets, dict):
            return None

        project = assets.get('project', {})
        if not isinstance(project, dict):
            project = {}
        restore = project.get('restore', {})
        if not isinstance(restore, dict):
            restore = {}
        restore_project_path = restore.get('projectPath')
        assets_project_file = None
        if isinstance(restore_project_path, str):
            assets_project_file = cls._path_from_msbuild(restore_project_path)
            if not assets_project_file.is_absolute():
                assets_project_file = assets_file.parent / assets_project_file
            assets_project_file = assets_project_file.resolve()

        if (
            project_file is not None
            and assets_project_file is not None
            and assets_project_file != project_file.resolve()
        ):
            return None
        if (
            project_file is not None
            and assets_project_file is None
            and assets_file.resolve()
            != (project_file.parent / 'obj' / 'project.assets.json').resolve()
        ):
            return None

        project_dir = (
            assets_project_file.parent
            if assets_project_file is not None
            else project_file.parent.resolve()
            if project_file is not None
            else assets_file.parent.parent
        )
        return assets, project_dir

    @classmethod
    def _project_assets_files(
        cls,
        lockfile: Path,
        project_file: t.Optional[Path],
    ) -> t.Iterable[Path]:
        project_dir = project_file.parent if project_file is not None else lockfile.parent
        default = project_dir / 'obj' / 'project.assets.json'
        yielded = set()

        if default.is_file():
            yielded.add(default.resolve())
            yield default

        # BaseIntermediateOutputPath and MSBuildProjectExtensionsPath can relocate
        # project.assets.json. Only search when the conventional location did not
        # identify the dependency, and validate candidates against projectPath.
        try:
            candidates = project_dir.rglob('project.assets.json')
            for candidate in candidates:
                resolved = candidate.resolve()
                if resolved not in yielded:
                    yielded.add(resolved)
                    yield candidate
        except OSError:
            return

    @classmethod
    def _find_project_in_assets(
        cls,
        lockfile: Path,
        dep_name: str,
        project_file: t.Optional[Path],
    ) -> t.List[Path]:
        dependency_name = dep_name.casefold()

        for assets_file in cls._project_assets_files(lockfile, project_file):
            loaded = cls._load_project_assets(assets_file, project_file)
            if loaded is None:
                continue

            assets, project_dir = loaded
            candidates = []
            libraries = assets.get('libraries', {})
            if not isinstance(libraries, dict):
                continue

            for identity, library in libraries.items():
                if not isinstance(identity, str) or not isinstance(library, dict):
                    continue
                if str(library.get('type', '')).casefold() != 'project':
                    continue

                name = identity.rsplit('/', 1)[0]
                if name.casefold() != dependency_name:
                    continue

                raw_path = library.get('msbuildProject') or library.get('path')
                if not isinstance(raw_path, str):
                    continue

                reference_file = cls._path_from_msbuild(raw_path)
                if not reference_file.is_absolute():
                    reference_file = project_dir / reference_file
                reference_file = reference_file.resolve()

                if (
                    reference_file.is_file()
                    and reference_file.parent not in candidates
                ):
                    candidates.append(reference_file.parent)

            if candidates:
                return candidates

        return []

    @classmethod
    def _project_dependency_name(
        cls,
        lockfile: Path,
        dep_name: str,
        project_file: t.Optional[Path],
    ) -> str:
        dependency_name = dep_name.casefold()
        for assets_file in cls._project_assets_files(lockfile, project_file):
            loaded = cls._load_project_assets(assets_file, project_file)
            if loaded is None:
                continue

            assets, _ = loaded
            libraries = assets.get('libraries', {})
            if not isinstance(libraries, dict):
                continue
            for identity, library in libraries.items():
                if not isinstance(identity, str) or not isinstance(library, dict):
                    continue
                if str(library.get('type', '')).casefold() != 'project':
                    continue

                name = identity.rsplit('/', 1)[0]
                if name.casefold() == dependency_name:
                    return name

        return dep_name

    @classmethod
    def _direct_project_names(
        cls,
        lockfile: Path,
        project_file: t.Optional[Path],
    ) -> t.Optional[t.Set[str]]:
        for assets_file in cls._project_assets_files(lockfile, project_file):
            loaded = cls._load_project_assets(assets_file, project_file)
            if loaded is None:
                continue

            assets, project_dir = loaded
            project = assets.get('project', {})
            restore = project.get('restore', {}) if isinstance(project, dict) else {}
            frameworks = restore.get('frameworks') if isinstance(restore, dict) else None
            if not isinstance(frameworks, dict):
                return None

            direct_project_files = set()
            for framework in frameworks.values():
                if not isinstance(framework, dict):
                    continue
                references = framework.get('projectReferences', {})
                if not isinstance(references, dict):
                    continue
                for reference_path, reference in references.items():
                    raw_path = (
                        reference.get('projectPath')
                        if isinstance(reference, dict)
                        else None
                    )
                    if not isinstance(raw_path, str):
                        raw_path = reference_path
                    if isinstance(raw_path, str):
                        direct_project_files.add(
                            cls._resolve_msbuild_path(raw_path, project_dir)
                        )

            libraries = assets.get('libraries', {})
            if not isinstance(libraries, dict):
                return None

            names = set()
            for identity, library in libraries.items():
                if not isinstance(identity, str) or not isinstance(library, dict):
                    continue
                if str(library.get('type', '')).casefold() != 'project':
                    continue

                raw_path = library.get('msbuildProject') or library.get('path')
                if not isinstance(raw_path, str):
                    continue
                project_path = cls._resolve_msbuild_path(raw_path, project_dir)
                if project_path in direct_project_files:
                    names.add(identity.rsplit('/', 1)[0].casefold())

            return names

        return None

    def _find_project_reference_candidates(
        self,
        lockfile: Path,
        dep_name: str,
        project_file: t.Optional[Path] = None,
    ) -> t.List[Path]:
        """Locate a project dependency using NuGet assets or ProjectReference paths."""
        candidates = self._find_project_in_assets(lockfile, dep_name, project_file)
        if candidates:
            return candidates

        dependency_name = dep_name.casefold()
        candidates = []

        for project_file in lockfile.parent.glob('*.*proj'):
            tree = ElementTree.parse(project_file)

            for reference in tree.iter():
                if reference.tag.rsplit('}', 1)[-1] != 'ProjectReference':
                    continue

                include = reference.get('Include')
                if not include or '$(' in include:
                    continue

                relative_path = Path(PureWindowsPath(include).as_posix())
                reference_file = (
                    relative_path if relative_path.is_absolute()
                    else project_file.parent / relative_path
                ).resolve()

                if not reference_file.is_file():
                    continue

                names = self._project_names(reference_file)
                names.update(
                    child.text.strip().casefold()
                    for child in reference
                    if child.tag.rsplit('}', 1)[-1] == 'Name' and child.text
                )

                if dependency_name in names and reference_file.parent not in candidates:
                    candidates.append(reference_file.parent)

        return candidates

    def _create_deps_from_nuspec(
        self,
        nuspec: Path,
        depth: int = 0,
        locked_dependencies: t.Optional[t.Mapping[str, LockedDependency]] = None,
        dependency_names: t.Optional[t.AbstractSet[str]] = None,
    ) -> t.List[Dependency]:
        ns = {"nuget": "http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"}
        tree = ElementTree.parse(nuspec)

        deps = []

        for xml_target in tree.findall("*/nuget:dependencies/nuget:group", namespaces=ns):
            target = xml_target.get("targetFramework")

            for xml_dep in xml_target.findall("nuget:dependency", namespaces=ns):
                name = xml_dep.get("id")
                version = xml_dep.get("version")
                if name is None or version is None:
                    continue

                child_dependency_names = None
                if locked_dependencies is not None:
                    normalized_name = name.casefold()
                    if (
                        dependency_names is not None
                        and normalized_name not in dependency_names
                    ):
                        continue

                    locked_dependency = locked_dependencies.get(normalized_name)
                    if locked_dependency is None:
                        continue

                    name, version, child_dependency_names = locked_dependency

                dep_key = "nuget:" + name
                dep_id = dep_key + ":" + version

                dep = Dependency(key=dep_key, name=name, type='nuget')
                dep.versions.append(version)

                if dep_id not in self.__processed_deps:
                    self.__processed_deps.add(dep_id)

                    dep.meta["target"] = target
                    dep.meta["dependency_type"] = "direct"

                    if candidates := self._find_in_global_packages(name, version):
                        dep_dir = candidates[0]

                        dep_files = dep_dir.rglob('**')
                        dep_files = [str(p) for p in dep_files if Path(p).is_file()]

                        dep.package_files.extend(dep_files)

                        if dep_nuspec := list(dep_dir.glob('*.nuspec')):
                            meta = self._metadata_from_nuspec(dep_nuspec[0])

                            dep.licenses.append(License("", meta["licenseUrl"]))
                            dep.homepageUrl = meta["projectUrl"]
                            dep.description = meta["description"]
                            dep.meta["copyright"] = meta["copyright"]

                        dep.dependencies = self._process_package(
                            dep_dir,
                            depth=depth + 1,
                            locked_dependencies=locked_dependencies,
                            dependency_names=child_dependency_names,
                        )

                deps.append(dep)

        return deps

    def _find_global_packages_dir(self) -> Path:
        assert self.__path is not None
        working_dir = self.__path if self.__path.is_dir() else self.__path.parent

        args = ['nuget'] if self.__using_dotnet_sdk else []
        args.extend(['locals', 'global-packages'])
        args.append('--list' if self.__using_dotnet_sdk else '-list')

        proc = self._exec(*args, capture_output=True, cwd=working_dir)

        stdout = proc.stdout or b''
        result = (
            stdout.decode('utf-8', errors='replace')
            if isinstance(stdout, bytes)
            else str(stdout)
        )
        match = re.search(r'^global-packages:\s*(.+)$', result, re.IGNORECASE | re.MULTILINE)
        if match:
            return Path(match.group(1).strip())

        configured = os.environ.get('NUGET_PACKAGES')
        fallback = Path(configured) if configured else Path.home() / '.nuget' / 'packages'
        msg.info(
            'Could not determine the NuGet global-packages directory from the '
            f'executable output. Using {fallback}.'
        )
        return fallback

    def _find_in_global_packages(self, name: str, version: str) -> t.List[Path]:
        """Finds all subfolders of the global-packages directory that match <name>/<version>/ (case in-sensitive)."""

        if self.__global_packages_dir is None:
            return []

        package_name = name.casefold()
        package_version = version.casefold()
        return [
            candidate
            for candidate in self.__global_packages_dir.glob('*/*')
            if candidate.parent.name.casefold() == package_name
            and candidate.name.casefold() == package_version
        ]

    @staticmethod
    def _metadata_from_nuspec(nuspec: Path) -> t.Dict:
        ns = {"nuget": "http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"}
        tree = ElementTree.parse(nuspec)
        return_dict = {}

        for tag in ("authors", "licenseUrl", "projectUrl", "description", "copyright"):
            element = tree.find(f"*/nuget:{tag}", namespaces=ns)

            return_dict[tag] = element.text if element is not None else ""

        return return_dict
