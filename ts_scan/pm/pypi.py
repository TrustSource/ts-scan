# SPDX-FileCopyrightText: 2020 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

import re
import build.util
import typing as t

from pathlib import Path
from typing import List, Optional, Iterable
from importlib.metadata import distribution, PackageNotFoundError

from . import Scanner, DependencyScan, Dependency, License


class PypiScanner(Scanner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def name() -> str:
        return "PyPI"

    def scan(self, path: Path) -> t.Optional[DependencyScan]:
        _scan = PypiScan(path)
        _scan.execute()
        return _scan if _scan.dependencies else None


class PypiScan(DependencyScan):
    def __init__(self, path: Path):
        super().__init__()

        self.__path = path
        self.__processed_deps = set()

        self.__dependencies = []

    @property
    def module(self) -> str:
        if len(self.__dependencies) == 1:
            return self.__dependencies[0].name
        else:
            return self.__path.name

    @property
    def moduleId(self) -> str:
        return f'pip:{self.module}'

    @property
    def dependencies(self) -> Iterable[Dependency]:
        return self.__dependencies

    def execute(self):
        stack = [self.__path]
        while len(stack) > 0:
            p = stack.pop()
            if p.is_dir():
                pkg_setup = p / "setup.py"
                if pkg_setup.exists():
                    try:
                        metadata = build.util.project_wheel_metadata(p, isolated=False)
                    except Exception as err:
                        print(f'An error occured while building packages metadata')
                        exit(2)

                    self.__dependencies.append(self._create_dep_from_metadata(metadata))
                else:
                    break
            #                    stack.extend([p/f for f in p.glob('*.py')])
            #                    stack.extend([p/d for d in p.rglob('**/')])
            else:
                for pkg in _extract_imported_pkgs(p):
                    if dep := self._create_dep(pkg):
                        self.__dependencies.append(dep)

    def _create_dep(self, pkg: str) -> Optional[Dependency]:
        try:
            pkg_info = distribution(pkg)
        except PackageNotFoundError:
            return None

        return self._create_dep_from_metadata(pkg_info.metadata)

    def _create_dep_from_metadata(self, metadata) -> Dependency:
        """
        Creates a dependency from the dist package metadate
        :param metadata: PackageMetadata
        :return:
        """
        name = metadata.get('Name', '')
        key = 'pip:' + name.lower()

        dep = Dependency(key=key, name=name, purl_type='pypi')

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

            # reqs = metadata.get_all('Requires-Dist', [])
            if reqs := dist.requires:
                dep.dependencies = [d for pkg in _extract_required_pkgs(reqs) if (d := self._create_dep(pkg))]

            if srcs := [Path(dist.locate_file(f)) for f in dist.files]:
                dep.files.extend(srcs)

            if lic_file := metadata.get('License-File', None):
                dep.license_file = next((f for f in dep.files if f.name == lic_file), None)

        return dep


_import_statement_regex = re.compile(r'(?:from|import) ([a-zA-Z0-9_]+).*')


def _extract_imported_pkgs(path: Path) -> List[str]:
    with path.open('r') as fp:
        try:
            data = fp.read()
            return _import_statement_regex.findall(data)
        except Exception:
            return []


_require_expr_regex = re.compile(r'([a-zA-Z0-9_\-]+).*')


def _extract_required_pkgs(reqs: List[str]) -> List[str]:
    for req in reqs:
        for pkg in _require_expr_regex.findall(req):
            yield pkg
