# SPDX-FileCopyrightText: 2020 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import os
import re
import sys
import json
import tempfile
import subprocess
import typing as t

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from importlib.metadata import distribution, PackageNotFoundError
from packaging.requirements import Requirement, InvalidRequirement
from packaging.utils import canonicalize_name

from . import (PackageManagerScanner, DependencyScan, Dependency, DependencyResolutionError, ExecutableNotFoundError,
               License, get_license_from_text)


_supported_pkg_files = [
    'setup.py',
    'pyproject.toml'
]

# Upper bound for the pip resolution: an unreachable package index must not block the scan forever
PIP_TIMEOUT_SECONDS = 600


class PypiScanner(PackageManagerScanner):
    def __init__(self,
                 extras: t.Optional[t.Tuple[str, ...]] = None,
                 indexUrl: t.Optional[str] = None,
                 extraIndexUrl: t.Optional[t.Tuple[str, ...]] = None,
                 **kwargs):
        super().__init__(**kwargs)

        self.extras = {canonicalize_name(e.strip()) for ext in extras or () for e in ext.split(',') if e.strip()}
        self.indexUrl = indexUrl
        self.extraIndexUrl = list(extraIndexUrl or ())

        # Canonical package name -> extras for which its requirements were already followed
        self.__expanded: t.Dict[str, t.Set[str]] = {}
        # Canonical package name -> metadata of the resolved distribution (from 'pip install --dry-run --report')
        self.__resolved: t.Dict[str, '_JsonMetadata'] = {}

    @staticmethod
    def name() -> str:
        return "PyPI"

    @classmethod
    def options(cls) -> PackageManagerScanner.OptionsType:
        return super().options() | {
            'extras': {
                'type': str,
                'required': False,
                'multiple': True,
                'help': 'Include optional dependencies of the given extras of the scanned project (comma-separated or repeated)'
            },
            'indexUrl': {
                'type': str,
                'required': False,
                'help': 'Base URL of the package index (PEP 503 simple API) to resolve dependencies from instead of PyPI, '
                        'e.g. a company repository; ${VAR} references are replaced with environment variables'
            },
            'extraIndexUrl': {
                'type': str,
                'required': False,
                'multiple': True,
                'help': 'Additional package index to resolve dependencies from; ${VAR} references are replaced with '
                        'environment variables'
            }
        }

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and any((path / pkg_file).exists() for pkg_file in _supported_pkg_files)

    def scan(self, src: t.Union[str, Path]) -> t.Iterable[DependencyScan]:
        path = Path(src)

        self.__expanded = {}
        self.__resolved, metadata = self._resolve(path)

        if dep := self._create_dep_from_metadata(metadata, extras=self.extras, project_path=path):
            return [DependencyScan.from_dep(dep)]
        else:
            return []

    def _resolve(self, path: Path) -> t.Tuple[t.Dict[str, '_JsonMetadata'], '_JsonMetadata']:
        """
        Resolves the dependencies of the project as 'pip install' would, without installing anything.
        Without access to the package index the dependencies cannot be determined, the scan is aborted then.
        :param path: Project path
        :return: Metadata of the resolved distributions by canonical name and metadata of the project
        """
        index_urls = [_expand_url(url) for url in ([self.indexUrl] if self.indexUrl else []) + self.extraIndexUrl]

        # Index URLs may contain credentials: pass them in the environment, not as arguments,
        # which are visible in the process list and in the representation of a CalledProcessError
        env = dict(os.environ)
        if self.indexUrl:
            env['PIP_INDEX_URL'] = index_urls[0]
        if extra_urls := index_urls[1 if self.indexUrl else 0:]:
            env['PIP_EXTRA_INDEX_URL'] = ' '.join(extra_urls)

        target = str(path.resolve())
        if self.extras:
            target += f'[{",".join(sorted(self.extras))}]'

        with tempfile.TemporaryDirectory() as tmp:
            report_file = Path(tmp) / 'report.json'
            try:
                self._exec('-m', 'pip', 'install', target,
                           '--dry-run', '--ignore-installed', '--quiet', '--no-input',
                           '--disable-pip-version-check', '--report', str(report_file),
                           executable_override=sys.executable,
                           forward_args=False,
                           capture_output=True,
                           text=True,
                           env=env,
                           timeout=PIP_TIMEOUT_SECONDS)

                with report_file.open() as fp:
                    report = json.load(fp)

            except (OSError, ValueError, ExecutableNotFoundError, subprocess.CalledProcessError,
                    subprocess.TimeoutExpired) as err:
                if isinstance(err, subprocess.TimeoutExpired):
                    details = f'pip did not finish within {PIP_TIMEOUT_SECONDS} seconds'
                elif isinstance(err, subprocess.CalledProcessError):
                    lines = [ln.strip() for ln in (err.stderr or '').strip().splitlines() if ln.strip()]
                    details = ' '.join([ln for ln in lines if ln.startswith('ERROR:')][-3:] or lines[-1:])
                    details = _redact_urls(details) or f'pip exited with code {err.returncode}'
                else:
                    details = str(err)

                if index_urls:
                    sources = ', '.join(_redact_url(url) for url in index_urls)
                else:
                    sources = 'the index configured for pip (default: https://pypi.org/simple)'

                raise DependencyResolutionError(
                    f'Cannot resolve the {self.name()} dependencies of {path}: {details.rstrip(".")}. '
                    f'Without access to the package sources of the project ({sources}) its transitive dependencies '
                    f'cannot be determined. Configure the package index with --pypi:indexUrl or with '
                    f'"pypi_indexUrl" in the tsproject.toml of the project.'
                ) from err

        resolved, project = {}, None
        for item in report.get('install', []):
            if (metadata := item.get('metadata')) and (name := metadata.get('name')):
                resolved[canonicalize_name(name)] = _JsonMetadata(metadata)

                if item.get('requested') and 'dir_info' in item.get('download_info', {}):
                    project = resolved[canonicalize_name(name)]

        if project is None:
            raise DependencyResolutionError(f'Cannot resolve the {self.name()} dependencies of {path}: '
                                            'pip did not report the project itself.')

        return resolved, project

    def _create_dep_from_metadata(self, metadata: t.Any,
                                  extras: t.AbstractSet[str] = frozenset(),
                                  project_path: t.Optional[Path] = None) -> Dependency:
        """
        Creates a dependency from the dist package metadate
        :param metadata: PackageMetadata
        :param extras: Extras of the package requested by the dependent package
        :return:
        """
        name = metadata.get('Name', '')
        canonical_name = canonicalize_name(name)

        dep = Dependency(key=f'pypi:{canonical_name}', name=name, type='pypi')

        if version := metadata.get('Version', None):
            dep.versions.append(version)

        reqs = _parse_requirements(metadata.get_all('Requires-Dist', []))

        if (expanded_extras := self.__expanded.get(canonical_name)) is not None:
            # Already processed: only follow the requirements enabled by extras requested for the first time
            if new_extras := set(extras) - expanded_extras:
                known = {canonicalize_name(r.name) for r in _active_requirements(reqs, expanded_extras)}
                expanded_extras.update(new_extras)
                dep.dependencies = [d for req in _active_requirements(reqs, new_extras)
                                    if canonicalize_name(req.name) not in known and (d := self._create_dep(req))]
            return dep

        self.__expanded[canonical_name] = set(extras)

        dep.description = metadata.get('Summary', '')

        if proj_urls := metadata.get_all('Project-URL', []):
            for proj_url in proj_urls:
                proj_url = proj_url.split(',', 1)

                lbl = _normalize_label(proj_url[0].strip())
                url = proj_url[1].strip() if len(proj_url) > 1 else ''

                if lbl in ('source', 'sources', 'repository', 'sourcecode', 'github'):
                    dep.repoUrl = url
                elif lbl == 'homepage':
                    dep.homepageUrl = url
        else:
            # Deprecated fields
            dep.repoUrl = metadata.get('Download-URL', '') or ''
            dep.homepageUrl = metadata.get('Home-page', '') or ''

        # Use the installed distribution for files only if it is the very same version
        dist = _find_distribution(name)
        if dist is not None and version and dist.version != version:
            dist = None

        dist_path = None
        dist_editable_path = None

        if dist is not None:
            # noinspection PyTypeChecker
            site_packages = Path(str(dist.locate_file('')))
            for file in dist.files or []:
                if file.name == 'METADATA' and file.parent.name.endswith('.dist-info'):
                    dist_path = site_packages / file.parent

                if file.name.startswith('__editable__') and file.name.endswith('.pth'):
                    # Open manually as dist.read_text() does not work here
                    with (site_packages / file.name).open() as fp:
                        dist_editable_path = fp.read().strip()

        # Collect license information
        lic_file = None
        lic_file_info = metadata.get_all('License-File', [])

        if len(lic_file_info) > 1:
            lic_file = next((lf for lf in lic_file_info if 'license' in lf.lower()), None)
        elif lic_file_info:
            lic_file = lic_file_info[0]

        if lic_file and dist_path is not None:
            lic_file_path = dist_path / f'licenses/{lic_file}'

            if lic_file_path.exists():
                dep.license_file = str(lic_file_path)
            else:
                lic_file_path = dist_path / lic_file
                if lic_file_path.exists():
                    dep.license_file = str(lic_file_path)
        elif project_path and (lic_file_path := _find_project_license_file(project_path, lic_file_info)):
            dep.license_file = str(lic_file_path)

        if lic := metadata.get('License-Expression'):
            dep.licenses.append(License(name=lic))
        elif (lic_text := metadata.get('License')) and not dep.license_file:
            if lics := get_license_from_text(lic_text, as_lic_text_only=False):
                dep.licenses.extend(License(name=lic) for lic in lics[1])
            # If the license text is very short, it might be a license name
            elif len(lic_text) < 30:
                dep.licenses.append(License(name=lic_text))

        # Collect package files
        if dist_editable_path:
            dep.package_files.append(dist_editable_path)
        elif dist and (top_level := dist.read_text('top_level.txt')):
            # noinspection PyTypeChecker
            files = (Path(str(dist.locate_file(f))).resolve() for f in top_level.split('\n') if f)
            dep.package_files.extend(str(f) for f in files if f.exists())
        elif project_path:
            dep.package_files.append(str(project_path.resolve()))

        # Collect dependencies, following only requirements whose markers apply
        dep.dependencies = [d for req in _active_requirements(reqs, extras) if (d := self._create_dep(req))]

        return dep

    def _create_dep(self, req: Requirement) -> t.Optional[Dependency]:
        extras = {canonicalize_name(e) for e in req.extras}

        if metadata := self.__resolved.get(canonicalize_name(req.name)):
            return self._create_dep_from_metadata(metadata, extras=extras)

        return Dependency(key=f'pypi:{canonicalize_name(req.name)}', name=req.name, type='pypi')


class _JsonMetadata:
    """
    Read access to the JSON form of core metadata (PEP 566), as reported by pip,
    with the interface of importlib.metadata.PackageMetadata
    """
    def __init__(self, data: t.Dict[str, t.Any]):
        self.__data = data

    @staticmethod
    def __key(field: str) -> str:
        return field.lower().replace('-', '_')

    def get(self, field: str, default: t.Any = None) -> t.Any:
        value = self.__data.get(self.__key(field), default)
        if isinstance(value, list):
            return value[0] if value else default
        return value

    def get_all(self, field: str, default: t.Any = None) -> t.Any:
        value = self.__data.get(self.__key(field))
        if value is None:
            return default
        return value if isinstance(value, list) else [value]


_import_statement_regex = re.compile(r'(?:from|import) ([A-Z0-9_]+).*', flags=re.IGNORECASE)


def _extract_imported_pkgs(path: Path) -> t.List[str]:
    with path.open('r') as fp:
        try:
            data = fp.read()
            return _import_statement_regex.findall(data)
        except:
            return []


def _parse_requirements(reqs: t.Iterable[str]) -> t.List[Requirement]:
    parsed = []
    for req in reqs:
        try:
            parsed.append(Requirement(req))
        except InvalidRequirement:
            pass
    return parsed


def _active_requirements(reqs: t.Iterable[Requirement], extras: t.AbstractSet[str]) -> t.List[Requirement]:
    """
    Selects the requirements that apply to the current environment for the given extras of the package.
    Requirements of extras which are not requested ('extra == "..."') and requirements for other
    platforms or Python versions are skipped.
    """
    envs = [{'extra': e} for e in sorted(extras)] + [{'extra': ''}]
    active: t.Dict[str, Requirement] = {}

    for req in reqs:
        if req.marker is not None and not any(req.marker.evaluate(env) for env in envs):
            continue

        if (name := canonicalize_name(req.name)) not in active:
            active[name] = Requirement(str(req))
        else:
            # The same package may be required several times, e.g. with different extras
            active[name].extras.update(req.extras)

    return list(active.values())


def _find_distribution(name: str):
    try:
        return distribution(name)
    except PackageNotFoundError:
        return None


def _expand_url(url: str) -> str:
    """Replaces ${VAR} references, e.g. for credentials, which must not be stored in the project settings"""
    expanded = os.path.expandvars(url)
    if unset := re.findall(r'\$\{?(\w+)\}?', expanded):
        raise DependencyResolutionError(f'Cannot resolve the PyPI dependencies: the environment variable(s) '
                                        f'{", ".join(unset)} used in the package index URL {_redact_url(url)} '
                                        f'are not set.')
    return expanded


def _redact_url(url: str) -> str:
    """Hides credentials in a URL for log output"""
    parts = urlsplit(url)
    if parts.username or parts.password:
        host = parts.hostname or ''
        if parts.port:
            host += f':{parts.port}'
        return urlunsplit(parts._replace(netloc=f'***@{host}'))
    return url


def _redact_urls(text: str) -> str:
    """Hides credentials of all URLs in a text, e.g. in pip messages, also if the scheme is missing"""
    text = re.sub(r'(\w+://)[^/@\s]+@', r'\1***@', text)
    # user:password@host without a scheme; a colon is required, so that 'git@host' stays readable
    return re.sub(r'(?<![^\s(\'"])[^\s/@:\'"()]+:[^\s/@]+@', '***@', text)


def _find_project_license_file(path: Path, metadata_license_files: t.Iterable[str]) -> t.Optional[Path]:
    for lic_file in metadata_license_files:
        for lic_path in (path / 'licenses' / lic_file, path / lic_file):
            if lic_path.exists():
                return lic_path

    for lic_name in ('LICENSE', 'LICENSE.txt', 'LICENSE.md', 'COPYING', 'COPYING.txt'):
        lic_path = path / lic_name
        if lic_path.exists():
            return lic_path

    return None


def _normalize_label(label: str) -> str:
    import string
    chars_to_remove = string.punctuation + string.whitespace
    removal_map = str.maketrans("", "", chars_to_remove)
    return label.translate(removal_map).lower()
