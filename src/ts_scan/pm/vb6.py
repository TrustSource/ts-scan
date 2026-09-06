import os
import re
import typing as t

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from . import Dependency, DependencyScan, PackageManagerScanner
from .vb6_catalog import VB6_RUNTIME_FILE, VB6_RUNTIME_VERSION, lookup as catalog_lookup


@dataclass
class VB6Project:
    path: Path
    name: str
    output_name: str
    project_type: str
    version: t.Optional[str]
    entries: t.List[t.Tuple[str, str]]


class VB6Scanner(PackageManagerScanner):
    """Scan classic Visual Basic 6 project and project-group files."""

    #: Project types whose output is executed by the VB6 runtime.
    RUNTIME_PROJECT_TYPES = {'exe', 'oleexe', 'oledll', 'control'}

    SOURCE_KEYS = {
        'class',
        'designer',
        'form',
        'module',
        'propertypage',
        'usercontrol',
        'userdocument',
    }
    REFERENCE_RE = re.compile(
        r'^(?:\*\\[A-Za-z])?'
        r'(?P<guid>\{[^}]+\})#'
        r'(?P<version>[^#]+)#'
        r'(?P<lcid>[^#;]*)(?P<separator>[#;])'
        r'(?P<remainder>.*)$'
    )
    DECLARE_RE = re.compile(
        r'^\s*(?:(?P<scope>Public|Private|Friend)\s+)?'
        r'Declare\s+(?:PtrSafe\s+)?'
        r'(?P<kind>Function|Sub)\s+'
        r'(?P<procedure>[A-Za-z_][A-Za-z0-9_]*)\s+'
        r'Lib\s+"(?P<library>[^"]+)"'
        r'(?:\s+Alias\s+"(?P<alias>[^"]+)")?',
        re.IGNORECASE | re.MULTILINE,
    )

    def __init__(self, excludeRuntime: bool = False, **kwargs: t.Any):
        super().__init__(**kwargs)
        self.excludeRuntime = excludeRuntime

    @staticmethod
    def name() -> str:
        return 'VB6'

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'excludeRuntime': {
                'default': False,
                'is_flag': True,
                'help': 'Do not add the implicit Visual Basic 6 runtime (MSVBVM60.DLL) '
                        'to VB6 project scans',
            }
        }

    def accepts(self, path: Path) -> bool:
        if path.is_file():
            return path.suffix.casefold() in ('.vbp', '.vbg')
        if not path.is_dir():
            return False
        return any(self._project_files(path)) or any(self._group_files(path))

    def scan(self, src: t.Union[str, Path]) -> t.Iterable[DependencyScan]:
        path = Path(src)
        if path.is_file() and path.suffix.casefold() == '.vbg':
            return [self._scan_group(path)]
        if path.is_file() and path.suffix.casefold() == '.vbp':
            project = self._load_project(path)
            return [
                self._scan_project(project, self._related_project_index(project))
            ]

        groups = list(self._group_files(path))
        if groups:
            return [self._scan_group(group) for group in groups]

        projects = [self._load_project(project) for project in self._project_files(path)]
        project_index = self._project_index(projects)
        return [self._scan_project(project, project_index) for project in projects]

    @staticmethod
    def _read_text(path: Path) -> str:
        data = path.read_bytes()
        try:
            return data.decode('utf-8-sig')
        except UnicodeDecodeError:
            return data.decode('cp1252', errors='replace')

    @staticmethod
    def _unquote(value: str) -> str:
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            return value[1:-1]
        return value

    @classmethod
    def _entries(cls, path: Path) -> t.List[t.Tuple[str, str]]:
        entries = []
        for line in cls._read_text(path).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('[') or '=' not in stripped:
                continue
            key, value = stripped.split('=', 1)
            entries.append((key.strip().casefold(), value.strip()))
        return entries

    @staticmethod
    def _first(entries: t.Iterable[t.Tuple[str, str]], key: str) -> t.Optional[str]:
        normalized_key = key.casefold()
        return next((value for name, value in entries if name == normalized_key), None)

    @classmethod
    def _load_project(cls, path: Path) -> VB6Project:
        entries = cls._entries(path)
        name = cls._unquote(cls._first(entries, 'Name') or path.stem)
        project_type = cls._unquote(cls._first(entries, 'Type') or '')
        output_name = cls._unquote(cls._first(entries, 'ExeName32') or '')
        if not output_name:
            suffix = {
                'control': '.ocx',
                'exe': '.exe',
                'oledll': '.dll',
            }.get(project_type.casefold(), '')
            output_name = f'{name}{suffix}'

        version_parts = [
            cls._unquote(cls._first(entries, key) or '')
            for key in ('MajorVer', 'MinorVer', 'RevisionVer')
        ]
        version = '.'.join(version_parts) if all(version_parts) else None
        return VB6Project(
            path=path.resolve(),
            name=name,
            output_name=output_name,
            project_type=project_type,
            version=version,
            entries=entries,
        )

    @classmethod
    def _group_project_files(cls, group_file: Path) -> t.List[Path]:
        projects = []
        seen = set()
        for key, raw_path in cls._entries(group_file):
            if key not in ('project', 'startupproject'):
                continue
            relative_path = Path(PureWindowsPath(cls._unquote(raw_path)).as_posix())
            project_path = (
                relative_path
                if relative_path.is_absolute()
                else group_file.parent / relative_path
            ).resolve()
            normalized_path = str(project_path).casefold()
            if project_path.is_file() and normalized_path not in seen:
                seen.add(normalized_path)
                projects.append(project_path)
        return projects

    @staticmethod
    def _project_files(path: Path) -> t.Iterable[Path]:
        return sorted(
            (entry for entry in path.iterdir() if entry.suffix.casefold() == '.vbp'),
            key=lambda entry: entry.name.casefold(),
        )

    @staticmethod
    def _group_files(path: Path) -> t.Iterable[Path]:
        return sorted(
            (entry for entry in path.iterdir() if entry.suffix.casefold() == '.vbg'),
            key=lambda entry: entry.name.casefold(),
        )

    @staticmethod
    def _project_index(projects: t.Iterable[VB6Project]) -> t.Dict[str, VB6Project]:
        index = {}
        for project in projects:
            if project.output_name:
                output_name = PureWindowsPath(project.output_name).name.casefold()
                index[output_name] = project
        return index

    @classmethod
    def _related_project_index(cls, project: VB6Project) -> t.Dict[str, VB6Project]:
        """Find sibling project files next to relative referenced outputs."""
        projects = []
        seen = set()
        for key, value in project.entries:
            if key not in ('object', 'reference'):
                continue
            match = cls.REFERENCE_RE.match(value.strip())
            if match is None:
                continue
            remainder = match.group('remainder').strip()
            raw_path = (
                remainder.partition('#')[0]
                if match.group('separator') == '#'
                else remainder
            )
            output_path = cls._resolve_library_path(
                cls._unquote(raw_path.strip()), project.path.parent
            )
            if output_path is None or not output_path.parent.is_dir():
                continue
            for candidate in output_path.parent.iterdir():
                if candidate.suffix.casefold() != '.vbp':
                    continue
                resolved = candidate.resolve()
                if resolved == project.path or resolved in seen:
                    continue
                seen.add(resolved)
                projects.append(cls._load_project(resolved))
        return cls._project_index(projects)

    def _scan_group(self, group_file: Path) -> DependencyScan:
        projects = [
            self._load_project(project_file)
            for project_file in self._group_project_files(group_file)
        ]
        project_index = self._project_index(projects)
        dependencies = [
            self._project_dependency(
                project,
                self._project_dependencies(project, project_index),
            )
            for project in projects
        ]
        return DependencyScan(
            module=group_file.stem,
            moduleId=f'vb:{group_file.stem}',
            dependencies=dependencies,
        )

    def _scan_project(
        self,
        project: VB6Project,
        project_index: t.Mapping[str, VB6Project],
    ) -> DependencyScan:
        return DependencyScan(
            module=project.name,
            moduleId=f'vb:{project.name}',
            dependencies=self._project_dependencies(project, project_index),
        )

    @classmethod
    def _project_dependency(
        cls,
        project: VB6Project,
        dependencies: t.Optional[t.List[Dependency]] = None,
    ) -> Dependency:
        dependency = Dependency(
            key=f'vb:{project.name}',
            name=project.name,
            type='vb',
            dependencies=dependencies or [],
        )
        if project.version:
            dependency.versions.append(project.version)
        dependency.package_files.append(str(project.path.parent))
        dependency.meta.update({
            'dependency_type': 'project',
            'project_file': str(project.path),
            'project_type': project.project_type,
            'output_name': project.output_name,
        })
        for source_key, metadata_key in (
            ('Title', 'title'),
            ('Description', 'description'),
            ('VersionCompanyName', 'company'),
            ('VersionProductName', 'product_name'),
        ):
            value = cls._first(project.entries, source_key)
            if value:
                dependency.meta[metadata_key] = cls._unquote(value)
        return dependency

    def _project_dependencies(
        self,
        project: VB6Project,
        project_index: t.Mapping[str, VB6Project],
    ) -> t.List[Dependency]:
        cls = type(self)
        dependencies: t.Dict[str, Dependency] = {}

        for key, value in project.entries:
            if key not in ('object', 'reference'):
                continue
            parsed = cls._parse_reference(key, value, project)
            if parsed is None:
                continue
            dependency, library_file = parsed
            target_project = project_index.get(library_file.name.casefold())
            if target_project is not None and target_project.path != project.path:
                dependency = cls._project_dependency(target_project)
                dependency.meta['reference'] = parsed[0].meta['references'][0]
            cls._add_dependency(dependencies, dependency)

        for source_file in cls._source_files(project):
            for dependency in cls._declared_libraries(source_file, project):
                library_path = dependency.meta['references'][0]['path']
                target_project = project_index.get(
                    PureWindowsPath(library_path).name.casefold()
                )
                if target_project is not None and target_project.path != project.path:
                    project_dependency = cls._project_dependency(target_project)
                    project_dependency.meta['reference'] = dependency.meta['references'][0]
                    dependency = project_dependency
                cls._add_dependency(dependencies, dependency)

        if (
            not self.excludeRuntime
            and project.project_type.casefold() in cls.RUNTIME_PROJECT_TYPES
        ):
            cls._add_dependency(dependencies, cls._runtime_dependency(project))

        return list(dependencies.values())

    @classmethod
    def _runtime_dependency(cls, project: VB6Project) -> Dependency:
        """The VB6 runtime is an implicit dependency of every compiled VB6 output."""
        runtime_file = PureWindowsPath(VB6_RUNTIME_FILE)
        dependency = cls._library_dependency(
            runtime_file.stem.upper(),
            runtime_file.suffix.lstrip('.'),
            project,
            {
                'reference_type': 'runtime',
                'path': VB6_RUNTIME_FILE,
                'version': VB6_RUNTIME_VERSION,
            },
            VB6_RUNTIME_FILE,
        )
        dependency.meta['dependency_type'] = 'runtime'
        dependency.meta['implicit'] = True
        dependency.versions.append(VB6_RUNTIME_VERSION)
        return dependency

    @staticmethod
    def _add_dependency(
        dependencies: t.MutableMapping[str, Dependency], dependency: Dependency
    ) -> None:
        normalized_key = dependency.key.casefold()
        existing = dependencies.get(normalized_key)
        if existing is None:
            dependencies[normalized_key] = dependency
            return

        for version in dependency.versions:
            if version not in existing.versions:
                existing.versions.append(version)
        for package_file in dependency.package_files:
            if package_file not in existing.package_files:
                existing.package_files.append(package_file)
        references = dependency.meta.get('references', [])
        if references:
            existing.meta.setdefault('references', []).extend(references)

    @classmethod
    def _parse_reference(
        cls, reference_type: str, value: str, project: VB6Project
    ) -> t.Optional[t.Tuple[Dependency, PureWindowsPath]]:
        match = cls.REFERENCE_RE.match(value.strip())
        if match is None:
            return None

        remainder = match.group('remainder').strip()
        if match.group('separator') == '#':
            raw_path, _, display_name = remainder.partition('#')
        else:
            raw_path, display_name = remainder, ''
        raw_path = cls._unquote(raw_path.strip())
        library_file = PureWindowsPath(raw_path)
        library_type = library_file.suffix.lstrip('.').casefold()
        name = library_file.stem
        if not library_type or not name:
            return None

        usage = {
            'reference_type': reference_type,
            'path': raw_path,
            'guid': match.group('guid'),
            'version': match.group('version'),
            'lcid': match.group('lcid'),
        }
        if display_name.strip():
            usage['display_name'] = display_name.strip()

        dependency = cls._library_dependency(
            name, library_type, project, usage, raw_path
        )
        version = match.group('version').strip()
        if version:
            dependency.versions.append(version)
        return dependency, library_file

    @classmethod
    def _source_files(cls, project: VB6Project) -> t.Iterable[Path]:
        seen = set()
        for key, raw_value in project.entries:
            if key not in cls.SOURCE_KEYS:
                continue
            value = raw_value.split(';', 1)[-1] if key in ('class', 'module') else raw_value
            relative_path = Path(PureWindowsPath(cls._unquote(value)).as_posix())
            source_file = (
                relative_path
                if relative_path.is_absolute()
                else project.path.parent / relative_path
            ).resolve()
            if source_file.is_file() and source_file not in seen:
                seen.add(source_file)
                yield source_file

    @classmethod
    def _declared_libraries(
        cls, source_file: Path, project: VB6Project
    ) -> t.Iterable[Dependency]:
        source = re.sub(r'\s+_\r?\n\s*', ' ', cls._read_text(source_file))
        for match in cls.DECLARE_RE.finditer(source):
            raw_path = match.group('library').strip()
            library_file = PureWindowsPath(raw_path)
            library_type = library_file.suffix.lstrip('.').casefold() or 'dll'
            name = library_file.stem or library_file.name
            usage = {
                'reference_type': 'declare',
                'path': raw_path,
                'source_file': str(source_file),
                'procedure': match.group('procedure'),
                'procedure_type': match.group('kind').casefold(),
            }
            if match.group('scope'):
                usage['scope'] = match.group('scope').casefold()
            if match.group('alias'):
                usage['alias'] = match.group('alias')
            yield cls._library_dependency(
                name, library_type, project, usage, raw_path
            )

    @classmethod
    def _library_dependency(
        cls,
        name: str,
        library_type: str,
        project: VB6Project,
        usage: t.Dict[str, str],
        raw_path: str,
    ) -> Dependency:
        dependency = Dependency(
            key=f'lib:{library_type}:{name}',
            name=name,
            type='lib',
            namespace=library_type,
        )
        dependency.meta.update({
            'dependency_type': 'library',
            'library_type': library_type,
            'source_project': str(project.path),
            'references': [usage],
        })
        if catalog_entry := catalog_lookup(name, library_type):
            dependency.description = catalog_entry['title']
            dependency.meta['catalog'] = dict(catalog_entry)
        resolved_path = cls._resolve_library_path(raw_path, project.path.parent)
        if resolved_path is not None:
            dependency.meta['resolved_path'] = str(resolved_path)
            if resolved_path.is_file():
                dependency.package_files.append(str(resolved_path))
        return dependency

    @staticmethod
    def _resolve_library_path(raw_path: str, project_dir: Path) -> t.Optional[Path]:
        windows_path = PureWindowsPath(raw_path)
        if windows_path.is_absolute():
            return Path(str(windows_path)).resolve() if os.name == 'nt' else None
        path = Path(windows_path.as_posix())
        return (project_dir / path).resolve()
