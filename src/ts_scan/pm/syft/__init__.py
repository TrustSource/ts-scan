import typing as t
import tempfile

from pathlib import Path
from urllib.parse import urlparse
from packageurl import PackageURL

from .model import Document, Package
from ts_scan.pm import Scanner, Dependency, DependencyScan, License
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
                        scan.moduleId = f'{url.scheme}:{scan.module}'
                    except ValueError:
                        pass

                return scan

    @staticmethod
    def __create_scan(path: Path) -> t.Optional[DependencyScan]:
        with path.open() as fp:
            data = fp.read()

        doc = Document.model_validate_json(data)

        if distro := doc.distro:
            module = distro.id
        else:
            module = doc.descriptor.name

        deps = [SyftScanner.__create_dep(pkg) for pkg in doc.artifacts]

        return DependencyScan(module=module, moduleId=module, dependencies=deps)

    @staticmethod
    def __create_dep(pkg: Package, use_purl_as_version=False) -> t.Optional[Dependency]:
        dep = None

        try:
            purl = PackageURL.from_string(pkg.purl)
        except ValueError:
            purl = None

        if purl:
            key = SyftScanner._map_purl_type(purl.type)
            if purl.namespace:
                key += ':' + purl.namespace
            key += ':' + purl.name

            if not use_purl_as_version:
                ver = pkg.version
            else:
                ver = pkg.purl

            ns = purl.namespace if purl.namespace else ''

            dep = Dependency(key, pkg.name, versions=[ver], type=purl.type, namespace=ns)
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
