import subprocess
import os
import json

from pathlib import Path, PureWindowsPath
from typing import Iterable, List, Tuple, Dict ,Optional
from enum import Enum
from glob import glob

from defusedxml import ElementTree

from . import Dependency, DependencyScan, License

class ProjectType(Enum):
    NUSPEC = 1
    PACKAGE_REFERENCE = 2
    PACKAGES_CONFIG = 3
    SOLUTION = 4


def scan(path: Path) -> Optional[DependencyScan]:
    _scan = NugetScan(path)
    _scan.execute()

    return _scan if _scan.dependencies else None


class NugetScan(DependencyScan):
    def __init__(self, path: Path):
        super().__init__()

        self.__path = Path(path)
        self.__processed_deps = set()
        self.__module = None
        self.__module_id = None
        self.__global_packages_dir = None
        self.__nuget_command = ["nuget"]
        self.__n_fail = 0

        self.__dependencies = []


    @property
    def module(self) -> str:
        return self.__module
    
    @property
    def moduleId(self) -> str:
        return self.__module_id
    
    @property
    def dependencies(self) -> Iterable['Dependency']:
        return self.__dependencies
    
    def __len__(self):
        return len(self.dependencies)
    
    def execute(self):
        os.chdir(self.__path)
        self.__nuget_command = self._determine_nuget_command()
        self.__global_packages_dir = self._find_global_packages_dir()

        self.__dependencies = self._process_package(self.__path)

        print(f"Scan complete, failed to process {self.__n_fail} dependenc{'y' if self.__n_fail == 1 else 'ies'}.")

    
    def _process_package(self, path: Path, depth: int = 0) -> List[Dependency]:
        print(f"Processing dependency at: {' ' * depth}{path}")

        ptype, files = self._determine_project_type(path)

        deps = []
        if ptype is ProjectType.PACKAGE_REFERENCE or ptype is ProjectType.PACKAGES_CONFIG:
            # run nuget restore with option to create a lock file
            deps = self._process_with_lock_file(path, Path(files[0], depth=depth).parts[-1])

        elif ptype is ProjectType.NUSPEC:
            # parse nuspec file
            deps = self._create_deps_from_nuspec(files[0], depth=depth)
        
        elif ptype is ProjectType.SOLUTION:
            # extract projects from solution file, process them recursively
            deps = self._process_solution_file(files[0], depth=depth)

        return deps
    
    
    def _determine_project_type(self, path: Path) -> Tuple[ProjectType, Path]:
        if files := glob(str(path / "*.nuspec")):
            return ProjectType.NUSPEC, [Path(f) for f in files]
        
        elif files := glob(str(path / "*.*proj")):
            return ProjectType.PACKAGE_REFERENCE, [Path(f) for f in files]
        
        elif files := glob(str(path / "packages.config")):
            return ProjectType.PACKAGES_CONFIG, [Path(f) for f in files]
        
        elif files := glob(str(path / "*.sln")):
            return ProjectType.SOLUTION, [Path(f) for f in files]
        
        else:
            raise FileNotFoundError("Could not determine project type")
        
    
    def _process_solution_file(self, solution: Path, depth: int = 0) -> List[Dependency]:
        with open(solution, "r") as f:
            projects = [line for line in f if line.strip().startswith("Project(")]

        # discard first Project line as it refers to itself
        projects = projects[1:]

        projects = [p.split("=")[-1].strip() for p in projects]
        names, paths = zip(*[p.split(",")[:2] for p in projects])

        names = [n.strip(' "') for n in names]
        paths = [Path(PureWindowsPath(p.strip(' "')).as_posix()) for p in paths]
        paths = [p.parent for p in paths if p.exists()]

        deps = []
        
        for path in paths:
            deps.extend(self._process_package(solution.parent / path, depth=depth))

        return deps
    

    def _process_with_lock_file(self, path: Path, project_file: Path, depth: int = 0) -> List[Dependency]:
        subprocess.run(self.__nuget_command + ["restore", str(path / project_file), "-UseLockFile"], stdout=subprocess.PIPE)

        lockfile = path / "packages.lock.json"

        if not lockfile.exists():
            raise FileNotFoundError("No lockfile was generated, something must have gone wrong")
        
        return self._create_deps_from_lockfile(lockfile, depth=depth)
        

    def _create_deps_from_lockfile(self, lockfile: Path, depth: int = 0) -> List[Dependency]:
        with open(lockfile, "r") as f:
            lock_dict = json.load(f)

        deps = []

        for net_target, net_target_dict in lock_dict["dependencies"].items():
            for dep_name, dep_dict in net_target_dict.items():
                if (dep_type := dep_dict["type"].lower()) in ("direct", "project"):

                    dep = Dependency(
                        "nuget:" + dep_name, 
                        dep_name
                    )

                    dep.meta[".NET target"] = net_target
                    dep.meta["dependency type"] = dep_type

                    if dep_type == "direct":
                        dep_version = dep_dict["resolved"].lower()
                        dep.versions.append(dep_version)

                        # find package in global-packages
                        candidates = self._find_in_global_packages(dep_name, dep_version)

                        dep_id = dep.key + ":" + dep_version

                    elif dep_type == "project":
                        # dependency folder should be on the same level as project folder (i.e. sibling folder)
                        candidates = glob(str(lockfile.parent.parent / "*"))
                        candidates = [d for d in candidates if Path(d.lower()).parts[-1] == dep_name.lower()]
                    
                        dep_id = dep.key
                        
                    if not dep_id in self.__processed_deps:
                        self.__processed_deps.add(dep_id)

                        if candidates:
                            dep.files.append(candidates[0])

                            # recursively create dependencies of dependency
                            dep.dependencies = self._process_package(Path(dep.files[0]), depth=depth+1)
                        
                        else:
                            self.__n_fail += 1
                            print(f"Could not find dependency location for {dep.name}")
                            print(f"Origin: {lockfile}")

                    deps.append(dep)

        return deps
    

    def _create_deps_from_nuspec(self, nuspec: Path, depth: int = 0) -> List[Dependency]:
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

                dep = Dependency(dep_key, name)
                dep.versions.append(version)

                if not dep_id in self.__processed_deps:
                    self.__processed_deps.add(dep_id)

                    dep.meta[".NET Target"] = target
                    dep.meta["dependency type"] = "direct"

                    if candidates := self._find_in_global_packages(name, version):
                        dep_files = candidates[0]
                        dep.files.append(dep_files)

                        dep_nuspec = glob(str(dep_files / "*.nuspec"))[0]
                        meta = self._metadata_from_nuspec(dep_nuspec)

                        dep.licenses.append(License("", meta["licenseUrl"]))
                        dep.homepageUrl = meta["projectUrl"]
                        dep.description = meta["description"]
                        dep.meta["copyright"] = meta["copyright"]

                        dep.dependencies = self._process_package(dep_files, depth=depth+1)

                deps.append(dep)

        return deps


    def _find_global_packages_dir(self) -> Path:
        result = subprocess.run(self.__nuget_command + ["locals", "global-packages", "-list"], stdout=subprocess.PIPE)
        result = Path(result.stdout.decode("utf-8").split("global-packages: ")[1].strip())

        return result
    
    def _find_in_global_packages(self, name: str, version: str) -> List[Path]:
        """Finds all subfolders of the global-packages directory that match <name>/<version>/ (case insensitive)."""

        candidates = glob(str(self.__global_packages_dir / "*" / "*"))
        candidates = [Path(d.lower()) for d in candidates]
        candidates = [d for d in candidates if d.parts[-2] == name.lower() and d.parts[-1] == version.lower()]
    
        return candidates
    
    @staticmethod
    def _metadata_from_nuspec(nuspec: Path) -> Dict:
        ns = {"nuget": "http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"}
        tree = ElementTree.parse(nuspec)
        return_dict = {}

        for tag in ("authors", "licenseUrl", "projectUrl", "description", "copyright"):
            element = tree.find(f"*/nuget:{tag}", namespaces=ns)
            
            return_dict[tag] = element.text if element is not None else ""

        return return_dict

    @staticmethod
    def _determine_nuget_command() -> List['str']:
        try:
            command = ["nuget"]
            subprocess.run(command)

        except FileNotFoundError:
            command = ["mono", "/usr/local/bin/nuget.exe"]
            result = subprocess.run(command, stdout=subprocess.PIPE)

            if "No such file or directory" in result.stdout.decode("utf-8"):
                raise FileNotFoundError("Detected mono, but did not find nuget.exe at expected location /usr/local/bin/nuget.exe")
        
        return command
    

if __name__ == "__main__":
    #test_scan = NugetScan("/home/soren/eacg/sample_projects/nuget/ts-dotnet/TrustSource/TS-NetCore-Scanner.ConsoleApp")
    #test_scan = NugetScan("/home/soren/eacg/sample_projects/nuget/ts-dotnet/TrustSource")
    #test_scan = NugetScan("/home/soren/eacg/sample_projects/nuget/AutoMapper/src/AutoMapper")
    #test_scan = NugetScan("/home/soren/eacg/sample_projects/nuget/AutoMapper")
    #test_scan = NugetScan("/home/soren/eacg/sample_projects/nuget/ts-dotnet/TrustSource/TS-NET-Scanner.Common/")
    test_scan = NugetScan("/home/soren/eacg/sample_projects/nuget/Castleproject.Core")
    test_scan.execute()