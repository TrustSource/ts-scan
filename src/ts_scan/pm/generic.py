import typing as t

from pathlib import Path

from . import PackageManagerScanner, DependencyScan, Dependency

from ..analyse import analyse_path_with_ds
from ..analyse.scanoss import analyse_scan as analyse_scan_with_scanoss


class GenericScanner(PackageManagerScanner):
    @staticmethod
    def name() -> str:
        return "Genric"

    @staticmethod
    def executable() -> t.Optional[str]:
        return None

    def accepts(self, path: Path) -> bool:
        return True

    def scan(self, path: Path) -> t.Optional[DependencyScan]:
        root = Dependency(name=path.name, type='unknown')
        scan = DependencyScan.from_dep(root)

        ds = analyse_path_with_ds(path, ds_args=["--include-scanoss-wfp", "--use-scanoss-api"])
        scan.deepscans[root.key] = ds

        analyse_scan_with_scanoss(scan, api_key=None)

        if ds_summary := ds.summary_at_path(''):
            for purl, versions in ds_summary.components.items():
                if dep := Dependency.create_from_purl(purl, versions_override=list(versions)):
                    root.dependencies.append(dep)                                

        return scan
