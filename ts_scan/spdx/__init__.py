import typing as t

from uuid import uuid4
from datetime import datetime
from pathlib import Path

from packageurl import PackageURL
from license_expression import LicenseExpression, combine_expressions
from spdx_tools.spdx.model import (Package, Document, CreationInfo, Actor, ActorType,
                                   ExternalPackageRef, ExternalPackageRefCategory)

from ..pm import Dependency, DependencyScan, License


def import_scan(path: Path) -> t.Optional[DependencyScan]:
    from spdx_tools.spdx.parser.parse_anything import parse_file

    if doc := parse_file(str(path)):
        return DependencyScan(module=doc.name,
                              moduleId=f'spdx:{doc.name}',
                              dependencies=[_create_dep(pkg) for pkg in doc.packages])

    else:
        raise ValueError('Cannot parse SPDX document')


def export_scan(scan: DependencyScan, path: Path):
    from spdx_tools.spdx.writer.write_anything import write_file

    creation_info = CreationInfo(
        spdx_id='SPDXRef-DOCUMENT',
        spdx_version='SPDX-2.3',
        name=scan.module,
        document_namespace=f'https://spdx.org/spdxdocs/{scan.module}-{str(uuid4())}',
        creators=[Actor(ActorType.TOOL, 'ts-scan')],
        created=datetime.now()
    )

    packages = []
    for dep in scan.iterdeps():
        packages.extend(_create_pkgs(len(packages), dep))

    doc = Document(creation_info=creation_info, packages=packages)
    write_file(doc, str(path))


def _create_pkgs(num: int, dep: Dependency) -> t.Iterable[Package]:
    if not dep.versions:
        pkg = Package(name=dep.name, spdx_id=f'SPDXRef-{num}')
        pkg.license_declared = combine_expressions([lic.name for lic in dep.licenses], relation='OR')
        yield pkg
    else:
        for v in dep.versions:
            pkg = Package(name=dep.name, spdx_id=f'SPDXRef-{num}')
            pkg.version = v
            pkg.license_declared = combine_expressions([lic.name for lic in dep.licenses], relation='OR')
            pkg_ref = ExternalPackageRef(
                category=ExternalPackageRefCategory.PACKAGE_MANAGER,
                reference_type='purl',
                locator=dep.purl.to_string()
            )
            pkg.external_references.append(pkg_ref)
            yield pkg


def _create_dep(pkg: Package, use_purl_as_version=False) -> t.Optional[Dependency]:
    dep = None
    meta = {}

    pkg_mngr_info = None

    for ref in pkg.external_references:
        if ref.category == 'PACKAGE-MANAGER':
            pkg_mngr_info = ref

    if pkg_mngr_info and pkg_mngr_info.reference_type == 'purl':
        try:
            purl = PackageURL.from_string(pkg_mngr_info.locator)
        except ValueError:
            purl = None

        if purl:
            key = purl.type
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
        if lic_expr := pkg.license_declared:
            if isinstance(lic_expr, LicenseExpression):
                dep.licenses = [License(name=str(s)) for s in lic_expr.symbols]

    if dep and meta:
        dep.meta = meta

    return dep
