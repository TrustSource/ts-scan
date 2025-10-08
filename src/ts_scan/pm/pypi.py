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

from . import PackageManagerScanner, DependencyScan, Dependency, License, get_license_from_text


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

            dep.description = metadata.get('Summary', '')

            if proj_urls := metadata.get_all('Project-URL', []):
                for proj_url in proj_urls:
                    proj_url = proj_url.split(',', 1)

                    lbl = _normalize_label(proj_url[0].strip())
                    url = proj_url[1].strip()

                    if lbl in ('source', 'sources', 'repository', 'sourcecode', 'github'):
                        dep.sourceUrl = url
                    elif lbl == 'homepage':
                        dep.homepageUrl = url
            else:
                # Deprecated fields
                dep.repoUrl = metadata.get('Download-URL', '')
                dep.homepageUrl = metadata.get('Home-page', '')

            dist = distribution(name)
            dist_path = None
            dist_editable_path = None

            # noinspection PyTypeChecker
            site_packages = Path(dist.locate_file(''))
            for file in dist.files:
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
            elif top_level := dist.read_text('top_level.txt'):
                # noinspection PyTypeChecker
                files = (Path(dist.locate_file(f)).resolve() for f in top_level.split('\n') if f)
                dep.package_files.extend(str(f) for f in files if f.exists())

            # Collect dependencies

            # if dist_path:
            #     direct_url_file = dist_path / 'direct_url.json'
            #     if direct_url_file.exists():
            #         with direct_url_file.open() as fp:
            #             data = json.load(fp)
            #             if data.get('dir_info', {}).get('editable', False):
            #                 url = data['url']
            #                 if url.startswith('file://'):
            #                     dep.package_files.append(urllib.parse.urlparse(url).path)
            #                 else:
            #                     dep.package_files.append(url)

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


def _normalize_label(label: str) -> str:
    import string
    chars_to_remove = string.punctuation + string.whitespace
    removal_map = str.maketrans("", "", chars_to_remove)
    return label.translate(removal_map).lower()
