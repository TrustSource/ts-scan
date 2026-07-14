import json
import re
import typing as t

from pathlib import Path
from subprocess import CalledProcessError
from typing_extensions import NotRequired, TypedDict

from . import Dependency, DependencyScan, PackageManagerScanner
from ..cli import msg


class PubPackage(TypedDict):
    name: str
    version: NotRequired[str]
    kind: NotRequired[str]
    source: NotRequired[str]
    dependencies: NotRequired[t.List[str]]
    directDependencies: NotRequired[t.List[str]]
    devDependencies: NotRequired[t.List[str]]


class PubDeps(TypedDict):
    root: NotRequired[str]
    packages: t.List[PubPackage]


class DartScanner(PackageManagerScanner):
    """Scan Dart and Flutter projects using pub's machine-readable graph."""

    def __init__(self, includeDevDependencies: bool = False, **kwargs: t.Any):
        super().__init__(**kwargs)
        self.includeDevDependencies = includeDevDependencies

    @staticmethod
    def name() -> str:
        return "Dart"

    @staticmethod
    def executable() -> t.Optional[str]:
        return "dart"

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            "includeDevDependencies": {
                "default": False,
                "is_flag": True,
                "help": "Include Dart development dependencies in the scan results",
            }
        }

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and (path / "pubspec.yaml").exists()

    def scan(self, src: t.Union[str, Path]) -> t.Optional[DependencyScan]:
        path = Path(src)
        args = ["pub", "deps", "--json"]

        use_flutter = self._uses_flutter(path)
        if use_flutter:
            msg.info("Flutter SDK detected. Scanning dependencies using Flutter...")

        try:
            result = self._exec(
                *args,
                cwd=path,
                capture_output=True,
                executable_override="flutter" if use_flutter else "dart",
            )
        except CalledProcessError as error:
            if use_flutter or not self._error_requires_flutter(error):
                raise
            msg.info(
                "Flutter SDK requirement detected. Retrying dependency scan using Flutter..."
            )
            result = self._exec(
                *args,
                cwd=path,
                capture_output=True,
                executable_override="flutter",
            )
        stdout = result.stdout
        if not stdout:
            return None
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8")

        data = t.cast(PubDeps, json.loads(stdout))
        return self._scan_from_pub_deps(data, path, self.includeDevDependencies)

    @staticmethod
    def _uses_flutter(path: Path) -> bool:
        if (path / ".metadata").is_file():
            return True

        pubspec_path = path / "pubspec.yaml"
        if not pubspec_path.is_file():
            return False

        pubspec = pubspec_path.read_text(encoding="utf-8", errors="replace")
        block_dependency = re.search(
            r"(?m)^[ \t]+sdk[ \t]*:[ \t]*flutter[ \t]*(?:#.*)?$", pubspec
        )
        inline_dependency = re.search(
            r"(?i)flutter\s*:\s*\{[^}]*\bsdk\s*:\s*flutter\b", pubspec
        )
        return block_dependency is not None or inline_dependency is not None

    @staticmethod
    def _error_requires_flutter(error: CalledProcessError) -> bool:
        output = b""
        for value in (error.stdout, error.stderr):
            if isinstance(value, bytes):
                output += value
            elif isinstance(value, str):
                output += value.encode("utf-8", errors="replace")

        message = output.decode("utf-8", errors="replace").lower()
        return "requires the flutter sdk" in message or "use `flutter pub`" in message

    @staticmethod
    def _scan_from_pub_deps(
        data: PubDeps,
        path: Path,
        include_dev_dependencies: bool = False,
    ) -> t.Optional[DependencyScan]:
        packages = {
            package["name"]: package
            for package in data.get("packages", [])
            if package.get("name")
        }

        root_name = data.get("root")
        root_package = packages.get(root_name) if root_name is not None else None
        if root_package is None:
            root_package = next(
                (package for package in packages.values() if package.get("kind") == "root"),
                None,
            )
        if root_package is None:
            return None

        workspace_roots = [
            package
            for package in packages.values()
            if package.get("kind") == "root" and package is not root_package
        ]
        dependency_cache: t.Dict[str, Dependency] = {}

        def create_dependency(package: PubPackage, ancestors: t.Set[str]) -> Dependency:
            name = package["name"]
            if cached_dependency := dependency_cache.get(name):
                return cached_dependency

            dep = Dependency(key=f"pub:{name}", name=name, type="pub")
            dependency_cache[name] = dep

            if version := package.get("version"):
                dep.versions.append(str(version))

            child_names = package.get("dependencies", [])
            if package.get("kind") == "root" and not include_dev_dependencies:
                direct_dependencies = package.get("directDependencies")
                if direct_dependencies:
                    child_names = direct_dependencies
                else:
                    child_names = [
                        child_name
                        for child_name in child_names
                        if packages.get(child_name, {}).get("kind") != "dev"
                    ]

            for child_name in child_names:
                if child_name in ancestors:
                    continue
                if child := packages.get(child_name):
                    dep.dependencies.append(create_dependency(child, ancestors | {name}))

            return dep

        if workspace_roots and not root_package.get("dependencies"):
            dependencies = [
                create_dependency(package, set()) for package in workspace_roots
            ]
            return DependencyScan(
                module=root_package["name"],
                moduleId=f'pub:{root_package["name"]}',
                dependencies=dependencies,
            )

        root = create_dependency(root_package, set())
        root.package_files.append(str(path.resolve()))
        return DependencyScan.from_dep(root)
