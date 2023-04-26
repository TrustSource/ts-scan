# This is a pytest script that applies to all submodules of pm
# (the magic that makes this work is in conftest.py)
#
# To write more test functions:
#   - define a function that starts with "test_"
#   - use assert statements to check whatever you want to check
#   - if you define the parameter "scanner_class", your function will be executed for each submodule
#     scanner_class is a tuple as (classname: str, class: *Scan-class)
#
# To write tests for a SPECIFIC scanner module:
#   - create a file called test_<name>.py in the pytest directory (this one)
#   - proceed as above, but DON'T use the scanner_class parameter
#     rather, hardcode the *Scan class you want to test into the script

from typing import List, Tuple
from pathlib import Path

from ts_scan.pm import DependencyScan


def test_class_exists(scanner_classes: List[Tuple[str, DependencyScan]]):
    assert len(scanner_classes) > 0, "no *Scan class found"
    assert len(scanner_classes) <= 1, "multiple *Scan classes found, only one is allowed per module"


def test_attributes(scanner_class: Tuple[str, DependencyScan]):
    scanner = scanner_class(Path("."))

    assert hasattr(scanner, "module")
    assert hasattr(scanner, "moduleId")
    assert hasattr(scanner, "dependencies")
    assert hasattr(scanner, "execute")

def test_execute(scanner_class: Tuple[str, DependencyScan]):
    pass