from . import scan

if __name__ == "__main__":
    s = scan("C:\\Users\\Soren\\eacg\\samples\\ts-mvn-plugin")

    print([dep.files for dep in s.dependencies])