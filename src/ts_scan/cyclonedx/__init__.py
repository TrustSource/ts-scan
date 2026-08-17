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
_bom_api = t.cast(t.Any, Bom)
_component_factory = t.cast(t.Any, Component)


def import_scan(path: Path, fmt: str) -> t.Optional[DependencyScan]:
    if fmt == 'cyclonedx-json':
        with path.open() as fp:
            bom_data = json.load(fp)
            bom = t.cast(Bom, _bom_api.from_json(bom_data))

    elif fmt == 'cyclonedx-xml':
        with path.open() as fp:
            bom_data = ElementTree.fromstring(fp.read())
            bom = t.cast(Bom, _bom_api.from_xml(bom_data))

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
    bom = t.cast(Bom, _bom_api())
    bom_api = t.cast(t.Any, bom)
    metadata = bom_api.metadata
    metadata.tools.components.add(_component_factory(
        name='ts-scan',
        type=ComponentType.APPLICATION))

    metadata.component = root = _component_factory(
        name=scan.module
    )

    comps = [_create_component(dep, bom) for dep in scan.dependencies]
    bom_api.register_dependency(root, comps)

    return bom


def _create_component(dep: Dependency, bom: Bom) -> Component:
    bom_api = t.cast(t.Any, bom)
    comp = t.cast(t.Optional[Component], bom_api.get_component_by_purl(dep.purl))

    if not comp:
        comp = t.cast(Component, _component_factory(
            name=dep.name,
            version=dep.version,
            licenses=[_lic_factory.make_from_string(lic.name) for lic in dep.licenses],
            purl=dep.purl
        ))
        bom_api.components.add(comp)

    bom_api.register_dependency(comp, [_create_component(d, bom) for d in dep.dependencies])
    return comp


def _create_scan(bom: Bom) -> DependencyScan:
    bom_api = t.cast(t.Any, bom)
    deps = {}
    visited = {}

    for comp in t.cast(t.Iterable[Component], bom_api.components):
        if dep := _create_dependency(comp):
            deps[t.cast(t.Any, comp).bom_ref] = dep

    metadata = bom_api.metadata
    for src_bom in t.cast(t.Iterable[t.Any], bom_api.dependencies):
        if metadata.component and src_bom.ref == metadata.component.bom_ref:
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

    if metadata.component:
        module = metadata.component.name
    else:
        module = 'unknown'

    return DependencyScan(module=module, moduleId=f'cdx:{module}', dependencies=list(deps.values()))


def _create_dependency(comp: Component) -> t.Optional[Dependency]:
    comp_api = t.cast(t.Any, comp)
    if (purl := comp_api.purl) and (dep := Dependency.create_from_purl(purl)):
        version = comp_api.version if comp_api.version else purl.version
        if version:
            dep.versions.append(version)

        lics = []
        for lic in t.cast(t.Iterable[t.Any], comp_api.licenses):
            lic_api = t.cast(t.Any, lic)
            if isinstance(lic, DisjunctiveLicense) and (lic_api.id or lic_api.name):
                lics.append(License(
                    name=lic_api.id if lic_api.id else lic_api.name,
                    url=str(lic_api.url) if lic_api.url else ''
                ))
            elif isinstance(lic, LicenseExpression) and lic_api.value:
                lics.append(License(name=lic_api.value))

        dep.licenses = lics

        return dep

    return None
