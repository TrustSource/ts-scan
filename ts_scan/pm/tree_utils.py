import re

from pathlib import Path
from typing import List, Any

class Tree:
    @classmethod
    def from_maven_file(cls, path: Path) -> 'Tree':
        """Parses a maven-generated dependency tree file, in the format 'text'."""

        with open(path, "r") as f:
            prev_indent = 0
            prev_vertex = Tree()
            root = None

            for line in f:
                # compute indent, i.e. tree depth, by counting non-alphanumeric characters
                # at the beginning of the string, then dividing by 3
                if indent_match := re.search(r'^\W+', line):
                    new_indent = indent_match.span()[1] // 3
                else:
                    new_indent = 0

                rest = re.search(r'[a-zA-Z].*', line)

                new_vertex = Tree()
                new_vertex._data = line[rest.start() : rest.end()].strip()

                if new_indent == 0:
                    # case 0, line has indent 0 (only happend at the start):
                    # new vertex has no parent, but is saved as a reference to the root
                    root = new_vertex

                elif new_indent > prev_indent:
                    # case 1, line is more indentet than last line:
                    # new vertex is a child of the previous vertex
                    new_vertex._parent = prev_vertex
                    prev_vertex._children.append(new_vertex)

                elif new_indent == prev_indent:
                    # case 2, line has the same indent as last line:
                    # new vertex is a sibling of the previous vertex
                    new_vertex._parent = prev_vertex._parent
                    prev_vertex._parent.children.append(new_vertex)

                else:
                    # case 3, line has less indent than last line:
                    # new vertex is a child of the vertex n+1 levels up in the hierarchy
                    # where n is the difference in indents
                    diff = prev_indent - new_indent
                    parent = prev_vertex._parent

                    for _ in range(diff):
                        parent = parent.parent

                    new_vertex._parent = parent
                    parent.children.append(new_vertex)

                prev_vertex = new_vertex
                prev_indent = new_indent

        return root


    def __init__(self):
        self._children = []
        self._parent = None
        self._data = None

    @property
    def data(self) -> Any:
        return self._data
    
    @property
    def parent(self) -> 'Tree':
        return self._parent
    
    @property
    def children(self) -> List['Tree']:
        return self._children
