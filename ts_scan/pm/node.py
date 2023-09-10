import os
import json
import requests
from semantic_version import Version, NpmSpec

from pathlib import Path
from typing import Iterable, Optional


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
        self.__lockfile_content = None
        self.__abs_module_path = Path(os.path.abspath(path))

        self.__lookup = {}
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
    

    def execute(self):
        os.chdir(self.__path)
        os.system("npm install")

        with open(self.__path / "package-lock.json") as lockfile:
            self.__lockfile_content = json.load(lockfile)


        #self.__dependencies = self._flat_deps_from_lockfile(self.__path / "package-lock.json")

        # first build dictionary that is indexable by name
        self.__lookup = self._dict_from_lock(self.__lockfile_content)

        # then traverse graph as described in lockfile
        self.__dependencies = self._dep_from_lock(self.__lockfile_content).dependencies


    @staticmethod
    def _dict_from_lock(lock: dict) -> dict:
        deps_dict = {}

        for dep_path, dep_dict in lock["packages"].items():
            name = dep_path.split("/")[-1]
            version = dep_dict["version"]

            deps_dict.setdefault(name, {})
            deps_dict[name][version] = dep_dict
            deps_dict[name][version]["_path"] = dep_path

        return deps_dict
    

    def _dep_from_lock(self, lock: dict, package_path: str = "") -> Dependency:
        name = package_path.split("/")[-1]
        version = lock["packages"][package_path]["version"]

        dep = Dependency("npm:" + name, name)
        dep.versions.append(version)

        dep_dir = self.__abs_module_path / package_path
        dep_files = dep_dir.rglob("**")
        dep_files = [p for p in dep_files if p.is_file()]

        dep.files.extend(dep_files)

        if name + version not in self.__processed_deps:
            self.__processed_deps.add(name + version)
            print(f"Getting metadata for {name} {version}...", end="", flush=True)

            meta = self._metadata_from_registry(name, version)

            if meta:
                dep.licenses = meta.licenses
                dep.description = meta.description
                dep.homepageUrl = meta.homepageUrl
                dep.repoUrl = meta.repoUrl
                print(" Success!")
            else:
                print(" Failed!")

            for dep_name, dep_version_range in lock["packages"][package_path].get("dependencies", {}).items():
                dep_path = None

                # find appropriate dependency version
                for dep_version, dep_version_dict in self.__lookup[dep_name].items():
                    dep_path = dep_version_dict["_path"]

                    if dep_version_range == "latest":
                        break

                    try:
                        range_spec = NpmSpec(dep_version_range)

                    except ValueError:
                        range_spec = NpmSpec("")

                    if Version(dep_version) in range_spec:
                        break

                if dep_path:
                    dep.dependencies.append(
                        self._dep_from_lock(self.__lockfile_content, dep_path)
                    )

        return dep


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


        dep = Dependency(key=f"npm:{name}", name=name, purl_type='npm')

        dep.versions.append(meta.get("version", ""))

        dep.description = meta.get("description", "")
        dep.homepageUrl = meta.get("homepage", "")
        dep.repoUrl = meta.get("repository", {}).get("url", "")

        dep.licenses.append(License(meta.get("license")))

        return dep

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_scan = NodeScan(Path(sys.argv[1]))
        test_scan.execute()

        for dep in test_scan.dependencies:
            print(dep.files)
    else:
        print('No path provided')