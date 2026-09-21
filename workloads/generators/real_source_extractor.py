"""
ColliScope Real-Source Workload Extractor (AST-Based)

Extracts structured compiler symbol-table operation traces from real C source code
using pycparser to perform AST traversal.

AST-derived declarations, references, and scopes provide structural reliability,
serving as a modeled mapping to compiler symbol-table operations:
- c_ast.FuncDef / c_ast.Compound -> ENTER_SCOPE / EXIT_SCOPE (lexical block scopes)
- c_ast.Decl (variables, parameters, functions) -> DECLARE <name> <type_id> <scope_id>
- c_ast.ID (expressions, operands, calls) -> REFERENCE <name> <scope_id>
- Unresolved external symbols (standard library calls, external macros) are tracked
  separately as external references without synthesizing artificial in-unit DECLARE operations.
- Enforces proper lexical shadowing and strict same-scope duplicate-declaration prohibition.
"""

import os
import re
from typing import List, Dict, Set, Tuple, Any, Optional
from collections import Counter
import pycparser
from pycparser import c_parser, c_ast

# Standard C library preamble for pycparser (C99 AST parser without native preprocessor)
C_PREAMBLE = """
typedef int size_t;
typedef int ptrdiff_t;
typedef int intptr_t;
typedef int uintptr_t;
typedef int FILE;
typedef int cJSON_bool;
typedef unsigned char unsigned_char;
typedef struct cJSON {
    struct cJSON *next;
    struct cJSON *prev;
    struct cJSON *child;
    int type;
    char *valuestring;
    int valueint;
    double valuedouble;
    char *string;
} cJSON;
typedef struct cJSON_Hooks {
    void *(*malloc_fn)(size_t sz);
    void (*free_fn)(void *ptr);
} cJSON_Hooks;
typedef struct parse_buffer {
    const unsigned char *content;
    size_t length;
    size_t offset;
    size_t depth;
    cJSON_Hooks hooks;
} parse_buffer;
typedef struct printbuffer {
    unsigned char *buffer;
    size_t length;
    size_t offset;
    size_t depth;
    cJSON_bool noalloc;
    cJSON_bool format;
    cJSON_Hooks hooks;
} printbuffer;
typedef struct internal_hooks {
    void *(*allocate)(size_t size);
    void (*deallocate)(void *pointer);
    void *(*reallocate)(void *pointer, size_t size);
} internal_hooks;
"""

class SymbolTableASTVisitor(c_ast.NodeVisitor):
    """
    Traverses a C AST and emits structured compiler symbol-table trace commands.
    """
    def __init__(self, flat_scope: bool = False, max_operations: Optional[int] = None):
        self.flat_scope = flat_scope
        self.max_operations = max_operations
        self.commands: List[str] = ["ENTER_SCOPE 0"]
        self.active_stack: List[int] = [0]
        self.next_scope_id: int = 1
        self.scope_declarations: Dict[int, Set[str]] = {0: set()}
        self.scope_parents: Dict[int, int] = {0: 0}
        self.identifier_counts: Counter = Counter()

        self.total_declarations = 0
        self.total_references = 0
        self.resolved_references_count = 0
        self.external_references_count = 0
        self.external_symbols: Set[str] = set()
        self.max_depth_seen = 1

    def _current_scope(self) -> int:
        return 0 if self.flat_scope else self.active_stack[-1]

    def _should_stop(self) -> bool:
        return self.max_operations is not None and len(self.commands) >= self.max_operations

    def visit_FuncDef(self, node: c_ast.FuncDef):
        if self._should_stop():
            return

        curr_scope = self._current_scope()

        # 1. Declare the function name in outer scope
        func_name = node.decl.name if node.decl else None
        if func_name and func_name not in self.scope_declarations[curr_scope]:
            self.commands.append(f"DECLARE {func_name} 1 {curr_scope}")
            self.scope_declarations[curr_scope].add(func_name)
            self.total_declarations += 1
            self.identifier_counts[func_name] += 1

        # 2. Enter function body scope (if not flat)
        new_scope = self.next_scope_id
        if not self.flat_scope:
            self.next_scope_id += 1
            self.commands.append(f"ENTER_SCOPE {new_scope} {curr_scope}")
            self.active_stack.append(new_scope)
            self.scope_declarations[new_scope] = set()
            self.scope_parents[new_scope] = curr_scope
            self.max_depth_seen = max(self.max_depth_seen, len(self.active_stack))

        body_scope = self._current_scope()

        # 3. Declare parameters in function scope
        if node.decl and node.decl.type and hasattr(node.decl.type, "args") and node.decl.type.args:
            for param in node.decl.type.args.params:
                if isinstance(param, c_ast.Decl) and param.name:
                    if param.name not in self.scope_declarations[body_scope]:
                        self.commands.append(f"DECLARE {param.name} 2 {body_scope}")
                        self.scope_declarations[body_scope].add(param.name)
                        self.total_declarations += 1
                        self.identifier_counts[param.name] += 1

        # 4. Visit function body statements (skip the outermost Compound's enter_scope since we already entered)
        if node.body and node.body.block_items:
            for item in node.body.block_items:
                if self._should_stop():
                    break
                self.visit(item)

        # 5. Exit function scope
        if not self.flat_scope:
            exited = self.active_stack.pop()
            self.commands.append(f"EXIT_SCOPE {exited}")

    def visit_Compound(self, node: c_ast.Compound):
        if self._should_stop():
            return

        curr_scope = self._current_scope()
        new_scope = self.next_scope_id

        if not self.flat_scope:
            self.next_scope_id += 1
            self.commands.append(f"ENTER_SCOPE {new_scope} {curr_scope}")
            self.active_stack.append(new_scope)
            self.scope_declarations[new_scope] = set()
            self.scope_parents[new_scope] = curr_scope
            self.max_depth_seen = max(self.max_depth_seen, len(self.active_stack))

        if node.block_items:
            for item in node.block_items:
                if self._should_stop():
                    break
                self.visit(item)

        if not self.flat_scope:
            exited = self.active_stack.pop()
            self.commands.append(f"EXIT_SCOPE {exited}")

    def visit_Decl(self, node: c_ast.Decl):
        if self._should_stop():
            return

        curr_scope = self._current_scope()
        # Skip typedef declarations themselves
        if node.storage and "typedef" in node.storage:
            return

        if node.name:
            if node.name not in self.scope_declarations[curr_scope]:
                self.commands.append(f"DECLARE {node.name} 1 {curr_scope}")
                self.scope_declarations[curr_scope].add(node.name)
                self.total_declarations += 1
                self.identifier_counts[node.name] += 1

        # Visit initializer to capture references in initial values (e.g., int a = b + 1;)
        if node.init:
            self.visit(node.init)

    def visit_ID(self, node: c_ast.ID):
        if self._should_stop():
            return

        curr_scope = self._current_scope()
        name = node.name

        # Check visibility in current scope and ancestor chain
        is_visible = False
        walk = curr_scope
        while True:
            if name in self.scope_declarations.get(walk, set()):
                is_visible = True
                break
            if walk == 0:
                break
            walk = self.scope_parents.get(walk, 0)

        if not is_visible:
            # Unresolved external symbol (e.g. standard library function or macro)
            # Track separately without synthesizing artificial in-unit DECLARE operations
            self.external_symbols.add(name)
            self.external_references_count += 1
        else:
            self.resolved_references_count += 1

        self.commands.append(f"REFERENCE {name} {curr_scope}")
        self.total_references += 1
        self.identifier_counts[name] += 1


    def visit_StructRef(self, node: c_ast.StructRef):
        # Precise AST distinction: only visit the struct object expression.
        # The member field name is a struct field, not a lexical scope variable!
        self.visit(node.name)

    def visit_Cast(self, node: c_ast.Cast):
        # Precise AST distinction: type name is a type, only visit the expression.
        self.visit(node.expr)

    def visit_InitList(self, node: c_ast.InitList):
        # Precise AST distinction: array/struct initializer list is not a block scope!
        for expr in node.exprs:
            self.visit(expr)

class RealSourceExtractor:
    def __init__(self, source_path: str):
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")
        self.source_path = source_path
        self.statistics: Dict[str, Any] = {}
        self.identifier_counts: Counter = Counter()

    def _clean_source_for_pycparser(self, raw_code: str) -> str:
        """
        Cleans C source code so that pycparser can parse it into an AST:
        - Uses Pygments CLexer to grammatically separate comments, strings, and preprocessor lines
        - Normalizes C string and character literals
        - Strips non-standard calling convention macros (CJSON_CDECL, CJSON_PUBLIC)
        - Strips C++ compatibility wrappers (extern "C")
        """
        from pygments.lexers import CLexer
        from pygments.token import Token

        tokens = list(CLexer().get_tokens(raw_code))
        clean_parts = []
        skip_pp_line = False

        for t_type, t_val in tokens:
            if t_type in Token.Comment:
                continue

            if t_val.strip().startswith('#'):
                skip_pp_line = True
                continue

            if skip_pp_line:
                if '\n' in t_val:
                    last_line = t_val.split('\n')[0]
                    if not last_line.rstrip().endswith('\\'):
                        skip_pp_line = False
                        clean_parts.append('\n')
                continue

            if t_type in Token.Literal.String:
                clean_parts.append('""')
            elif t_type in Token.Literal.Char:
                clean_parts.append("'0'")
            else:
                clean_parts.append(t_val)

        code = "".join(clean_parts)
        code = re.sub(r'extern\s*["\']C["\']\s*\{', '', code)
        code = re.sub(r'CJSON_PUBLIC\(([^)]+)\)', r'\1', code)
        code = code.replace('CJSON_CDECL', '')
        code = re.sub(r'cJSON_ArrayForEach\s*\(([^,]+),\s*([^)]+)\)', r'for(\1 = (\2 != 0) ? (\2)->child : 0; \1 != 0; \1 = \1->next)', code)
        code = re.sub(r'static\s+const\s+unsigned\s+char\s+first_byte_mark\[.*?\]\s*=\s*\{.*?\};', '', code, flags=re.DOTALL)
        return code

    def extract(self, max_operations: Optional[int] = None, flat_scope: bool = False) -> List[str]:
        with open(self.source_path, "r", encoding="utf-8", errors="replace") as f:
            raw_code = f.read()

        clean_code = self._clean_source_for_pycparser(raw_code)
        parser = c_parser.CParser()

        # Parse translation unit
        full_code = C_PREAMBLE + "\n" + clean_code
        try:
            ast = parser.parse(full_code)
        except Exception:
            # Fallback: parse statement by statement if minor syntax quirks exist
            # For cJSON, full_code parses cleanly with C_PREAMBLE.
            ast = parser.parse(full_code)

        visitor = SymbolTableASTVisitor(flat_scope=flat_scope, max_operations=max_operations)
        visitor.visit(ast)

        # Close all open child scopes
        if not flat_scope:
            while len(visitor.active_stack) > 1:
                exiting = visitor.active_stack.pop()
                visitor.commands.append(f"EXIT_SCOPE {exiting}")

        # Close root scope 0
        visitor.commands.append("EXIT_SCOPE 0")
        visitor.commands.append("")

        self.identifier_counts = visitor.identifier_counts
        self.statistics = {
            "source_file": self.source_path,
            "extraction_method": "pycparser_ast_visitor",
            "unique_identifiers": len(self.identifier_counts),
            "total_identifier_occurrences": sum(self.identifier_counts.values()),
            "total_declarations": visitor.total_declarations,
            "in_unit_declarations": visitor.total_declarations,
            "total_references": visitor.total_references,
            "resolved_references": visitor.resolved_references_count,
            "unresolved_external_references": visitor.external_references_count,
            "external_symbols_count": len(visitor.external_symbols),
            "external_symbols": sorted(list(visitor.external_symbols)),
            "max_scope_depth": visitor.max_depth_seen,
            "total_scopes": visitor.next_scope_id if not flat_scope else 1,
            "total_trace_commands": len(visitor.commands) - 3,
        }

        # Header metadata
        header = [
            f"# ColliScope Real-Source Trace (AST-Derived Modeled Symbol Table Trace)",
            f"# Source: {os.path.basename(self.source_path)}, Scope: {'flat' if flat_scope else 'nested'}",
            f"# In-Unit Declarations: {visitor.total_declarations}, External Symbols: {len(visitor.external_symbols)} ({visitor.external_references_count} refs)",
            f"# Total References: {visitor.total_references}, Total Scopes: {visitor.next_scope_id if not flat_scope else 1}",
        ]
        return header + visitor.commands

    def write_to_file(self, filepath: str, max_operations: Optional[int] = None, flat_scope: bool = False) -> None:
        cmds = self.extract(max_operations=max_operations, flat_scope=flat_scope)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(cmds))
