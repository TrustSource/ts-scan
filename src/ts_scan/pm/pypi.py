# SPDX-FileCopyrightText: 2020 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import re
import build.util
import typing as t

from pathlib import Path
from importlib.metadata import distribution, PackageNotFoundError
from importlib.metadata._meta import PackageMetadata
from shippinglabel.requirements import parse_requirements

from . import PackageManagerScanner, DependencyScan, Dependency, License
from ..cli import msg

_supported_pkg_files = [
    'setup.py',
    'pyproject.toml'
]


class PypiScanner(PackageManagerScanner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__processed_deps = set()

    @staticmethod
    def name() -> str:
        return "PyPI"

    def accepts(self, path: Path) -> bool:
        return path.is_dir() and any((path / pkg_file).exists() for pkg_file in _supported_pkg_files)

    def scan(self, path: Path) -> t.Optional[DependencyScan]:
        metadata = build.util.project_wheel_metadata(path, isolated=False)

        if dep := self._create_dep_from_metadata(metadata):
            return DependencyScan(module=dep.name, moduleId=f'pip:{dep.name}', dependencies=[dep])
        else:
            return None

    def _create_dep_from_metadata(self, metadata: PackageMetadata) -> Dependency:
        """
        Creates a dependency from the dist package metadate
        :param metadata: PackageMetadata
        :return:
        """
        name = metadata.get('Name', '')
        key = 'pip:' + name.lower()

        dep = Dependency(key=key, name=name, type='pypi')

        if version := metadata.get('Version', None):
            dep.versions.append(version)

        if name not in self.__processed_deps:
            self.__processed_deps.add(name)

            if licence := metadata.get('License', None):
                dep.licenses.append(License(name=licence))

            dep.repoUrl = metadata.get('Download-URL', '')
            dep.description = metadata.get('Summary', '')
            dep.homepageUrl = metadata.get('Home-page', '')

            dist = distribution(name)

            if lic_file := metadata.get('License-File', None):
                # noinspection PyTypeChecker
                dep.license_file = str(Path(dist.locate_file(lic_file)).resolve())

            if top_level := dist.read_text('top_level.txt'):
                # noinspection PyTypeChecker
                files = (str(Path(dist.locate_file(f)).resolve()) for f in top_level.split('\n') if f)
                dep.package_files.extend(files)

            # reqs = metadata.get_all('Requires-Dist', [])
            if reqs := dist.requires:
                req_pkgs = list(_extract_required_pkgs(reqs))
                dep.dependencies = [d for pkg in req_pkgs if (d := self._create_dep(pkg))]

        return dep

    def _create_dep(self, pkg: str) -> t.Optional[Dependency]:
        try:
            pkg_info = distribution(pkg)
        except PackageNotFoundError:
            return None

        return self._create_dep_from_metadata(pkg_info.metadata)


_import_statement_regex = re.compile(r'(?:from|import) ([A-Z0-9_]+).*', flags=re.IGNORECASE)


def _extract_imported_pkgs(path: Path) -> t.List[str]:
    with path.open('r') as fp:
        try:
            data = fp.read()
            return _import_statement_regex.findall(data)
        except:
            return []


def _extract_required_pkgs(reqs: t.List[str]) -> t.Iterable[str]:
    reqs, _ = parse_requirements(reqs)
    return {req.name for req in reqs}
