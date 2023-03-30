import os
import subprocess

# TODO: change to igraph library, since graph-tool is not available on PyPI
from graph_tool.all import load_graph, Graph, Vertex

from pathlib import Path
from typing import Iterable, Optional, Tuple, List
from glob import glob

from defusedxml import ElementTree

from . import DependencyScan, Dependency, License


def scan(path: Path) -> Optional[DependencyScan]:
    _scan = MavenScan(path)
    _scan.execute()

    if len(_scan) > 0: return _scan


class MavenScan(DependencyScan):
    def __init__(self, path: Path):
        super().__init__()

        self.__path = path
        self.__processed_deps = set()
        self.__module = None
        self.__module_id = None
        self.__graph = None
        self.__local_rep = None

        self.__dependencies = []

    @property
    def module(self) -> str:
        """returns the module name, i.e. maven artifact id"""
        return self.__module
    
    @property
    def moduleId(self) -> str:
        """returns the module id, i.e. maven key group_id:artifact_id"""
        return self.__module_id
    
    @property
    def dependencies(self) -> Iterable['Dependency']:
        return self.__dependencies
    

    def __len__(self):
        return len(self.dependencies)
    
    
    def execute(self):
        os.chdir(self.__path)
        os.system("mvn dependency:tree -DoutputType=dot -DoutputFile=deps.dot")

        self.__local_rep = _find_local_repository()

        self.__graph = g = load_graph("deps.dot")

        os.remove("deps.dot")
        
        root = self._find_root(g)

        group_id, artifact_id, *_ = self._vertex_name(root, g)
        self.__module = artifact_id
        self.__module_id = group_id + ":" + artifact_id

        self.__dependencies = [self._create_dep_from_vertex(child) for child in root.out_neighbors()]


    def _find_root(self, g: Graph) -> Vertex:
        vertex = g.vertex(0)
        depth = 0

        while depth < 100:
            parents = list(vertex.in_neighbors())

            if len(parents) == 0:
                return vertex
            
            else:
                vertex = parents[0]

        raise ValueError("dependency graph not a tree or too deep")


    def _vertex_name(self, v: Vertex, g: Graph) -> str:
        return g.vertex_properties["vertex_name"][v]
    

    def _create_dep_from_vertex(self, v: Vertex) -> Dependency:
        # example coordinates: org.tmatesoft.svnkit:svnkit:jar:1.8.7:provided

        coords = self._vertex_name(v, self.__graph)
        print(coords) 
        group_id, artifact_id, *_, version, _ = coords.split(":")

        key = group_id + ":" + artifact_id
        
        dep = Dependency(key=key, name=artifact_id)
        dep.versions.append(version)

        # try to resolve coordinates to file location and query the artifact's pom for more metadata
        try:
            path = _artifact_dir_from_coords(coords, self.__local_rep)
            pom = glob(str(path / "*.pom"))[0]

            url, licenses = _parse_pom(pom)

            dep.homepageUrl = url
            dep.licenses = licenses

        except:
            pass

        if artifact_id not in self.__processed_deps:
            self.__processed_deps.add(artifact_id)

            dep.dependencies = [self._create_dep_from_vertex(child) for child in v.out_neighbors()]

        return dep
    

def _find_local_repository() -> Path:
    result = subprocess.run(["mvn", "help:evaluate", "-Dexpression=settings.localRepository", "-q", "-DforceStdout=true"], stdout=subprocess.PIPE)

    return Path(result.stdout.decode("utf-8"))


_N_FAIL = 0
_N_SUCCESS = 0

def _artifact_dir_from_coords(coords: str, local_rep: Path) -> Path:
    global _N_FAIL, _N_SUCCESS

    group_id, artifact_id, *_, version, _ = coords.split(":")

    group_path = Path(*group_id.split("."))
    artifact_path = Path(*artifact_id.split("."))

    full_path = local_rep / group_path / artifact_path / version

    if full_path.exists():
        _N_SUCCESS += 1
        return full_path
    else:
        _N_FAIL += 1
        raise FileNotFoundError(f"The directory for {coords} is not at the suspected location: {full_path}")
    

def _parse_pom(path: Path) -> Tuple[str, List["License"]]:
    tree = ElementTree.parse(path)
    namespaces = {'xmlns' : 'http://maven.apache.org/POM/4.0.0'}

    url = tree.find("/xmlns:url", namespaces=namespaces).text

    license_names = tree.findall("/xmlns:licenses/xmlns:license/xmlns:name", namespaces=namespaces)
    license_urls = tree.findall("/xmlns:licenses/xmlns:license/xmlns:url", namespaces=namespaces)

    licenses = [License(n.text.strip(), u.text.strip()) for n, u in zip(license_names, license_urls)]

    return url, licenses

if __name__ == "__main__":
    test_scan = scan("/home/soren/eacg/sample_projects/maven/maven-project-example")