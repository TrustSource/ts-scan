from pathlib import Path
from typing import Optional

from spdx.document import Document
from spdx.parsers.loggers import StandardLogger

from spdx.parsers import rdf
from spdx.parsers import tagvalue
from spdx.parsers import jsonparser
from spdx.parsers import yamlparser
from spdx.parsers import xmlparser
from spdx.parsers import jsonyamlxmlbuilders, tagvaluebuilders, rdfbuilders


def parse(path: Path) -> Optional[Document]:
    read_data = False
    builder_module = jsonyamlxmlbuilders

    if path.suffix in ['.spdx', '.rdf', '.rdf.xml']:
        parser_module = rdf
        builder_module = rdfbuilders

    elif path.suffix == '.tag':
        read_data = True
        parser_module = tagvalue
        builder_module = tagvaluebuilders

    elif path.suffix == '.json':
        parser_module = jsonparser

    elif path.suffix in ['.yaml', '.yml']:
        parser_module = yamlparser

    elif path.suffix == '.xml':
        parser_module = xmlparser

    else:
        return None

    parser = parser_module.Parser(builder_module.Builder(), StandardLogger())

    if hasattr(parser, "build"):
        parser.build()

    with path.open('r') as f:
        doc, err = parser.parse(f.read()) if read_data else parser.parse(f)
        return doc
