"""Conan 2 dependency graphs, resolved by Conan or supplied by the build."""
import json
import re
import subprocess
import typing as t
from pathlib import Path

import click
from packageurl import PackageURL

from . import Dependency, DependencyScan, ExecutableNotFoundError, License, PackageManagerScanner
from ..cli import msg


class ConanScanner(PackageManagerScanner):
    def __init__(self, graphFile: t.Optional[Path] = None,
                 includeBuildDependencies: bool = False,
                 includeTestDependencies: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.graph_file = Path(graphFile) if graphFile is not None else None
        self.include_build = includeBuildDependencies
        self.include_test = includeTestDependencies

    @staticmethod
    def name() -> str:
        return 'Conan'

    @staticmethod
    def executable() -> str:
        return 'conan'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'graphFile': {
                'type': click.Path(exists=True, dir_okay=False, path_type=Path),
                'help': 'Read a Conan 2 graph JSON file instead of invoking Conan'
            },
            'includeBuildDependencies': {
                'default': False, 'is_flag': True,
                'help': 'Include Conan build-context and tool dependencies'
            },
            'includeTestDependencies': {
                'default': False, 'is_flag': True,
                'help': 'Include Conan test dependencies'
            }
        }

    def accepts(self, path: Path) -> bool:
        if path.is_dir():
            return self.graph_file is not None or any(
                (path / name).is_file() for name in ('conanfile.py', 'conanfile.txt'))
        return path.is_file() and (
            path.name in ('conanfile.py', 'conanfile.txt')
            or (self.graph_file is not None and path.resolve() == self.graph_file.resolve()))

    def scan(self, src: t.Union[str, Path]) -> t.Iterable[DependencyScan]:
        source = Path(src).resolve()
        project = source if source.is_dir() else source.parent
        try:
            if self.graph_file is not None:
                data = json.loads(self.graph_file.read_text(encoding='utf-8'))
            else:
                args = ['graph', 'info', str(source), '--format=json']
                if (project / 'conan.lock').is_file():
                    args.append('--lockfile=' + str(project / 'conan.lock'))
                try:
                    result = self._exec(*args, cwd=project, capture_output=True)
                except subprocess.CalledProcessError as err:
                    # Conan requires a default build profile even for graph info.
                    # Bootstrap only a missing default, never a missing custom profile.
                    detail = self._command_error(err)
                    if not re.search(r"default (?:build |host )?profile[^\n]*doesn't exist", detail, re.IGNORECASE):
                        raise
                    msg.info('Conan default profile is missing. Detecting the local build profile...')
                    self._exec('profile', 'detect', '--exist-ok', cwd=project,
                               capture_output=True, forward_args=False)
                    result = self._exec(*args, cwd=project, capture_output=True)
                data = json.loads(result.stdout)
            return [self._from_graph(data, project)]
        except (ExecutableNotFoundError, subprocess.CalledProcessError,
                OSError, ValueError) as err:
            detail = self._command_error(err) if isinstance(err, subprocess.CalledProcessError) else str(err)
            msg.warn(f'Conan scan incomplete: {detail.rstrip(".")}. No resolved scan was produced.')
            return []

    @staticmethod
    def _command_error(err: subprocess.CalledProcessError) -> str:
        output = err.stderr or err.stdout
        if output:
            return (output.decode('utf-8', errors='replace') if isinstance(output, bytes) else output).strip()
        return str(err)

    def _from_graph(self, data: t.Any, project: Path) -> DependencyScan:
        graph = data.get('graph') if isinstance(data, dict) else None
        nodes = graph.get('nodes') if isinstance(graph, dict) else None
        if not isinstance(nodes, dict) or not nodes:
            raise ValueError('Expected a Conan 2 graph.nodes object')
        if graph.get('error'):
            raise ValueError(f"Conan graph resolution failed: {graph['error']}")
        roots = graph.get('root', {'0': None})
        if not isinstance(roots, dict) or len(roots) != 1:
            raise ValueError('Expected one Conan graph root')
        root_id = next(iter(roots))
        if root_id not in nodes:
            raise ValueError('Conan graph root is missing')
        for node in nodes.values():
            if not isinstance(node, dict) or not isinstance(node.get('dependencies', {}), dict):
                raise ValueError('Invalid Conan graph node')
            for target, edge in node.get('dependencies', {}).items():
                if target not in nodes or not isinstance(edge, dict):
                    raise ValueError('Invalid Conan dependency edge or missing target')

        def build(node_id: str, ancestors: t.Set[str]) -> Dependency:
            node = nodes[node_id]
            name = node.get('name')
            version = node.get('version')
            ref = node.get('ref')
            if isinstance(ref, str) and '/' in ref:
                name_ref, version_ref = ref.split('#', 1)[0].split('@', 1)[0].split('/', 1)
                name = name or name_ref
                version = version or version_ref
            if not name:
                if node_id != root_id:
                    raise ValueError('Conan package name is missing')
                name = project.name
            if not isinstance(name, str) or (version is not None and not isinstance(version, str)):
                raise ValueError('Invalid Conan package name or version')
            qualifiers = {key: str(node[key]) for key in ('user', 'channel', 'rrev', 'prev')
                          if node.get(key) is not None}
            if isinstance(ref, str):
                base, _, revision = ref.partition('#')
                if revision:
                    qualifiers.setdefault('rrev', revision.split('%', 1)[0])
                if '@' in base:
                    user_channel = base.split('@', 1)[1].split('/')
                    if len(user_channel) != 2:
                        raise ValueError('Invalid Conan user/channel reference')
                    for key, value in zip(('user', 'channel'), user_channel):
                        if value:
                            qualifiers.setdefault(key, value)
            for field in ('settings', 'options'):
                values = node.get(field) or {}
                if not isinstance(values, dict):
                    raise ValueError(f'Invalid Conan {field}')
                qualifiers.update({str(k).lower(): str(v) for k, v in values.items() if v is not None})
            purl = PackageURL(type='conan', name=name, version=str(version) if version else None,
                              qualifiers=qualifiers)
            dep = Dependency.create_from_purl(purl)
            if dep is None:
                raise ValueError('Invalid Conan package reference')
            dep.description = node.get('description') or ''
            dep.homepageUrl = node.get('homepage') or ''
            dep.repoUrl = node.get('url') or ''
            licenses = node.get('license') or []
            if isinstance(licenses, str):
                licenses = [licenses]
            if not isinstance(licenses, list) or any(not isinstance(lic, str) for lic in licenses):
                raise ValueError('Invalid Conan license metadata')
            dep.licenses = [License(name=lic) for lic in licenses]
            dep.meta['conan'] = {key: node[key] for key in (
                'ref', 'context', 'test', 'package_id', 'rrev', 'prev', 'settings', 'options',
                'remote', 'binary', 'package_type', 'system_requires', 'python_requires') if key in node}
            if node_id == root_id:
                dep.package_files = [str(project)]
            for target, edge in node.get('dependencies', {}).items():
                child = nodes[target]
                if edge.get('direct') is not True or edge.get('skip'):
                    continue
                if not self.include_build and (edge.get('build') or child.get('context') == 'build'):
                    continue
                if not self.include_test and (edge.get('test') or child.get('test')):
                    continue
                if target in ancestors:
                    msg.warn(f'Conan dependency cycle at {target}; omitting the cyclic edge.')
                    continue
                dep.dependencies.append(build(target, ancestors | {target}))
            return dep

        root = build(root_id, {root_id})
        scan = DependencyScan.from_dep(root)
        # Build settings identify package variants, not the project/module itself.
        module_qualifiers = {key: value for key, value in root.qualifiers.items()
                             if key in ('user', 'channel')}
        module_purl = PackageURL(type='conan', name=root.name, qualifiers=module_qualifiers)
        module_dep = Dependency.create_from_purl(module_purl)
        if module_dep is not None:
            scan.moduleId = module_dep.key
        return scan
