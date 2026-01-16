#!/usr/bin/env -S uv run python
"""
Extract documentation from Python source files into Markdown.

Walks the AST to find docstrings, standalone strings, and creates
formatted signatures for classes, methods, and functions.
"""

import ast
import glob
import os
import sys
from pathlib import Path
from typing import List, Tuple


class DocExtractor(ast.NodeVisitor):
    def __init__(self):
        self.sections: List[Tuple[str, str, str, str]] = []  # (type, signature, doc, fields)
        self.current_class = None

    def visit_Module(self, node: ast.Module) -> None:
        """Extract module-level docstring."""
        docstring = ast.get_docstring(node)
        if docstring:
            self.sections.append(("module", "", docstring, ""))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract class signature and docstring."""
        bases = ", ".join(self._format_expr(base) for base in node.bases)
        sig = f"class {node.name}({bases})" if bases else f"class {node.name}"

        docstring = ast.get_docstring(node)

        # Check if this is a Pydantic model (inherits from BaseModel)
        is_pydantic = self._is_pydantic_model(node)
        fields_md = ""
        if is_pydantic:
            fields_md = self._extract_pydantic_fields(node)

        if docstring or fields_md:
            self.sections.append(("class", sig, docstring or "", fields_md))

        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract function/method signature and docstring."""
        args = self._format_arguments(node.args)
        returns = f" -> {self._format_expr(node.returns)}" if node.returns else ""

        if self.current_class:
            sig = f"def {self.current_class}.{node.name}({args}){returns}"
            doc_type = "method"
        else:
            sig = f"def {node.name}({args}){returns}"
            doc_type = "function"

        docstring = ast.get_docstring(node)
        if docstring:
            self.sections.append((doc_type, sig, docstring, ""))

        # Also look for standalone string literals in the function body
        for stmt in node.body[1:]:  # Skip docstring
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                if isinstance(stmt.value.value, str):
                    self.sections.append(("note", "", stmt.value.value, ""))

        self.generic_visit(node)

    def _format_arguments(self, args: ast.arguments) -> str:
        """Format function arguments."""
        parts = []

        # Regular args
        for i, arg in enumerate(args.args):
            annotation = f": {self._format_expr(arg.annotation)}" if arg.annotation else ""
            default_offset = len(args.args) - len(args.defaults)
            if i >= default_offset:
                default = self._format_expr(args.defaults[i - default_offset])
                parts.append(f"{arg.arg}{annotation} = {default}")
            else:
                parts.append(f"{arg.arg}{annotation}")

        # *args
        if args.vararg:
            annotation = f": {self._format_expr(args.vararg.annotation)}" if args.vararg.annotation else ""
            parts.append(f"*{args.vararg.arg}{annotation}")

        # **kwargs
        if args.kwarg:
            annotation = f": {self._format_expr(args.kwarg.annotation)}" if args.kwarg.annotation else ""
            parts.append(f"**{args.kwarg.arg}{annotation}")

        return ", ".join(parts)

    def _format_expr(self, node) -> str:
        """Format an expression node as a string."""
        if node is None:
            return ""
        return ast.unparse(node)

    def _is_pydantic_model(self, node: ast.ClassDef) -> bool:
        """Check if a class inherits from BaseModel (directly or indirectly)."""
        for base in node.bases:
            base_str = self._format_expr(base)
            # Check for BaseModel in bases (could be pydantic.BaseModel, BaseModel, etc.)
            if "BaseModel" in base_str:
                return True
            # Also check for common Pydantic model base class names
            # This handles cases like BaseMedicalEntity which inherits from BaseModel
            if "Entity" in base_str and "Base" in base_str:
                return True

        # Also check if class has annotated assignments (field definitions)
        # which is a strong indicator of a Pydantic model
        has_annotated_fields = any(isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and not stmt.target.id.startswith("_") for stmt in node.body)

        # If it has annotated fields and inherits from something with "Model" or "Entity" in name
        if has_annotated_fields:
            base_names = [self._format_expr(base) for base in node.bases]
            if any("Model" in name or "Entity" in name for name in base_names):
                return True

        return False

    def _extract_pydantic_fields(self, node: ast.ClassDef) -> str:
        """Extract field type hints from a Pydantic model class."""
        fields = []

        for stmt in node.body:
            # Look for annotated assignments (field definitions)
            if isinstance(stmt, ast.AnnAssign):
                field_name = stmt.target.id if isinstance(stmt.target, ast.Name) else None
                if field_name:
                    # Skip private attributes and special methods
                    if field_name.startswith("_") and field_name != "__init__":
                        continue

                    # Format type annotation
                    type_hint = self._format_expr(stmt.annotation) if stmt.annotation else "Any"

                    # Format default value if present
                    default = ""
                    if stmt.value:
                        default_str = self._format_expr(stmt.value)
                        # Simplify Field() calls to show just the default
                        if default_str.startswith("Field("):
                            # Try to extract default value from Field()
                            default = self._extract_field_default(stmt.value)
                        else:
                            default = default_str

                    # Format the field line
                    if default:
                        fields.append(f"{field_name}: {type_hint} = {default}")
                    else:
                        fields.append(f"{field_name}: {type_hint}")

        if fields:
            return "**Fields:**\n\n```python\n" + "\n".join(fields) + "\n```\n"
        return ""

    def _extract_field_default(self, field_node: ast.Call) -> str:
        """Extract default value from Field() call."""
        # Look for default or default_factory in Field() arguments
        for keyword in field_node.keywords:
            if keyword.arg == "default":
                return self._format_expr(keyword.value)
            elif keyword.arg == "default_factory":
                factory = self._format_expr(keyword.value)
                # Simplify common factories
                if factory == "list":
                    return "Field(default_factory=list)"
                elif factory == "dict":
                    return "Field(default_factory=dict)"
                elif factory == "datetime.now":
                    return "Field(default_factory=datetime.now)"
                else:
                    return f"Field(default_factory={factory})"

        # If no default found, check if first positional arg is a default
        if field_node.args:
            return self._format_expr(field_node.args[0])

        return "Field(...)"


def extract_docs(source_path: Path) -> str:
    """Extract documentation from a Python file and return as Markdown."""
    source_code = source_path.read_text()
    tree = ast.parse(source_code)

    extractor = DocExtractor()
    extractor.visit(tree)

    # Build markdown with file boundary markers
    path_str = str(source_path.absolute())
    # boundary_width = max(len(path_str) + 8, 50)
    # boundary = "*" * boundary_width

    # lines = [boundary, boundary, f"**  {path_str}  **", boundary, boundary, f"# {source_path.name}\n"]
    lines = [f"# {path_str}"]

    for section in extractor.sections:
        doc_type, signature, content, fields = section
        if doc_type == "module":
            lines.append(f"{content}\n")
        elif doc_type == "class":
            lines.append(f"## `{signature}`\n")
            if content:
                lines.append(f"{content}\n")
            if fields:
                lines.append(f"{fields}\n")
        elif doc_type in ("function", "method"):
            lines.append(f"### `{signature}`\n")
            lines.append(f"{content}\n")
        elif doc_type == "note":
            lines.append(f"> {content}\n")

    return "\n".join(lines)


def all():
    for path in os.popen("git ls-files | sort").readlines():
        path = path.rstrip()
        if ("Dockerfile" in path or
            path.endswith(".md") or
            path.endswith(".yml") or
            path.endswith(".sh")):
            print("# " + path)
            print()
            for line in open(path).readlines():
                print("    " + line.rstrip())
            print()
        elif path.endswith(".py"):
            if path.endswith("/extract_docs.py"):
                continue
            print("# " + path)
            print()
            for line in extract_docs(Path(path)).split("\n"):
                print("    " + line)
            print()


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <python_file_or_pattern> [<pattern2> ...]")
        print("Examples:")
        print(f"  {sys.argv[0]} entity.py")
        print(f"  {sys.argv[0]} *.py")
        print(f"  {sys.argv[0]} entity.py base.py")
        sys.exit(1)

    if "--all" in sys.argv[1:]:
        all()
        sys.exit(0)

    # Collect all matching files
    all_files = []
    for pattern in sys.argv[1:]:
        # Check if it's a glob pattern or a direct file path
        if "*" in pattern or "?" in pattern or "[" in pattern:
            # It's a glob pattern
            matches = glob.glob(pattern, recursive=False)
            if not matches:
                print(f"Warning: No files matched pattern '{pattern}'")
            all_files.extend(matches)
        else:
            # It's a direct file path
            path = Path(pattern)
            if path.exists():
                all_files.append(str(path))
            else:
                print(f"Warning: File not found: {pattern}")

    if not all_files:
        print("Error: No files to process")
        sys.exit(1)

    # Process each file
    for file_path_str in sorted(set(all_files)):  # Remove duplicates and sort
        source_path = Path(file_path_str)
        if not source_path.is_file():
            continue

        try:
            markdown = extract_docs(source_path)
            if False:
                output_path = source_path.with_suffix(".md")
                output_path.write_text(markdown)
                print(f"Documentation written to {output_path}")
            else:
                print(markdown)
        except Exception as e:
            print(f"Error processing {source_path}: {e}")
            continue


if __name__ == "__main__":
    main()
