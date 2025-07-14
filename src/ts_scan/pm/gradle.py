import re
import typing as t

from pathlib import Path

from .maven.pom_utils import Pom
from . import PackageManagerScanner, DependencyScan, Dependency
from ..cli import msg


class GradleScanner(PackageManagerScanner):
    def __init__(self, configuration: str, **kwargs):
        super().__init__(**kwargs)

        self.configuration = configuration

        self.__gradle_cache = Path.home() / '.gradle' / 'caches' / 'modules-2' / 'files-2.1'
        self.__processed_deps = set()

    @staticmethod
    def name() -> str:
        return "Gradle"

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'gradle'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'configuration': {
                'type': str,
                'required': True,
                'help': 'Specify the Gradle configuration to scan (e.g., "compileClasspath", "runtimeClasspath")'
            }
        }

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and (path / 'build.gradle').exists() or (path / 'build.gradle.kts').exists()

    def scan(self, path: Path) -> t.Optional[DependencyScan]:
        res = self._exec('dependencies', f'--configuration={self.configuration}', '--console=plain',
                         cwd=path,
                         capture_output=True)

        if not self.__gradle_cache.exists():
            msg.warn(f"Gradle cache not found at {self.__gradle_cache}. Dependency resolution may be incomplete.")

        output = res.stdout.decode('utf-8')
        deps = self.extract_dependencies_from_output(output)

        return DependencyScan(module='unknown', moduleId='gradle:unknown', dependencies=deps)

    def extract_dependencies_from_output(self, output: str) -> t.List[Dependency]:
        """
        Extracts the dependency tree from Gradle dependencies task output.
        Returns a nested structure representing parent/child relationships.
        Each node is a dict: {'group': ..., 'name': ..., 'version': ..., 'children': [...]}
        Handles version notations like ':1.2.0', ':1.2.0 -> 1.7.0', '-> 1.6.6'.
        """

        # Matches:
        #   +--- group:name:version
        #   +--- group:name:version1 -> version2
        #   +--- group:name -> version
        dep_pattern = re.compile(
            r"^([| ]*)([+\\]---) ([^:\s]+):([^:\s]+)(?::(\S+))?(?: -> (\S+))?"
        )

        roots = []
        stack = []

        for line in output.splitlines():
            match = dep_pattern.match(line)
            if not match:
                continue
            prefix, _, group, name, version1, version2 = match.groups()

            # Determine resolved version
            if version2:
                version = version2
            elif version1:
                version = version1
            else:
                version = ""

            dep = self.create_dependency(group, name, version)
            
            # Each level is determined by the number of 5-char blocks in the prefix
            level = 0
            i = 0
            while i + 5 <= len(prefix):
                level += 1
                i += 5

            if level == 0:
                roots.append(dep)
                stack = [dep]
            else:
                while len(stack) > level:
                    stack.pop()
                stack[-1].dependencies.append(dep)
                stack.append(dep)

        return roots

    def create_dependency(self, group: str, name: str, version: str) -> Dependency:
        dep = GradleDependency(group=group, name=name, version=version,
                               local_repo=self.__gradle_cache)

        if dep.key not in self.__processed_deps:
            dep.load()

            if src_data := dep.sources_data:
                dep.package_files.append(str(src_data))

            self.__processed_deps.add(dep.key)

        return dep


class GradleDependency(Dependency):
    def __init__(self, group: str, name: str, version: str,
                 local_repo: t.Optional[Path] = None,
                 **kwargs):

        # TODO: analyse dependency source to identify pkg type more accurately
        super().__init__(key=f'mvn:{group}:{name}',
                         name=name,
                         versions=[version],
                         type='maven',
                         namespace=group,
                         **kwargs)

        if local_repo:
            local_repo_path = local_repo / Path(group) / Path(name) / version
            if local_repo_path.exists():
                self.__local_repo_path = local_repo_path
            else:
                self.__local_repo_path = None

        if self.__local_repo_path and (pom_file := next(self.__local_repo_path.rglob('*.pom'), None)):
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
        return next(self.__local_repo_path.rglob('*.jar'), None)

    @property
    def sources_data(self) -> t.Optional[Path]:
        return next(self.__local_repo_path.rglob('*-sources.jar'), None)
