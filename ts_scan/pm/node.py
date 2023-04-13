import os
import json
import requests

from pathlib import Path
from typing import Iterable, Optional, List

from tqdm import tqdm

from . import DependencyScan, Dependency, License


def scan(path: Path) -> Optional[DependencyScan]:
    _scan = NodeScan(path)
    _scan.execute()

    return _scan if _scan.dependencies else None


class NodeScan(DependencyScan):
    def __init__(self, path: Path):
        super().__init__()

        self.__path = Path(path)
        self.__processed_deps = set()
        self.__module = None
        self.__module_id = None
        self.__failed_requests = 0
        
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
        return len(self.__dependencies)
    

    def execute(self):
        os.chdir(self.__path)
        os.system("npm install")

        self.__dependencies = self._flat_deps_from_lockfile(self.__path / "package-lock.json")


    def _flat_deps_from_lockfile(self, lockfile: Path) -> List[Dependency]:
        with open(lockfile, "r") as f:
            deps_dict = json.load(f)

        deps = []

        print("Getting metadata for dependencies:")

        for dep_path, dep_dict in tqdm(deps_dict["packages"].items()):
            name = dep_path.split("/")[-1]
            if name != "":
                dep = self._metadata_from_registry(name, dep_dict["version"])

                if dep: 
                    deps.append(dep)

        return deps


    def _metadata_from_registry(self, name: str, version: str) -> Optional[Dependency]:
        template = "https://registry.npmjs.org/{}/{}"

        try:
            result = requests.get(template.format(name, version))

            if result.status_code != 200:
                raise requests.ConnectionError()

            meta = json.loads(result.text)
            
        except requests.ConnectionError:
            self.__failed_requests += 1
            return None


        dep = Dependency("npm:" + name, name)

        dep.versions.append(meta["version"])

        dep.description = meta.get("description", "")
        dep.homepageUrl = meta.get("homepage", "")
        dep.repoUrl = meta.get("repository", {}).get("url", "")

        dep.licenses.append(License(meta.get("license")))

        return dep

if __name__ == "__main__":
    test_scan = NodeScan("/home/soren/eacg/sample_projects/node/ts-node-client")
    test_scan.execute()