import typing as t
import tempfile

from pathlib import Path
from urllib.parse import urlparse
from packageurl import PackageURL

from .model import Document, Package
from ts_scan_core import Dependency, DependencyScan, License
from ts_scan.pm import Scanner
from ts_scan.cli import msg


class SyftScanner(Scanner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def name() -> str:
        return "Syft"

    @staticmethod
    def executable() -> t.Optional[str]:
        return 'syft'

    def accepts(self, path: Path) -> bool:
        return True

    def scan(self, src: t.Union[str, Path]) -> t.Optional[DependencyScan]:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(f'{tmpdir}/scan.json')

            res = self._exec(str(src), '-o', f'syft-json={output}')

            if res.returncode != 0:
                msg.fail(f'Syft failed to scan {str(src)}. Error code: {res.returncode}')
                return None

            if scan := self.__create_scan(output):
                if isinstance(src, Path):
                    scan.moduleId = f'{src.name}:{scan.module}'
                else:
                    try:
                        url = urlparse(src)
                        scan.moduleId = f'{url.scheme}:{scan.moduleId}'
                    except ValueError:
                        pass

                return scan

            return None

    @staticmethod
    def __create_scan(path: Path) -> t.Optional[DependencyScan]:
        with path.open() as fp:
            data = fp.read()

        doc = Document.model_validate_json(data)

        module = None
        moduleId = None

        if distro := doc.distro:
            if distro.prettyName:
                module = distro.prettyName
            elif distro.name:
                module = distro.name

            if distro.id:
                moduleId = distro.id + (f':{distro.versionID}' if distro.versionID else '')

        if not module:
            module = doc.descriptor.name

        if not moduleId:
            moduleId = module

        deps = []
        for pkg in doc.artifacts:
            if dep := SyftScanner.__create_dep(pkg):
                deps.append(dep)

        return DependencyScan(module=module, moduleId=moduleId, dependencies=deps)

    @staticmethod
    def __create_dep(pkg: Package, use_purl_as_version=False) -> t.Optional[Dependency]:
        dep = None

        try:
            purl = PackageURL.from_string(pkg.purl)
        except ValueError:
            purl = None

        if purl:
            if not use_purl_as_version:
                versions = [pkg.version]
            else:
                versions = []

            dep = Dependency.create_from_purl(purl, versions_override=versions)

            if dep:
                for pkg_lic in pkg.licenses.root:
                    if pkg_lic.type == 'declared':
                        lic = License(pkg_lic.value)
                        if pkg_lic.urls:
                            lic.url = pkg_lic.urls[0]
                        dep.licenses.append(lic)
            else:
                msg.warn(f'Could not create dependency from purl: {pkg.purl}')
        else:
            msg.warn(f'Skipping package {pkg.name} as it has no purl.')

        return dep
