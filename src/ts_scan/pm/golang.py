import json
import requests
import typing as t

from pathlib import Path


from ts_scan_core import DependencyScan, Dependency
from . import PackageManagerScanner, PackageFileNotFoundError


class GolangScanner(PackageManagerScanner):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__processed_deps = set()

    @staticmethod
    def name() -> str:
        return "Golang"

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'go'

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and (path / 'go.mod').exists()

    def scan(self, path: Path) -> t.Optional[DependencyScan]:
        if root := GoDependency.load_from_package(path):

            # Generate go.sum if it doesn't exist
            go_sum_path = path / "go.sum"
            if not go_sum_path.exists():
                try:
                    self._exec('mod', 'download', cwd=path)
                except:
                    pass  # Continue even if download fails

            # Get all modules first
            modules_map = {}
            try:
                result = self._exec('list', '-m', '-json', 'all', cwd=path, capture_output=True)
                if result.stdout:
                    modules_json = result.stdout.decode('utf-8').strip()
                    modules = []

                    mod_json = ''
                    for line in modules_json.split('\n'):
                        mod_json += line
                        try:
                            modules.append(json.loads(mod_json))
                            mod_json = ''
                        except json.JSONDecodeError:
                            continue

                    # Build modules map
                    for mod in modules:
                        if 'Path' in mod:
                            dep = GoDependency(mod['Path'])
                            dep.load_from_module_info(mod)
                            modules_map[mod['Path']] = dep

            except Exception:
                pass  # Continue without module info if go list fails

            # Get dependency graph with deps information
            try:
                result = self._exec('list', '-deps', '-json', './...', cwd=path, capture_output=True)
                if result.stdout:
                    packages_json = result.stdout.decode('utf-8').strip()
                    packages = []

                    pkg_json = ''
                    for line in packages_json.split('\n'):
                        pkg_json += line
                        try:
                            packages.append(json.loads(pkg_json))
                            pkg_json = ''
                        except json.JSONDecodeError:
                            continue

                    # Build dependency relationships
                    self._build_dependency_tree(packages, modules_map, root)

            except Exception:
                # Fallback: just use direct dependencies without transitive relationships
                root.dependencies = [dep for path, dep in modules_map.items()
                                   if path != root.name and not dep.is_main_module]

            # Load metadata for all dependencies
            for dep in self._get_all_dependencies(root):
                if dep.name not in self.__processed_deps:
                    self.__processed_deps.add(dep.name)
                    dep.load_from_proxy()

            return DependencyScan.from_dep(root)

        return None

    def _build_dependency_tree(self, packages: list, modules_map: dict, root: 'GoDependency'):
        """Build the dependency tree from go list -deps output"""
        package_to_module = {}
        module_deps = {}

        # Map packages to their modules and collect imports
        for pkg in packages:
            if 'ImportPath' in pkg and 'Module' in pkg:
                import_path = pkg['ImportPath']
                module_path = pkg['Module']['Path']

                package_to_module[import_path] = module_path

                if module_path not in module_deps:
                    module_deps[module_path] = set()

                # Add imported modules as dependencies
                for imp in pkg.get('Imports', []):
                    if imp in package_to_module:
                        dep_module = package_to_module[imp]
                        if dep_module != module_path and dep_module in modules_map:
                            module_deps[module_path].add(dep_module)

        # Build the dependency tree
        for module_path, deps in module_deps.items():
            if module_path in modules_map:
                module = modules_map[module_path]
                module.dependencies = [modules_map[dep] for dep in deps if dep in modules_map]

        # Set root dependencies (direct dependencies of the main module)
        root.dependencies = [dep for dep in modules_map.values()
                           if not dep.is_main_module and dep.name in module_deps.get(root.name, set())]

    def _get_all_dependencies(self, root: 'GoDependency') -> list:
        """Get all dependencies recursively"""
        all_deps = []
        visited = set()

        def collect_deps(dep):
            if dep.name in visited:
                return
            visited.add(dep.name)
            all_deps.append(dep)
            for child_dep in dep.dependencies:
                collect_deps(child_dep)

        for dep in root.dependencies:
            collect_deps(dep)

        return all_deps


class GoDependency(Dependency):
    def __init__(self, name: str):
        super().__init__(key="golang:" + name, name=name, type='golang')
        self.is_main_module = False

    def load_from_module_info(self, module_info: dict):
        """Load dependency info from go list -m -json output"""
        if version := module_info.get('Version'):
            if version not in self.versions:
                self.versions.append(version)

        if module_info.get('Main'):
            self.is_main_module = True

        if replace := module_info.get('Replace'):
            # Handle module replacement
            if replace_version := replace.get('Version'):
                self.versions = [replace_version]
            if replace_path := replace.get('Path'):
                self.repoUrl = self._infer_repo_url(replace_path)
        else:
            self.repoUrl = self._infer_repo_url(self.name)

    @staticmethod
    def _infer_repo_url(module_path: str) -> str:
        """Infer repository URL from Go module path"""
        # Handle common hosting patterns
        if module_path.startswith('github.com/'):
            return f"https://{module_path}"
        elif module_path.startswith('gitlab.com/'):
            return f"https://{module_path}"
        elif module_path.startswith('bitbucket.org/'):
            return f"https://{module_path}"
        elif module_path.startswith('gopkg.in/'):
            # gopkg.in redirects, try to resolve the actual repo
            parts = module_path.split('/')
            if len(parts) >= 2:
                return f"https://github.com/{parts[1]}/{parts[2].split('.')[0]}"

        return f"https://{module_path}"

    def load_from_dict(self, data: dict):
        """Load dependency info from proxy API response"""
        if version := data.get('Version'):
            if version not in self.versions:
                self.versions.append(version)

        if time := data.get('Time'):
            self.meta['time'] = time

    def load_from_proxy(self):
        """Load package info from Go module proxy"""
        if not self.version:
            return

        try:
            # Use GOPROXY (default is proxy.golang.org)
            base_url = "https://proxy.golang.org"

            # Get module info
            info_url = f"{base_url}/{self.name}/@v/{self.version}.info"
            resp = requests.get(info_url, timeout=10)
            if resp.status_code == 200:
                info_data = resp.json()
                self.load_from_dict(info_data)

            # Try to get additional metadata from go.mod
            mod_url = f"{base_url}/{self.name}/@v/{self.version}.mod"
            resp = requests.get(mod_url, timeout=10)
            if resp.status_code == 200:
                mod_content = resp.text
                self._parse_go_mod(mod_content)

        except Exception:
            pass  # Fail silently if proxy is unavailable

    def _parse_go_mod(self, mod_content: str):
        """Parse go.mod content for additional metadata"""
        lines = mod_content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('//'):
                # Extract description from comments
                comment = line[2:].strip()
                if not self.description and comment:
                    self.description = comment
                    break

    @staticmethod
    def load_from_package(path: Path) -> t.Optional['GoDependency']:
        """Load root package from go.mod file"""
        mod_path = path / 'go.mod'

        if not mod_path.exists():
            raise PackageFileNotFoundError()

        with mod_path.open() as fp:
            content = fp.read()

        # Parse go.mod file
        lines = content.split('\n')
        module_name = None

        for line in lines:
            line = line.strip()
            if line.startswith('module '):
                module_name = line.split('module ')[1].strip()
                break

        if module_name:
            dep = GoDependency(module_name)
            dep.is_main_module = True

            # Try to extract version from git if available
            try:
                import subprocess
                result = subprocess.run(['git', 'describe', '--tags', '--always'],
                                        cwd=path, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    version = result.stdout.strip()
                    if version not in dep.versions:
                        dep.versions.append(version)
            except:
                pass

            return dep

        return None
