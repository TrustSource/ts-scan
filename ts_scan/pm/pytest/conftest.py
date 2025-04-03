import pkgutil
import inspect
import pytest
import importlib

from pkgutil import ModuleInfo
from typing import List, Tuple

from ts_scan.pm import DependencyScan

def pytest_generate_tests(metafunc):
    if "scanner_module_info" in metafunc.fixturenames:
        import ts_scan.pm

        scanner_modules = pkgutil.iter_modules(ts_scan.pm.__path__)

        metafunc.parametrize("scanner_module_info", scanner_modules)

@pytest.fixture
def scanner_classes(scanner_module_info: ModuleInfo) -> List[Tuple[str, DependencyScan]]:
    module_name = "ts_scan.pm." + scanner_module_info.name
    scanner_module = importlib.import_module(module_name)
    scanner_candidates = inspect.getmembers(scanner_module, inspect.isclass)

    # only keep classes that are defined in the scanner module, not inherited
    scanner_candidates = [s for s in scanner_candidates if s[1].__module__ == module_name]

    scanner_candidates = [s for s in scanner_candidates if s[0].endswith("Scan")]

    return scanner_candidates

@pytest.fixture
def scanner_class(scanner_classes: List[Tuple[str, DependencyScan]]) -> Tuple[str, DependencyScan]:
    return scanner_classes[0][1]