import subprocess
import os
import json

from pathlib import Path
from typing import Iterable, List, Tuple
from enum import Enum
from glob import glob

from . import Dependency, DependencyScan, License


class ProjectType(Enum):
    NUSPEC = 1
    PACKAGE_REFERENCE = 2
    PACKAGES_CONFIG = 3
    SOLUTION = 4

class NugetScan(DependencyScan):
    def __init__(self, path: Path):
        super().__init__()

        self.__path = Path(path)
        self.__processed_deps = set()
        self.__module = None
        self.__module_id = None
        self.__global_packages_dir = None
        self.__nuget_command = ["nuget"]

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

    
    def _process_package(self, path: Path) -> List[Dependency]:
        print("Processing package:", path)

        ptype, files = self._determine_project_type(path)

        deps = []
        if ptype is ProjectType.PACKAGE_REFERENCE or ptype is ProjectType.PACKAGES_CONFIG:
            # run nuget restore with option to create a lock file
            deps = self._process_with_lock_file(path, Path(files[0]).parts[-1])

        elif ptype is ProjectType.NUSPEC:
            # parse nuspec file
            deps = []
        
        elif ptype is ProjectType.SOLUTION:
            # extract projects from solution file, process them recursively
            deps = []

        return deps
    
    
    def _determine_project_type(self, path: Path) -> Tuple[ProjectType, Path]:
        if files := glob(str(path / "*.nuspec")):
            return ProjectType.NUSPEC, files
        
        elif files := glob(str(path / "*.*proj")):
            return ProjectType.PACKAGE_REFERENCE, files
        
        elif files := glob(str(path / "packages.config")):
            return ProjectType.PACKAGES_CONFIG, files
        
        elif files := glob(str(path / "*.sln")):
            return ProjectType.SOLUTION, files
        
        else:
            raise FileNotFoundError("Could not determine project type")
        
    
    def _process_with_lock_file(self, path: Path, project_file: Path) -> List[Dependency]:
        subprocess.run(self.__nuget_command + ["restore", str(path / project_file), "-UseLockFile"], stdout=subprocess.PIPE)

        lockfile = path / "packages.lock.json"

        if not lockfile.exists():
            raise FileNotFoundError("No lockfile was generated, something must have gone wrong")
        
        return self._create_deps_from_lockfile(lockfile)
        

    def _create_deps_from_lockfile(self, lockfile: Path) -> List['str']:
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
                        candidates = glob(str(self.__global_packages_dir / "*" / "*"))
                        candidates = [d for d in candidates if Path(d.lower()).parts[-2] == dep_name.lower() and Path(d.lower()).parts[-1] == dep_version]

                        dep_id = dep.key + ":" + dep_version

                    elif dep_type == "project":
                        # dependency folder should be on the same level as project folder (i.e. sibling folder)
                        candidates = glob("../*")
                        candidates = [d for d in candidates if Path(d.lower()).parts[-1] == dep_name.lower()]
                    
                        dep_id = dep.key
                        
                    if not dep_id in self.__processed_deps:
                        self.__processed_deps.add(dep_id)

                        dep.files.append(candidates[0])

                        # recursively create dependencies of dependency
                        dep.dependencies = self._process_package(Path(dep.files[0]))

                        deps.append(dep)

        return deps


    def _find_global_packages_dir(self) -> Path:
        result = subprocess.run(self.__nuget_command + ["locals", "global-packages", "-list"], stdout=subprocess.PIPE)
        result = Path(result.stdout.decode("utf-8").split("global-packages: ")[1].strip())

        return result
    

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
    test_scan = NugetScan("/home/soren/eacg/sample_projects/nuget/ts-dotnet/TrustSource/TS-NetCore-Scanner.Engine")
    test_scan.execute()