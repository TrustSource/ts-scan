import typing as t

from functools import cached_property
from pathlib import Path
from defusedxml import ElementTree as ET

from .. import License


class Pom:
    def __init__(self):
        self.__tree: ET = None
        self.__namespaces = {'xmlns': 'http://maven.apache.org/POM/4.0.0'}

    @cached_property
    def url(self) -> str:
        if node := self.__tree.find("/xmlns:url", namespaces=self.__namespaces):
            return node.text
        return ''

    @cached_property
    def description(self) -> str:
        if node := self.__tree.find("/xmlns:description", namespaces=self.__namespaces):
            return node.text
        return ''

    @cached_property
    def licenses(self) -> t.List[License]:
        names = self.__tree.findall("/xmlns:licenses/xmlns:license/xmlns:name", namespaces=self.__namespaces)
        urls = self.__tree.findall("/xmlns:licenses/xmlns:license/xmlns:url", namespaces=self.__namespaces)

        return [License(n.text.strip(), u.text.strip()) for n, u in zip(names, urls)]

    @cached_property
    def repositories(self) -> t.Dict[str, str]:
        ids = self.__tree.findall("/xmlns:repositories/xmlns:repository/xmlns:id", namespaces=self.__namespaces)
        urls = self.__tree.findall("/xmlns:repositories/xmlns:repository/xmlns:url", namespaces=self.__namespaces)
        return {n.text.strip(): u.text.strip() for n, u in zip(ids, urls)}

    @classmethod
    def from_file(cls, path: Path) -> t.Optional['Pom']:
        if not path.exists():
            return None

        pom = Pom()
        pom.__tree = ET.parse(path)

        return pom

    @classmethod
    def from_string(cls, data: str) -> t.Optional['Pom']:
        pom = Pom()
        pom.__tree = ET.fromstring(data)

        return pom
