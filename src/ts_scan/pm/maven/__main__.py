from . import MavenScanner
from pathlib import Path

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        s = next(iter(MavenScanner().scan(Path(sys.argv[1]))), None)

        print([dep.package_files for dep in s.dependencies] if s is not None else [])
    else:
        print('No path provided')
