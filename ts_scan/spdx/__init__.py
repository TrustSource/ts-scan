import typing as t
from typing_extensions import TextIO

from copy import copy
from uuid import uuid4
from datetime import datetime
from pathlib import Path

from packageurl import PackageURL
from license_expression import LicenseExpression, combine_expressions, ExpressionError
from spdx_tools.spdx.model import (Package, Document, CreationInfo, Actor, ActorType,
                                   ExternalPackageRef, ExternalPackageRefCategory, SpdxNone,
                                   Relationship, RelationshipType)
from spdx_tools.spdx.formats import FileFormat, file_name_to_format

from ..pm import Dependency, DependencyScan, License


def import_scan(path: Path, fmt: str) -> t.Optional[DependencyScan]:
    fmt = file_name_to_format(fmt.replace('-', '.'))

    if doc := _parse_file(path, fmt):
        return DependencyScan(module=doc.creation_info.name,
                              moduleId=f'spdx:{doc.creation_info.name}',
                              dependencies=_create_deps(doc))

    else:
        raise ValueError('Cannot parse SPDX document')


def export_scan(scan: DependencyScan, output: t.TextIO, fmt: str):
    creation_info = CreationInfo(
        spdx_id='SPDXRef-DOCUMENT',
        spdx_version='SPDX-2.3',
        name=scan.module,
        document_namespace=f'https://spdx.org/spdxdocs/{scan.module}-{str(uuid4())}',
        creators=[Actor(ActorType.TOOL, 'ts-scan')],
        created=datetime.now()
    )

    packages, relationships = _create_pkgs(scan.dependencies)
    doc = Document(creation_info=creation_info,
                   packages=packages,
                   relationships=relationships)

    fmt = file_name_to_format(fmt.replace('-', '.'))
    _write_stream(doc, output, fmt)


def _create_pkgs(deps: t.Iterable[Dependency]) -> t.Tuple[t.List[Package], t.List[Relationship]]:
    visited = {}

    def _create_pkgs_impl(_deps: t.Iterable[Dependency]) -> t.Tuple[t.List[Package], t.List[Relationship]]:
        packages = []
        relations = []

        for dep in _deps:
            pkg_key = dep.key, dep.version
            pkg = visited.get(pkg_key)

            if not pkg:
                pkg = _create_pkg(dep, len(visited))
                visited[pkg_key] = pkg

            packages.append(pkg)

            pkgs, rels = _create_pkgs_impl(dep.dependencies)
            relations.extend(rels)

            for p in pkgs:
                relations.append(Relationship(pkg.spdx_id, RelationshipType.DEPENDS_ON, p.spdx_id))

        return packages, relations

    _, relationships = _create_pkgs_impl(deps)
    return list(visited.values()), relationships


def _create_pkg(dep: Dependency, ref_id: int) -> Package:
    pkg = Package(name=dep.name, spdx_id=f'SPDXRef-{ref_id}', download_location=SpdxNone())
    pkg.version = dep.version

    try:
        pkg.license_declared = combine_expressions([lic.name for lic in dep.licenses], relation='OR')
    except ExpressionError:
        print("Cannot parse licenses")
        pkg.license_declared = SpdxNone()

    pkg_ref = ExternalPackageRef(
        category=ExternalPackageRefCategory.PACKAGE_MANAGER,
        reference_type='purl',
        locator=dep.purl.to_string()
    )
    pkg.external_references.append(pkg_ref)

    return pkg


def _create_deps(doc: Document) -> t.List[Dependency]:
    deps = {}
    visited = {}

    for pkg in doc.packages:
        if dep := _create_dep(pkg):
            deps[pkg.spdx_id] = dep

    for rel in doc.relationships:
        if rel.relationship_type == RelationshipType.DEPENDS_ON:
            src = deps.get(rel.spdx_element_id)
            if not src:
                src = visited.get(rel.spdx_element_id)

            if dst := deps.pop(rel.related_spdx_element_id, None):
                visited[rel.related_spdx_element_id] = dst
            else:
                dst = visited.get(rel.related_spdx_element_id)

            if src and dst:
                dst = copy(dst)
                dst.dependencies = []

                src.dependencies.append(dst)

    visited = {(dep.key, dep.version): dep for dep in visited.values()}

    stack = []
    stack.extend(deps.values())

    while len(stack) > 0:
        cur = stack.pop()
        cur_deps = []

        for dep in cur.dependencies:
            if d := visited.pop((dep.key, dep.version), None):
                cur_deps.append(d)
                stack.append(d)
            else:
                cur_deps.append(dep)

        cur.dependencies = cur_deps

    return list(deps.values())


def _create_dep(pkg: Package, use_purl_as_version=False) -> t.Optional[Dependency]:
    dep = None
    meta = {}

    pkg_mngr_info = None

    for ref in pkg.external_references:
        if ref.category == ExternalPackageRefCategory.PACKAGE_MANAGER:
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

            dep = Dependency(key, pkg.name, type=purl.type, versions=[ver])

    if dep and pkg.license_declared:
        if lic_expr := pkg.license_declared:
            if isinstance(lic_expr, LicenseExpression):
                dep.licenses = [License(name=str(s)) for s in lic_expr.symbols]

    if dep and meta:
        dep.meta = meta

    return dep


def _write_stream(document: Document, stream: TextIO, fmt: FileFormat, validate=False):
    from spdx_tools.spdx.writer.json import json_writer
    from spdx_tools.spdx.writer.tagvalue import tagvalue_writer
    from spdx_tools.spdx.writer.xml import xml_writer
    from spdx_tools.spdx.writer.yaml import yaml_writer

    if fmt == FileFormat.JSON:
        json_writer.write_document_to_stream(document, stream, validate)
    elif fmt == FileFormat.YAML:
        yaml_writer.write_document_to_stream(document, stream, validate)
    elif fmt == FileFormat.XML:
        xml_writer.write_document_to_stream(document, stream, validate)
    elif fmt == FileFormat.TAG_VALUE:
        tagvalue_writer.write_document_to_stream(document, stream, validate)


def _parse_file(path: Path, fmt: FileFormat) -> Document:
    from spdx_tools.spdx.parser.json import json_parser
    from spdx_tools.spdx.parser.tagvalue import tagvalue_parser
    from spdx_tools.spdx.parser.xml import xml_parser
    from spdx_tools.spdx.parser.yaml import yaml_parser

    if fmt == FileFormat.TAG_VALUE:
        return tagvalue_parser.parse_from_file(str(path), 'utf-8')
    elif fmt == FileFormat.JSON:
        return json_parser.parse_from_file(str(path), 'utf-8')
    elif fmt == FileFormat.XML:
        return xml_parser.parse_from_file(str(path), 'utf-8')
    elif fmt == FileFormat.YAML:
        return yaml_parser.parse_from_file(str(path), 'utf-8')
