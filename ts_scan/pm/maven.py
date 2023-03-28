import os
import sys

from graph_tool.all import load_graph, Graph, Vertex

from pathlib import Path
from typing import Iterable

#from . import DependencyScan, Dependency, License

#######################################################
# IMPORT BY COPY-PASTE (tm) ONLY FOR TESTING PURPOSES #
# REMOVE AFTER TESTING                                #
#######################################################

class DependencyScan:
    """dummy class for testing purposes"""
    def __init__(self):
        pass

from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Dependency:
    key: str
    name: str

    repoUrl: str = ''
    homepageUrl: str = ''
    description: str = ''
    checksum: str = ''
    private: bool = False

    versions: List[str] = field(default_factory=lambda: [])
    dependencies: List['Dependency'] = field(default_factory=lambda: [])
    licenses: List['License'] = field(default_factory=lambda: [])

    meta: Dict = field(default_factory=lambda: {})

    def __post_init__(self):
        self.__files = []

    @property
    def files(self):
        return self.__files
    
#####################
# END OF COPY-PASTE #
#####################


def scan(path: Path) -> DependencyScan:
    _scan = MavenScan(path)
    _scan.execute()

    return _scan


class MavenScan(DependencyScan):
    def __init__(self, path: Path):
        super().__init__()

        self.__path = path
        self.__processed_deps = set()
        self.__module = None
        self.__module_id = None
        self.__graph = None

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
    
    
    def execute(self):
        os.chdir(self.__path)
        os.system("mvn dependency:tree -DoutputType=dot -DoutputFile=deps.dot")

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

        if artifact_id not in self.__processed_deps:
            self.__processed_deps.add(artifact_id)

            dep.dependencies = [self._create_dep_from_vertex(child) for child in v.out_neighbors()]

        return dep
    

if __name__ == "__main__":
    test_scan = scan("/home/soren/eacg/sample_projects/maven/maven-project-example/")

