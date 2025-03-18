import json
import typing as t

from pathlib import Path
from defusedxml import ElementTree
from copy import copy

from cyclonedx.model.bom import Bom
from cyclonedx.model.component import Component, ComponentType
from cyclonedx.model.license import LicenseExpression, DisjunctiveLicense
from cyclonedx.factory.license import LicenseFactory
from cyclonedx.schema import OutputFormat, SchemaVersion
from cyclonedx.output import make_outputter

from ..pm import Dependency, DependencyScan, License

_lic_factory = LicenseFactory()


def import_scan(path: Path, fmt: str) -> t.Optional[DependencyScan]:
    if fmt == 'cyclonedx-json':
        with path.open() as fp:
            bom_data = json.load(fp)
            bom = Bom.from_json(bom_data)

    elif fmt == 'cyclonedx-xml':
        with path.open() as fp:
            bom_data = ElementTree.fromstring(fp.read())
            bom = Bom.from_xml(bom_data)

    else:
        raise ValueError(f'Unsupported CycloneDX input format: {fmt}')

    return _create_scan(bom)


def export_scan(scan: DependencyScan, output: t.TextIO, fmt: str):
    if fmt == 'cyclonedx-json':
        output_fmt = OutputFormat.JSON
    elif fmt == 'cyclonedx-xml':
        output_fmt = OutputFormat.XML
    else:
        raise ValueError(f'Unsupported CycloneDX output format: {fmt}')

    bom = _create_bom(scan)
    outputter = make_outputter(bom, output_fmt, SchemaVersion.V1_6)

    output.write(outputter.output_as_string(indent=2))


def _create_bom(scan: DependencyScan) -> Bom:
    bom = Bom()
    bom.metadata.tools.components.add(Component(
        name='ts-scan',
        type=ComponentType.APPLICATION))

    bom.metadata.component = root = Component(
        name=scan.module
    )

    comps = [_create_component(dep, bom) for dep in scan.dependencies]
    bom.register_dependency(root, comps)

    return bom


def _create_component(dep: Dependency, bom: Bom) -> Component:
    comp = bom.get_component_by_purl(dep.purl)

    if not comp:
        comp = Component(
            name=dep.name,
            version=dep.version,
            licenses=[_lic_factory.make_from_string(lic.name) for lic in dep.licenses],
            purl=dep.purl
        )
        bom.components.add(comp)

    bom.register_dependency(comp, [_create_component(d, bom) for d in dep.dependencies])
    return comp


def _create_scan(bom: Bom) -> DependencyScan:
    deps = {}
    visited = {}

    for comp in bom.components:
        if dep := _create_dependency(comp):
            deps[comp.bom_ref] = dep

    for src_bom in bom.dependencies:
        if bom.metadata.component and src_bom.ref == bom.metadata.component.bom_ref:
            continue

        src = deps.get(src_bom.ref)
        if not src:
            src = visited.get(src_bom.ref)

        for dst_bom in src_bom.dependencies:
            if dst := deps.pop(dst_bom.ref, None):
                visited[dst_bom.ref] = dst
            else:
                dst = visited.get(dst_bom.ref)

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

    if bom.metadata.component:
        module = bom.metadata.component.name
    else:
        module = 'unknown'

    return DependencyScan(module=module, moduleId=f'cdx:{module}', dependencies=list(deps.values()))


def _create_dependency(comp: Component) -> t.Optional[Dependency]:
    if (purl := comp.purl) and (dep := Dependency.create_from_purl(purl)):
        dep.versions.append(comp.version if comp.version else purl.version)

        lics = []
        for lic in comp.licenses:
            if type(lic) is DisjunctiveLicense and lic.id or lic.name:
                lics.append(License(name=lic.id if lic.id else lic.name, url=lic.url))
            elif type(lic) is LicenseExpression and lic.value:
                lics.append(License(name=lic.value))

        dep.licenses = lics

        return dep

    return None
