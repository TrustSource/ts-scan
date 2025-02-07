import re
import typing as t

from pathlib import Path


class Tree:
    def __init__(self):
        self.__children = []
        self.__parent = None
        self.__data = None

    @property
    def data(self) -> t.Optional[str]:
        return self.__data

    @property
    def parent(self) -> t.Optional['Tree']:
        return self.__parent

    @property
    def children(self) -> t.List['Tree']:
        return self.__children

    @classmethod
    def from_maven_file(cls, path: Path) -> t.List['Tree']:
        """Parses a maven-generated dependency tree file, in the format 'text'."""

        with open(path, "r") as f:
            root_nodes = []
            prev_indent = 0
            prev_vertex = Tree()

            for line in f:
                # compute indent, i.e. tree depth, by counting non-alphanumeric characters
                # at the beginning of the string, then dividing by 3
                if indent_match := re.search(r'^\W+', line):
                    new_indent = indent_match.span()[1] // 3
                else:
                    new_indent = 0

                rest = re.search(r'[a-zA-Z].*', line)

                new_vertex = Tree()
                new_vertex.__data = line[rest.start(): rest.end()].strip()

                if new_indent == 0:
                    # case 0, line has indent 0 (only happend at the start):
                    # new vertex has no parent, but is saved as a reference to the root
                    # and added to the list of root nodes
                    root_nodes.append(new_vertex)

                elif new_indent > prev_indent:
                    # case 1, line is more indentet than last line:
                    # new vertex is a child of the previous vertex
                    new_vertex.__parent = prev_vertex
                    prev_vertex.__children.append(new_vertex)

                elif new_indent == prev_indent:
                    # case 2, line has the same indent as last line:
                    # new vertex is a sibling of the previous vertex
                    new_vertex.__parent = prev_vertex.__parent
                    prev_vertex.__parent.children.append(new_vertex)

                else:
                    # case 3, line has less indent than last line:
                    # new vertex is a child of the vertex n+1 levels up in the hierarchy
                    # where n is the difference in indents
                    diff = prev_indent - new_indent
                    parent = prev_vertex.__parent

                    for _ in range(diff):
                        parent = parent.parent

                    new_vertex.__parent = parent
                    parent.children.append(new_vertex)

                prev_vertex = new_vertex
                prev_indent = new_indent

        return root_nodes


if __name__ == "__main__":
    deps = Path("/Users/markin/Projects/eacg/thirdparty/wildfly/deps.tree")
    nodes = Tree.from_maven_file(deps)

    for n in nodes:
        print(n.data)
