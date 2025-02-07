import typing as t

from pathlib import Path
from packageurl import PackageURL

from .model import Document, Package
from ..pm import Dependency, DependencyScan, License


def import_scan(path: Path) -> t.Optional[DependencyScan]:
    with path.open() as fp:
        data = fp.read()
        doc = Document.model_validate_json(data)
        return SyftScan(doc)


class SyftScan(DependencyScan):
    def __init__(self, doc: Document):
        super().__init__()

        self.__doc = doc

        self.__module = ''
        self.__moduleId = ''

    @property
    def module(self) -> str:
        if module := self.__module:
            return module
        elif distro := self.__doc.distro:
            return distro.id
        else:
            return self.__doc.descriptor.name

    @module.setter
    def module(self, value: str):
        self.__module = value

    @property
    def moduleId(self) -> str:
        if moduleId := self.__moduleId:
            return moduleId
        else:
            return self.module

    @moduleId.setter
    def moduleId(self, value: str):
        self.__moduleId = value

    @property
    def dependencies(self) -> t.Iterable['Dependency']:
        for pkg in self.__doc.artifacts:
            if dep := SyftScan.__create_dep(pkg):
                yield dep

    @staticmethod
    def __create_dep(pkg: Package, use_purl_as_version=False) -> t.Optional[Dependency]:
        dep = None

        try:
            purl = PackageURL.from_string(pkg.purl)
        except ValueError:
            purl = None

        if purl:
            key = SyftScan._map_purl_type(purl.type)
            if purl.namespace:
                key += ':' + purl.namespace
            key += ':' + purl.name

            if not use_purl_as_version:
                ver = pkg.version
            else:
                ver = pkg.purl

            dep = Dependency(key, pkg.name, versions=[ver], purl_type=purl.type, purl_namespace=purl.namespace)
            dep.meta['purl'] = pkg.purl

            for pkg_lic in pkg.licenses.root:
                if pkg_lic.type == 'declared':
                    lic = License(pkg_lic.value)
                    if pkg_lic.urls:
                        lic.url = pkg_lic.urls[0]
                    dep.licenses.append(lic)

        return dep

    @staticmethod
    def _map_purl_type(ty: str):
        # TrustSource key mapping
        if ty == 'maven':
            return 'mvn'
        else:
            return ty
