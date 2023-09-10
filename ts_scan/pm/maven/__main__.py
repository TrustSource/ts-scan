from . import scan
from pathlib import Path

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        s = scan(Path(sys.argv[1]))

        print([dep.files for dep in s.dependencies])
    else:
        print('No path provided')