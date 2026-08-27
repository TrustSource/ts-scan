"""
OBOM (Ownership Bill of Materials) -- extracts a generic access graph
{principal, resource, actions[], effect, grantedVia} from IaC sources found
in a scanned target, on top of a trimmed, vendored copy of Checkov's own
resource graph builder (checkov.cloudformation.graph_manager /
checkov.terraform.graph_manager).

This is evidence for real IAM-privilege-based trust boundaries in
ts-tm-agent's threat modeling: without it, trust zones are inferred from
SBOM/dependency signals alone. See:
https://github.com/eacg-gmbh/ts-tm-agent (CONCEPT.md, trust-boundary work)

Ported from the scan2graph proof of concept
(https://github.com/jthDEV/checkov, branch feature/scan2graph-extraction).
That branch's scan2graph/README.md has the detailed scope notes (SAM policy
template coverage, what's handled per IaC front-end, the abandoned cf2tf
conversion attempt) -- not duplicated here in full.

## Why vendored, not `pip install checkov`

The full `checkov` PyPI distribution pins three libraries ts-scan itself
depends on -- importlib-metadata<8.0, cyclonedx-python-lib<8.0,
packageurl-python<0.14 -- all newer in ts-scan. The latter two are core to
ts-scan's own SBOM/PURL generation, not safely downgradable on a guess.

Turned out unnecessary: graph-building code path only pulled in checkov's
CVE-scanning/SBOM/reporting/platform-integration machinery (boto3,
cloudsplaining, detect_secrets, aiohttp, ...) through a handful of *unused*
import couplings (e.g. cfn_utils.py importing the whole check registry for
one unrelated default-parameter value). None of it is on the path actually
exercised by `build_graph_from_source_directory()`. _obom_vendor/checkov/
is the graph-builder's real, unmodified source (from
jthDEV/checkov@feature/scan2graph-extraction) plus:
  - the ~25 files that real graph-building genuinely touches (found by
    iteratively importing and copying in whatever was actually missing,
    not by trusting static analysis alone -- see heal_imports.py in that
    branch's history for the tool used)
  - stub replacements (unittest.mock.MagicMock via module __getattr__, see
    each stub's docstring) for check-registry/platform-integration/
    reporting modules that are imported but never called on this path
  - one small hand-edit (common/util/json_utils.py) where a stub broke a
    genuinely-needed class (CustomJSONEncoder) -- replaced four
    cross-subsystem isinstance() branches (Severity/ImageDetails/SAST
    types/PotentialSecret) with local unreachable sentinel classes instead

Verified byte-identical output against both scan2graph fixtures after
trimming (ts-tm-agent's own template.yaml for CloudFormation/SAM: 15
edges/3 unresolved; the hand-written Terraform fixture: 1 edge/1
unresolved) -- not just "it imports without crashing".

Resulting external dependency footprint: bc-python-hcl2, bc-jsonpath-ng,
lark, ply, dpath, networkx, numpy, asteval, regex, packaging (plus
requests/tqdm/typing-extensions/PyYAML, already in ts-scan's own
requirements). None of these conflict with ts-scan's pins.

Currently covers CloudFormation/SAM and Terraform. `extract(source_dir)`
tries both and merges the results; each front-end's graph builder returns
an empty vertex list (not an error) when it finds nothing of its kind, so
running both unconditionally is simpler than sniffing file types first.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import typing as t
from dataclasses import dataclass, field, asdict
from pathlib import Path
from types import ModuleType

OBOM_INSTALL_HINT = 'Install it with: pip install "ts-scan[obom]"'

_VENDOR_DIR = Path(__file__).parent / '_obom_vendor'

_checkov: t.Optional[ModuleType] = None


class CheckovNotInstalledError(RuntimeError):
    """Raised when the vendored graph-builder's own (lightweight) third-party
    dependencies -- bc-python-hcl2, networkx, etc., declared under the
    ts-scan "obom" extra -- aren't installed. Not about checkov itself: no
    checkov install is used or needed, the graph-builder is vendored."""
    pass


def is_checkov_installed() -> bool:
    """Name kept for continuity with the pre-vendoring version of this
    module; checks the vendored copy's own lightweight dependencies, not an
    actual checkov install (there is none)."""
    vendor_path = str(_VENDOR_DIR)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
    return importlib.util.find_spec('hcl2') is not None and importlib.util.find_spec('networkx') is not None


def obom_feature_help(description: str) -> str:
    if is_checkov_installed():
        return description
    return f'{description} [Unavailable: obom dependencies are not installed. {OBOM_INSTALL_HINT}]'


def require_checkov() -> ModuleType:
    """Ensures the vendored checkov/ subset (_obom_vendor/checkov) is on
    sys.path and importable, then returns it -- same call shape as the
    pre-vendoring version so the rest of this module (and any external
    caller) didn't need to change."""
    global _checkov

    if _checkov is not None:
        return _checkov

    vendor_path = str(_VENDOR_DIR)
    if vendor_path not in sys.path:
        # Prepend, not append: if a real `checkov` also happens to be
        # installed in this environment for an unrelated reason, our
        # trimmed/patched copy must win -- it's the one actually tested.
        sys.path.insert(0, vendor_path)

    try:
        _checkov = importlib.import_module('checkov')
        return _checkov
    except ModuleNotFoundError as err:
        raise CheckovNotInstalledError(
            f'obom dependencies are required for OBOM extraction. {OBOM_INSTALL_HINT}'
        ) from err


# AWS SAM Policy Templates this pass understands, mapped to their granted
# actions (https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-policy-templates.html).
# Deliberately partial -- extend as new templates show up in real templates,
# never guess for the rest.
SAM_POLICY_TEMPLATE_ACTIONS: t.Dict[str, t.List[str]] = {
    'DynamoDBCrudPolicy': [
        'dynamodb:GetItem',
        'dynamodb:DeleteItem',
        'dynamodb:PutItem',
        'dynamodb:Scan',
        'dynamodb:Query',
        'dynamodb:UpdateItem',
        'dynamodb:BatchWriteItem',
        'dynamodb:BatchGetItem',
        'dynamodb:DescribeTable',
        'dynamodb:ConditionCheckItem',
    ],
    'DynamoDBReadPolicy': [
        'dynamodb:GetItem',
        'dynamodb:Query',
        'dynamodb:Scan',
        'dynamodb:BatchGetItem',
        'dynamodb:DescribeTable',
        'dynamodb:ConditionCheckItem',
    ],
    'DynamoDBWritePolicy': [
        'dynamodb:PutItem',
        'dynamodb:DeleteItem',
        'dynamodb:UpdateItem',
        'dynamodb:BatchWriteItem',
    ],
}


# Checkov injects dunder-wrapped bookkeeping keys onto every parsed node --
# __file__/__startline__/__endline__ for CloudFormation, __start_line__/
# __end_line__/__address__ for Terraform. Strip generically rather than
# listing both IaC front-ends' exact key names.
def _is_synthetic_key(key: t.Any) -> bool:
    return isinstance(key, str) and key.startswith('__') and key.endswith('__')


def _clean(value: t.Any) -> t.Any:
    """Drop checkov's dunder-wrapped bookkeeping keys."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if not _is_synthetic_key(k)}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _stringify_resource(value: t.Any) -> str:
    """Render a Resource value (literal, {Ref}, {Fn::GetAtt}, {Fn::Sub}, or a
    list of these) as a short, human-readable, non-resolved string. This is
    NOT ARN resolution -- it's a graph-readable label, e.g. "Ref:TableName"."""
    import json

    value = _clean(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ', '.join(_stringify_resource(v) for v in value)
    if isinstance(value, dict):
        if 'Ref' in value:
            return f"Ref:{value['Ref']}"
        if 'Fn::GetAtt' in value:
            target = value['Fn::GetAtt']
            if isinstance(target, list):
                target = '.'.join(target)
            return f'GetAtt:{target}'
        if 'Fn::Sub' in value:
            return f"Sub:{value['Fn::Sub']}"
        return json.dumps(value)
    return str(value)


def _as_list(value: t.Any) -> t.List[t.Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


@dataclass
class ObomEdge:
    principal: str
    resource: str
    actions: t.List[str]
    effect: str
    grantedVia: str


@dataclass
class ObomUnresolved:
    principal: str
    reason: str
    detail: str


@dataclass
class ObomResult:
    edges: t.List[ObomEdge] = field(default_factory=list)
    unresolved: t.List[ObomUnresolved] = field(default_factory=list)

    def to_dict(self) -> t.Dict[str, t.Any]:
        return {
            'edges': [asdict(e) for e in self.edges],
            'unresolved': [asdict(u) for u in self.unresolved],
        }

    def extend(self, other: 'ObomResult') -> None:
        self.edges.extend(other.edges)
        self.unresolved.extend(other.unresolved)


def _statements_to_edges(
    statements: t.Any, principal: str, granted_via: str
) -> t.List[ObomEdge]:
    edges: t.List[ObomEdge] = []
    for stmt in _as_list(_clean(statements)):
        if not isinstance(stmt, dict):
            continue
        effect = stmt.get('Effect', 'Allow')
        actions = [str(a) for a in _as_list(stmt.get('Action'))]
        resources = _as_list(stmt.get('Resource')) or [None]
        for res in resources:
            edges.append(
                ObomEdge(
                    principal=principal,
                    resource=_stringify_resource(res) if res is not None else '*',
                    actions=actions,
                    effect=effect,
                    grantedVia=granted_via,
                )
            )
    return edges


def _extract_role(vertex: t.Any, result: ObomResult) -> None:
    principal = vertex.name
    config = _clean(vertex.config)

    for arn in _as_list(config.get('ManagedPolicyArns')):
        result.unresolved.append(
            ObomUnresolved(
                principal=principal,
                reason='aws-managed-policy',
                detail=f"actions live in AWS's own policy JSON, not the template: {arn}",
            )
        )

    for policy in _as_list(config.get('Policies')):
        name = policy.get('PolicyName', 'inline-policy')
        statements = (policy.get('PolicyDocument') or {}).get('Statement')
        result.edges += _statements_to_edges(
            statements, principal, f"AWS::IAM::Role inline policy '{name}'"
        )


def _extract_sam_function(vertex: t.Any, result: ObomResult) -> None:
    principal = vertex.name
    config = _clean(vertex.config)

    for entry in _as_list(config.get('Policies')):
        if isinstance(entry, str):
            result.unresolved.append(
                ObomUnresolved(
                    principal=principal,
                    reason='aws-managed-or-sam-template-policy',
                    detail=f'bare policy name, not resolved: {entry}',
                )
            )
            continue
        if not isinstance(entry, dict):
            continue

        if 'Statement' in entry:
            result.edges += _statements_to_edges(
                entry['Statement'], principal, 'SAM inline Policies[].Statement'
            )
            continue

        # Otherwise: exactly one key naming a SAM policy template.
        for template_name, params in entry.items():
            actions = SAM_POLICY_TEMPLATE_ACTIONS.get(template_name)
            if actions is None:
                result.unresolved.append(
                    ObomUnresolved(
                        principal=principal,
                        reason='unmapped-sam-policy-template',
                        detail=f'{template_name}({params})',
                    )
                )
                continue
            # SAM templates parameterize by resource name/ARN under varying
            # keys (TableName, BucketName, QueueArn, ...) -- take the first
            # value present rather than hardcoding one key name.
            target = next(iter(params.values())) if isinstance(params, dict) else params
            result.edges.append(
                ObomEdge(
                    principal=principal,
                    resource=_stringify_resource(target),
                    actions=actions,
                    effect='Allow',
                    grantedVia=f"SAM policy template '{template_name}'",
                )
            )


def extract_cloudformation(source_dir: str) -> ObomResult:
    require_checkov()
    from checkov.cloudformation.graph_manager import CloudformationGraphManager
    from checkov.common.graph.db_connectors.networkx.networkx_db_connector import (
        NetworkxConnector,
    )

    graph_manager = CloudformationGraphManager(db_connector=NetworkxConnector())
    local_graph, _ = graph_manager.build_graph_from_source_directory(source_dir)

    result = ObomResult()
    for vertex in local_graph.vertices:
        resource_type = vertex.attributes.get('resource_type')
        if resource_type == 'AWS::IAM::Role':
            _extract_role(vertex, result)
        elif resource_type == 'AWS::Serverless::Function':
            _extract_sam_function(vertex, result)
    return result


# --- Terraform ---

# Not exhaustive -- extend as new compute resource types show up. Used to
# tell "the actual thing that assumes this role" apart from a bare policy
# resource when resolving a role/user/group reference to a principal.
TF_COMPUTE_RESOURCE_TYPES = {
    'aws_lambda_function',
    'aws_ecs_task_definition',
    'aws_ecs_service',
    'aws_instance',
    'aws_batch_job_definition',
}

TF_POLICY_RESOURCE_TYPES = {
    'aws_iam_role_policy',
    'aws_iam_user_policy',
    'aws_iam_group_policy',
}

TF_ATTACHMENT_RESOURCE_TYPES = {
    'aws_iam_role_policy_attachment',
    'aws_iam_user_policy_attachment',
    'aws_iam_group_policy_attachment',
}

TF_PRINCIPAL_ATTRS = ('role', 'user', 'group')


def _tf_resource_type(vertex: t.Any) -> t.Optional[str]:
    rt = vertex.attributes.get('resource_type')
    return rt[0] if isinstance(rt, list) else rt


def _tf_config(vertex: t.Any) -> t.Dict[str, t.Any]:
    """Terraform vertex.config is {resource_type: {resource_name: {...}}} --
    unwrap to the inner attribute dict."""
    resource_type = _tf_resource_type(vertex)
    inner = (vertex.config or {}).get(resource_type, {}) if resource_type else {}
    return _clean(next(iter(inner.values()), {})) if inner else {}


def _tf_attr(config: t.Dict[str, t.Any], key: str) -> t.Any:
    """Plain HCL attributes render as a single-element list (["value"]);
    jsonencode(...) blocks render as an already-evaluated dict/list, not
    wrapped this way. Unwrap only the former."""
    value = config.get(key)
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _index_edges(
    local_graph: t.Any,
) -> t.Tuple[t.Dict[int, t.List[t.Any]], t.Dict[int, t.List[t.Any]]]:
    by_origin: t.Dict[int, t.List[t.Any]] = {}
    by_dest: t.Dict[int, t.List[t.Any]] = {}
    for edge in local_graph.edges:
        by_origin.setdefault(edge.origin, []).append(edge)
        by_dest.setdefault(edge.dest, []).append(edge)
    return by_origin, by_dest


def _tf_resolve_compute_principal(
    local_graph: t.Any, by_dest: t.Dict[int, t.List[t.Any]], role_vertex_index: int
) -> str:
    """Given a role/user/group vertex, look for an inbound `role` edge from a
    compute resource (Lambda, ECS task, ...) that assumes it -- if found,
    that's the more useful principal name. Falls back to the role itself."""
    role_vertex = local_graph.vertices[role_vertex_index]
    for edge in by_dest.get(role_vertex_index, []):
        origin_vertex = local_graph.vertices[edge.origin]
        if (
            edge.label == 'role'
            and _tf_resource_type(origin_vertex) in TF_COMPUTE_RESOURCE_TYPES
        ):
            return origin_vertex.id
    return role_vertex.id


def _tf_principal(
    local_graph: t.Any,
    by_origin: t.Dict[int, t.List[t.Any]],
    by_dest: t.Dict[int, t.List[t.Any]],
    vertex_index: int,
    config: t.Dict[str, t.Any],
) -> str:
    for attr in TF_PRINCIPAL_ATTRS:
        if attr not in config:
            continue
        for edge in by_origin.get(vertex_index, []):
            if edge.label == attr:
                return _tf_resolve_compute_principal(local_graph, by_dest, edge.dest)
        raw = _tf_attr(config, attr)
        if raw:
            return str(raw)
    return local_graph.vertices[vertex_index].id


def _extract_tf_policy(
    vertex_index: int,
    local_graph: t.Any,
    by_origin: t.Dict[int, t.List[t.Any]],
    by_dest: t.Dict[int, t.List[t.Any]],
    result: ObomResult,
) -> None:
    vertex = local_graph.vertices[vertex_index]
    config = _tf_config(vertex)
    principal = _tf_principal(local_graph, by_origin, by_dest, vertex_index, config)
    policy_doc = _tf_attr(config, 'policy')
    statements = policy_doc.get('Statement') if isinstance(policy_doc, dict) else None
    result.edges += _statements_to_edges(
        statements, principal, f'{vertex.id} (Terraform inline policy)'
    )


def _extract_tf_attachment(
    vertex_index: int,
    local_graph: t.Any,
    by_origin: t.Dict[int, t.List[t.Any]],
    by_dest: t.Dict[int, t.List[t.Any]],
    result: ObomResult,
) -> None:
    vertex = local_graph.vertices[vertex_index]
    config = _tf_config(vertex)
    principal = _tf_principal(local_graph, by_origin, by_dest, vertex_index, config)
    policy_arn = _tf_attr(config, 'policy_arn')
    result.unresolved.append(
        ObomUnresolved(
            principal=principal,
            reason='aws-managed-policy',
            detail=f"actions live in AWS's own policy JSON, not the template: {policy_arn}",
        )
    )


def extract_terraform(source_dir: str) -> ObomResult:
    require_checkov()
    from checkov.terraform.graph_manager import TerraformGraphManager
    from checkov.common.graph.db_connectors.networkx.networkx_db_connector import (
        NetworkxConnector,
    )

    graph_manager = TerraformGraphManager(db_connector=NetworkxConnector())
    local_graph, _ = graph_manager.build_graph_from_source_directory(source_dir)
    by_origin, by_dest = _index_edges(local_graph)

    result = ObomResult()
    for i, vertex in enumerate(local_graph.vertices):
        resource_type = _tf_resource_type(vertex)
        if resource_type in TF_POLICY_RESOURCE_TYPES:
            _extract_tf_policy(i, local_graph, by_origin, by_dest, result)
        elif resource_type in TF_ATTACHMENT_RESOURCE_TYPES:
            _extract_tf_attachment(i, local_graph, by_origin, by_dest, result)
    return result


def extract(source_dir: str) -> ObomResult:
    """Try both IaC front-ends and merge. Each graph builder returns an
    empty vertex list (not an error) when it finds none of its kind, so
    running both unconditionally is simpler than sniffing file types first."""
    result = ObomResult()
    result.extend(extract_cloudformation(source_dir))
    result.extend(extract_terraform(source_dir))
    return result
