"""
AST Parser for Cascade Graph Engine.
Supports Python, TypeScript, JavaScript.
Extracts: functions, classes, imports, calls.
Flags dynamic callsites explicitly — never skips them.
"""

import os
from pathlib import Path
from typing import Optional
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
import tree_sitter_javascript as tsjavascript

# Build language objects once at module load
PY_LANGUAGE  = Language(tspython.language())
TS_LANGUAGE  = Language(tstypescript.language_typescript())
TSX_LANGUAGE = Language(tstypescript.language_tsx())
JS_LANGUAGE  = Language(tsjavascript.language())

LANGUAGE_MAP = {
    ".py":  PY_LANGUAGE,
    ".ts":  TS_LANGUAGE,
    ".tsx": TSX_LANGUAGE,
    ".js":  JS_LANGUAGE,
    ".jsx": JS_LANGUAGE,
}

# Dynamic call patterns to always flag
DYNAMIC_PATTERNS = {"getattr", "eval", "exec", "__import__", "importlib"}


def get_parser(ext: str) -> Optional[Parser]:
    lang = LANGUAGE_MAP.get(ext.lower())
    if not lang:
        return None
    return Parser(lang)


def node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def parse_file(file_path: str) -> dict:
    """
    Parse a single source file.
    Returns dict with keys:
      path, language, functions, classes, imports, calls, error
    """
    path   = Path(file_path)
    ext    = path.suffix.lower()
    parser = get_parser(ext)

    result = {
        "path":      str(file_path),
        "language":  ext.lstrip("."),
        "functions": [],
        "classes":   [],
        "imports":   [],
        "calls":     [],
        "error":     None
    }

    if not parser:
        result["error"] = f"Unsupported extension: {ext}"
        return result

    try:
        source = path.read_bytes()
    except Exception as e:
        result["error"] = str(e)
        return result

    try:
        tree = parser.parse(source)
    except Exception as e:
        result["error"] = f"Parse error: {e}"
        return result

    root = tree.root_node

    if ext == ".py":
        result["functions"] = _extract_py_functions(root, source)
        result["classes"]   = _extract_py_classes(root, source)
        result["imports"]   = _extract_py_imports(root, source)
        result["calls"]     = _extract_py_calls(root, source)
    else:
        result["functions"] = _extract_ts_functions(root, source)
        result["classes"]   = _extract_ts_classes(root, source)
        result["imports"]   = _extract_ts_imports(root, source)
        result["calls"]     = _extract_ts_calls(root, source)

    return result


# ── Python extractors ───────────────────────────────────────────

def _extract_py_functions(root, source: bytes) -> list:
    functions = []
    for node in _walk(root):
        if node.type not in ("function_definition", "async_function_definition"):
            continue
        name_node = node.child_by_field_name("name")
        if not name_node:
            continue
        functions.append({
            "name":       node_text(name_node, source),
            "line_start": node.start_point[0] + 1,
            "line_end":   node.end_point[0] + 1,
            "docstring":  _get_py_docstring(node, source),
            "params":     _get_py_params(node, source),
            "is_method":  _is_method(node),
            "is_async":   node.type == "async_function_definition"
        })
    return functions


def _extract_py_classes(root, source: bytes) -> list:
    classes = []
    for node in _walk(root):
        if node.type != "class_definition":
            continue
        name_node = node.child_by_field_name("name")
        if not name_node:
            continue
        bases = []
        args_node = node.child_by_field_name("superclasses")
        if args_node:
            for child in args_node.children:
                if child.type == "identifier":
                    bases.append(node_text(child, source))
        classes.append({
            "name":       node_text(name_node, source),
            "line_start": node.start_point[0] + 1,
            "line_end":   node.end_point[0] + 1,
            "bases":      bases,
            "docstring":  _get_py_docstring(node, source),
            "methods":    [f["name"] for f in _extract_py_functions(node, source)]
        })
    return classes


def _extract_py_imports(root, source: bytes) -> list:
    imports = []
    for node in _walk(root):
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append({
                        "module":  node_text(child, source),
                        "names":   [],
                        "is_from": False,
                        "line":    node.start_point[0] + 1
                    })
        elif node.type == "import_from_statement":
            module = ""
            names  = []
            for child in node.children:
                if child.type == "dotted_name" and not module:
                    module = node_text(child, source)
                elif child.type in ("import_prefix", "relative_import"):
                    module = node_text(child, source)
                elif child.type == "aliased_import":
                    n = child.child_by_field_name("name")
                    if n:
                        names.append(node_text(n, source))
                elif child.type == "identifier":
                    names.append(node_text(child, source))
                elif child.type == "wildcard_import":
                    names.append("*")
            imports.append({
                "module":  module,
                "names":   names,
                "is_from": True,
                "line":    node.start_point[0] + 1
            })
    return imports


def _extract_py_calls(root, source: bytes) -> list:
    calls = []
    for node in _walk(root):
        if node.type != "call":
            continue
        func_node = node.child_by_field_name("function")
        if not func_node:
            continue
        call_text  = node_text(func_node, source)
        is_dynamic = (
            func_node.type == "attribute" or
            any(pat in call_text for pat in DYNAMIC_PATTERNS)
        )
        callee = call_text.split(".")[-1] if "." in call_text else call_text
        calls.append({
            "callee":     callee,
            "full_call":  call_text,
            "is_dynamic": is_dynamic,
            "line":       node.start_point[0] + 1
        })
    return calls


# ── TypeScript / JavaScript extractors ─────────────────────────

def _extract_ts_functions(root, source: bytes) -> list:
    functions = []
    target_types = {
        "function_declaration", "function", "arrow_function",
        "method_definition", "function_expression"
    }
    for node in _walk(root):
        if node.type not in target_types:
            continue
        name = ""
        name_node = node.child_by_field_name("name")
        if name_node:
            name = node_text(name_node, source)
        elif node.parent and node.parent.type in (
            "variable_declarator", "pair", "assignment_expression"
        ):
            id_node = node.parent.child_by_field_name("name")
            if id_node:
                name = node_text(id_node, source)
        if not name:
            continue
        functions.append({
            "name":       name,
            "line_start": node.start_point[0] + 1,
            "line_end":   node.end_point[0] + 1,
            "docstring":  "",
            "params":     [],
            "is_method":  node.type == "method_definition",
            "is_async":   False
        })
    return functions


def _extract_ts_classes(root, source: bytes) -> list:
    classes = []
    for node in _walk(root):
        if node.type != "class_declaration":
            continue
        name_node = node.child_by_field_name("name")
        if not name_node:
            continue
        bases = []
        heritage = node.child_by_field_name("heritage")
        if heritage:
            for child in _walk(heritage):
                if child.type == "identifier":
                    bases.append(node_text(child, source))
        classes.append({
            "name":       node_text(name_node, source),
            "line_start": node.start_point[0] + 1,
            "line_end":   node.end_point[0] + 1,
            "bases":      bases,
            "docstring":  "",
            "methods":    []
        })
    return classes


def _extract_ts_imports(root, source: bytes) -> list:
    imports = []
    for node in _walk(root):
        if node.type != "import_statement":
            continue
        source_node = node.child_by_field_name("source")
        module = (
            node_text(source_node, source).strip("'\"")
            if source_node else ""
        )
        names = []
        for child in _walk(node):
            if child.type == "imported_binding":
                names.append(node_text(child, source))
            elif child.type == "namespace_import":
                names.append("*")
        imports.append({
            "module":  module,
            "names":   names,
            "is_from": True,
            "line":    node.start_point[0] + 1
        })
    return imports


def _extract_ts_calls(root, source: bytes) -> list:
    calls = []
    for node in _walk(root):
        if node.type != "call_expression":
            continue
        func_node = node.child_by_field_name("function")
        if not func_node:
            continue
        call_text  = node_text(func_node, source)
        is_dynamic = func_node.type == "member_expression"
        callee     = call_text.split(".")[-1] if "." in call_text else call_text
        calls.append({
            "callee":     callee,
            "full_call":  call_text,
            "is_dynamic": is_dynamic,
            "line":       node.start_point[0] + 1
        })
    return calls


# ── Helpers ─────────────────────────────────────────────────────

def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _get_py_docstring(node, source: bytes) -> str:
    body = node.child_by_field_name("body")
    if not body:
        return ""
    for child in body.children:
        if child.type == "expression_statement":
            for sub in child.children:
                if sub.type in ("string", "concatenated_string"):
                    raw = node_text(sub, source)
                    return (raw.strip('"""')
                               .strip("'''")
                               .strip('"')
                               .strip("'")
                               .strip())
    return ""


def _get_py_params(node, source: bytes) -> list:
    params = []
    params_node = node.child_by_field_name("parameters")
    if not params_node:
        return params
    for child in params_node.children:
        if child.type == "identifier":
            params.append(node_text(child, source))
        elif child.type in (
            "default_parameter", "typed_parameter", "typed_default_parameter"
        ):
            n = child.child_by_field_name("name")
            if n:
                params.append(node_text(n, source))
    return params


def _is_method(node) -> bool:
    parent = node.parent
    while parent:
        if parent.type == "class_definition":
            return True
        parent = parent.parent
    return False
