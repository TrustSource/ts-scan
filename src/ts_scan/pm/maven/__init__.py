import re
import typing as t
import subprocess

from pathlib import Path
from tempfile import TemporaryDirectory

from xml.etree import ElementTree as ET

from .. import PackageManagerScanner, DependencyScan, Dependency

from .pom_utils import Pom
from .tree_utils import Tree


class MavenScanner(PackageManagerScanner):
    def __init__(self, excludeDepTypes: t.Optional[str] = None, **kwargs):
        super().__init__(**kwargs)

        self.__excludeDepTypes = excludeDepTypes.split(',') if excludeDepTypes else ['test']

        self.__path = None
        self.__nodes = None
        self.__processed_deps = set()

        self.__local_repo = None
        self.__remote_repos = {'central': 'https://repo.maven.apache.org/maven2'}

    @staticmethod
    def name() -> str:
        return 'Maven'

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'mvn'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'excludeDepTypes': {
                'type': str,
                'required': False,
                'help': 'A comma separated list of Maven dependency types to be excluded from the scan'
            }
        }

    def accepts(self, path: Path) -> bool:
        return ((path.is_dir() and (path / 'pom.xml').exists()) or
                (path.is_file() and path.name == 'pom.xml'))

    def scan(self, path: Path) -> t.Optional[DependencyScan]:
        return self._execute(path)

    def _execute(self, path: Path) -> t.Optional['DependencyScan']:
        self.__path = path

        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            self.__local_repo = self._find_local_repository(temp_dir)
            self.__remote_repos.update(self._find_remote_repositories(temp_dir))

            tree_file = temp_dir / 'deps.tree'

            # Dump dependencies tree
            result = self._mvn('dependency:tree',
                               '-DoutputType=text', '-DappendOutput=true', f'-DoutputFile={tree_file}')

            if result.returncode != 0:
                print('Failed to dump dependency tree')
                exit(1)

            # Resolve dependencies sources
            self._mvn('dependency:sources', '-fn')

            scan = None
            if nodes := Tree.from_maven_file(tree_file):
                deps = []
                self.__nodes = nodes

                for n in nodes:
                    if dep := self._create_dep_from_node(n):
                        deps.append(dep)

                name = self._evaluate('project.name', temp_dir)
                groupId = self._evaluate('project.groupId', temp_dir)
                artifactId = self._evaluate('project.artifactId', temp_dir)
                version = self._evaluate('project.version', temp_dir)

                scan = DependencyScan(module=name,
                                      moduleId=f'mvn:{groupId}:{artifactId}' + f':{version}' if version else '',
                                      dependencies=deps)

            return scan

    def _mvn(self, *args, **kwargs) -> subprocess.CompletedProcess:
        return self._exec('-f', self.__path, *args, **kwargs)

    def _evaluate(self, expr: str, output: Path) -> t.Optional[str]:
        out = None
        out_file = output / 'eval.out'
        if self._mvn('help:3.3.0:evaluate', f'-Dexpression={expr}', f'-Doutput={out_file}').returncode == 0:
            with out_file.open('r') as fp:
                out = fp.read()
            out_file.unlink()
        return out

    def _create_dep_from_node(self, node: Tree) -> t.Optional[Dependency]:
        # example coordinates: org.tmatesoft.svnkit:svnkit:jar:1.8.7:provided

        try:
            group_id, artifact_id, _, version, *other = node.data.split(":")

            if len(other) > 0:
                if other[0] in self.__excludeDepTypes:
                    return None

            dep = MavenDependency(group_id=group_id,
                                  artifact_id=artifact_id,
                                  version=version,
                                  remote_repos=self.__remote_repos,
                                  local_repo=self.__local_repo)

            if artifact_id not in self.__processed_deps:
                dep.load()

                if pkg_data := dep.package_data:
                    _, _, checksum = pkg_data

                    if checksum:
                        dep.checksum = checksum[1]

                if src_data := dep.sources_data:
                    repo, pkg, checksum = src_data

                    dep.package_files.append(str(pkg))

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

                for child in node.children:
                    if child_dep := self._create_dep_from_node(child):
                        dep.dependencies.append(child_dep)

            return dep

        except Exception as err:
            print(err)
            raise err

    def _get_project_modules(self, workdir: Path) -> t.List[str]:
        if res := self._evaluate('project.modules', workdir):
            try:
                return [node.text for node in ET.fromstring(res)]
            except:
                pass

        return []

    def _create_effective_pom(self, workdir: Path) -> t.Optional[Pom]:
        pom_file = workdir / 'effective-pom.xml'
        result = self._mvn('help:effective-pom', f'-Doutput={pom_file}')

        if result.returncode == 0:
            return Pom.from_file(pom_file)

        return None

    def _find_local_repository(self, workdir: Path) -> t.Optional[Path]:
        if res := self._evaluate('settings.localRepository', workdir):
            return Path(res)
        else:
            return None

    def _find_remote_repositories(self, workdir: Path) -> t.Dict[str, str]:
        if res := self._evaluate('project.repositories', workdir):
            try:
                repos = {}
                for repo in ET.fromstring(res):
                    _id, _url = None, None
                    for prop in repo:
                        if prop.tag == 'id':
                            _id = prop.text
                        elif prop.tag == 'url':
                            _url = prop.text

                        if _id and _url:
                            repos[_id] = _url
                            _id, _url = None, None
                            break

                return repos

            except:
                pass

        return {}


class MavenDependency(Dependency):
    def __init__(self, group_id: str, artifact_id: str, version: str,
                 remote_repos: t.Dict[str, str],
                 local_repo: t.Optional[Path] = None,
                 **kwargs):

        super().__init__(key=f'mvn:{group_id}:{artifact_id}',
                         name=artifact_id,
                         versions=[version],
                         type='maven',
                         namespace=group_id,
                         **kwargs)

        self.__remote_repos = remote_repos

        if local_repo:
            local_repo_path = local_repo / Path(*group_id.split('.')) / Path(*artifact_id.split('.')) / version
            if local_repo_path.exists():
                self.__local_repo_path = local_repo_path
            else:
                self.__local_repo_path = None

        if self.__local_repo_path and (pom_file := next(self.__local_repo_path.glob('*.pom'), None)):
            self.__pom_file = pom_file
        else:
            self.__pom_file = None

    def load(self):
        if self.__pom_file and (pom := Pom.from_file(self.__pom_file)):
            self.homepageUrl = pom.url
            self.description = pom.description
            self.licenses = pom.licenses

    @property
    def package_data(self) -> t.Optional[t.Tuple[str, Path, t.Optional[t.Tuple[str, str]]]]:
        return self._find_artifact_data('.jar')

    @property
    def sources_data(self) -> t.Optional[t.Tuple[str, Path, t.Optional[t.Tuple[str, str]]]]:
        return self._find_artifact_data('-sources.jar')

    def _find_artifact_data(self, artifact_name_suffix: str) -> t.Optional[
        t.Tuple[str, Path, t.Optional[
            t.Tuple[str, str]]]]:
        """
        Returns sources repository url, sources jar file and optionally its checksum
        :return: (sources_repo, sources_jar, (checksum_alg, checksum))
        """

        if not self.__local_repo_path:
            return None

        remote_repos = self.__local_repo_path / '_remote.repositories'
        if not remote_repos.exists():
            return None

        artifact_data_re = re.compile(rf"([\w.\-]*{artifact_name_suffix})>(.*)=")

        with remote_repos.open('r') as fp:
            for line in fp:
                if m := artifact_data_re.search(line):
                    fname = m.group(1)

                    repo = m.group(2) if m.group(2) else 'central'
                    if repo_url := self.__remote_repos.get(repo, None):
                        checksum = (f for f in self.__local_repo_path.glob(f'{fname}.*')
                                    if any(f.suffix.startswith(a) for a in ['.sha', '.md5']))

                        if checksum := next(checksum, None):
                            alg = checksum.suffix[1:]
                            with checksum.open('r') as checksum_fp:
                                checksum = alg, next(checksum_fp, None)

                        return repo_url, self.__local_repo_path / fname, checksum

        return None
