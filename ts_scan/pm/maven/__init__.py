import re
import subprocess
import typing as t

from pathlib import Path
from tempfile import TemporaryDirectory

from .. import DependencyScan, Dependency

from .pom_utils import Pom
from .tree_utils import Tree


def scan(path: Path) -> t.Optional[DependencyScan]:
    _scan = MavenScan(path)
    _scan.execute()

    return _scan if _scan.dependencies else None


class MavenScan(DependencyScan):
    def __init__(self, path: Path):
        super().__init__()

        self.__path = path
        self.__processed_deps = set()
        self.__module = None
        self.__module_id = None
        self.__tree = None

        self.__local_repo = None

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
    def dependencies(self) -> t.Iterable['Dependency']:
        return self.__dependencies


    def execute(self):
        self.__local_repo = self._find_local_repository()

        with TemporaryDirectory() as temp_dir:
            tree_file = Path(temp_dir)/'deps.tree'

            # Dump dependencies tree
            subprocess.run(
                ['mvn', 'dependency:tree', '-DoutputType=text', f'-DoutputFile={tree_file}'],
                cwd=self.__path,
                capture_output=True)

            # Resolve dependencies sources
            subprocess.run(
                ['mvn', 'dependency:sources'],
                cwd=self.__path,
                capture_output=True)

            if tree := Tree.from_maven_file(tree_file):
                self.__tree = tree

                dep = self._create_dep_from_node(tree)

                self.__module = dep.name
                self.__module_id = dep.key
                self.__dependencies = dep.dependencies


    def _create_dep_from_node(self, node: Tree) -> Dependency:
        # example coordinates: org.tmatesoft.svnkit:svnkit:jar:1.8.7:provided

        group_id, artifact_id, _, version, *_ = node.data.split(":")

        dep = MavenDependency(group_id=group_id, artifact_id=artifact_id, version=version, local_repo=self.__local_repo)

        if artifact_id not in self.__processed_deps:
            dep.load()

            if pkg_data := dep.package_data:
                _, _, checksum = pkg_data

                if checksum:
                    dep.checksum = checksum[1]

            if src_data := dep.sources_data:
                repo, pkg, checksum = src_data
                download_url = f'{repo}/{pkg.relative_to(self.__local_repo)}'

                sources_meta = {
                    'url': download_url
                }

                if checksum:
                    sources_meta['checksum'] = {
                        checksum[0]: checksum[1]
                    }

                dep.meta['sources'] = sources_meta

            self.__processed_deps.add(artifact_id)
            dep.dependencies = [self._create_dep_from_node(child) for child in node.children]

        return dep


    def _create_effective_pom(self) -> t.Optional[Pom]:
        with TemporaryDirectory() as temp_dir:
            pom_file = Path(temp_dir)/'effective-pom.xml'

            result = subprocess.run(
                ['mvn', 'help:effective-pom', f'-Doutput={pom_file}'],
                cwd = self.__path,
                capture_output=True
            )

            if result.returncode == 0:
                return Pom.from_maven_file(pom_file)

        return  None

    def _find_local_repository(self) -> t.Optional[Path]:
        result = subprocess.run(
            ['mvn', 'help:evaluate', '-Dexpression=settings.localRepository', '-q', '-DforceStdout=true'],
            cwd=self.__path,
            capture_output=True,
            text=True,
            encoding='utf-8'
            )

        return Path(result.stdout) if result.returncode == 0 else None


class MavenDependency(Dependency):
    def __init__(self, group_id: str, artifact_id: str, version: str, local_repo: t.Optional[Path] = None, **kwargs):
        super().__init__(key=f'mvn:{group_id}:{artifact_id}',
                         name=artifact_id,
                         versions=[version],
                         purl_type='maven',
                         purl_namespace=group_id, **kwargs)

        if local_repo:
            self.__local_repo_path = local_repo / Path(*group_id.split('.')) / Path(*artifact_id.split('.')) / version

            if self.__local_repo_path.exists() and (pom := next(self.__local_repo_path.glob('*.pom'), None)):
                self.__pom: t.Optional[Pom] = Pom.from_maven_file(pom)
            else:
                self.__pom: t.Optional[Pom] = None

    def load(self):
        if self.__pom:
            self.homepageUrl = self.__pom.url
            self.description = self.__pom.description
            self.licenses = self.__pom.licenses

        if self.__local_repo_path:
            self.files.extend(self.__local_repo_path.rglob('**'))

    @property
    def package_data(self) -> t.Optional[t.Tuple[str, Path, t.Optional[t.Tuple[str, str]]]]:
        return self._find_artifact_data('.jar')

    @property
    def sources_data(self)-> t.Optional[t.Tuple[str, Path, t.Optional[t.Tuple[str, str]]]]:
        return self._find_artifact_data('-sources.jar')


    def _find_artifact_data(self, artifact_name_suffix: str) -> t.Optional[t.Tuple[str, Path, t.Optional[t.Tuple[str, str]]]]:
        """
        Returns sources repository url, sources jar file and optionally its checksum
        :return: (sources_repo, sources_jar, (checksum_alg, checksum))
        """

        if not self.__local_repo_path:
            return None

        remote_repos = self.__local_repo_path/'_remote.repositories'
        if not remote_repos.exists():
            return None

        repos = {'central': 'https://repo.maven.apache.org/maven2'}
        if self.__pom:
            repos.update(self.__pom.repositories)

        with remote_repos.open('r') as fp:
            for line in fp:
                if m := re.search(f"([\w\d\.\-]*{artifact_name_suffix})>(.*)=", line):
                    fname = m.group(1)

                    repo = m.group(2) if m.group(2) else 'central'
                    if repo_url := repos.get(repo, None):
                        checksum = (f for f in self.__local_repo_path.glob(f'{fname}.*')
                                        if any(f.suffix.startswith(a) for a in ['.sha', '.md5']))

                        if checksum := next(checksum, None):
                            alg = checksum.suffix[1:]
                            with checksum.open('r') as checksum_fp:
                                checksum = alg, next(checksum_fp, None)

                        return repo_url, self.__local_repo_path/fname, checksum

        return None

