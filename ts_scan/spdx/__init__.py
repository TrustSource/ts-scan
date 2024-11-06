import typing as t

from pathlib import Path
from typing import Iterable

from spdx.package import Package
from spdx.document import Document
from packageurl import PackageURL
from license_expression import get_spdx_licensing

from .parser import parse
from ..pm import Dependency, DependencyScan, License

licensing = get_spdx_licensing()


def import_scan(path: Path) -> t.Optional[DependencyScan]:
    if doc := parse(path):
        return SpdxScan(doc)
    else:
        raise ValueError('Cannot parse SPDX document')


class SpdxScan(DependencyScan):
    def __init__(self, doc: Document):
        super().__init__()

        self.__doc = doc

        self.__module = ''
        self.__moduleId = ''

    @property
    def module(self) -> str:
        if module := self.__module:
            return module
        else:
            return self.__doc.name

    @module.setter
    def module(self, value: str):
        self.__module = value

    @property
    def moduleId(self) -> str:
        if moduleId := self.__moduleId:
            return moduleId
        else:
            return f'spdx:{self.__doc.name}'

    @moduleId.setter
    def moduleId(self, value: str):
        self.__moduleId = value

    @property
    def dependencies(self) -> Iterable['Dependency']:
        for pkg in self.__doc.packages:
            if dep := SpdxScan.__create_dep(pkg):
                yield dep

    @staticmethod
    def __create_dep(pkg: Package, use_purl_as_version=True, parse_license_exprs=True) -> t.Optional[Dependency]:
        dep = None
        meta = {}

        pkg_mngr_info = None

        for ref in pkg.pkg_ext_refs:
            if ref.category == 'PACKAGE-MANAGER':
                pkg_mngr_info = ref

        if pkg_mngr_info and pkg_mngr_info.pkg_ext_ref_type == 'purl':
            try:
                purl = PackageURL.from_string(pkg_mngr_info.locator)
            except ValueError:
                purl = None

            if purl:
                key = SpdxScan._map_purl_type(purl.type)
                if purl.namespace:
                    key += ':' + purl.namespace
                key += ':' + purl.name

                if not use_purl_as_version:
                    ver = pkg.version
                    meta['purl'] = pkg_mngr_info.locator
                else:
                    ver = pkg_mngr_info.locator

                dep = Dependency(key, pkg.name, versions=[ver], purl_type=purl.type)

        if dep and pkg.license_declared:
            lic_expr = pkg.license_declared.identifier
            if lic_expr not in ['NONE', 'NOASSERTION']:
                if parse_license_exprs:
                    parsed = licensing.parse(lic_expr)
                    symbols = parsed.symbols
                    dep.licenses = [License(name=str(s)) for s in symbols]
                else:
                    dep.licenses = [License(name=lic_expr)]

        if dep and meta:
            dep.meta = meta

        return dep

    @staticmethod
    def _map_purl_type(ty: str):
        # TrustSource key mapping
        if ty == 'maven':
            return 'mvn'
        else:
            return ty
