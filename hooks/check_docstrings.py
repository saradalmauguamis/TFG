"""Check that all functions have proper docstrings and comments with length limits."""

import ast
import io
import os
import sys
import tokenize
from typing import List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notebook_utils import extract_notebook_code_cells  # noqa: E402

MAX_DOCSTRING_LINE_LENGTH = 100


class DocstringChecker(ast.NodeVisitor):
    """Check function docstrings for required sections and line length."""

    def __init__(self, filename: str):
        """Initialize the checker for one file.

        args:
            filename: Path of the file being validated.
        """
        self.filename = filename
        self.errors: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check one function definition for required docstring sections.

        args:
            node: AST node for the function definition.
        """
        docstring = ast.get_docstring(node)
        lines: List[str] = []
        has_args_section = False
        has_params = False
        has_returns_section = False
        has_return_annotation = False
        returns_none = False

        if not docstring:
            self.errors.append(
                f"{self.filename}:{node.lineno}: Function '{node.name}' missing docstring"
            )
            return

        # Check for brief description (first line)
        lines = docstring.strip().split("\n")
        if not lines[0].strip():
            self.errors.append(
                f"{self.filename}:{node.lineno}: "
                f"Function '{node.name}' docstring missing brief description"
            )

        # Check for args section (if function has arguments)
        has_args_section = "args:" in docstring
        has_params = len(node.args.args) > 0 or len(node.args.posonlyargs) > 0

        if has_params and not has_args_section:
            self.errors.append(
                f"{self.filename}:{node.lineno}: "
                f"Function '{node.name}' missing 'args:' section in docstring"
            )

        # Check for returns section (if function has return type annotation or explicit returns)
        has_returns_section = "returns:" in docstring
        has_return_annotation = node.returns is not None
        returns_none = self._annotation_is_none(node.returns)

        if has_return_annotation and not returns_none and not has_returns_section:
            self.errors.append(
                f"{self.filename}:{node.lineno}: "
                f"Function '{node.name}' missing 'returns:' section in docstring"
            )

        self._check_docstring_length(node, docstring)

        self.generic_visit(node)

    def visit_Module(self, node: ast.Module) -> None:
        """Check the module docstring for length.

        args:
            node: AST module node.
        """
        docstring = ast.get_docstring(node)
        if docstring and node.body:
            self._check_docstring_length(node, docstring, node.body[0].lineno)

        self.generic_visit(node)

    def _check_docstring_length(
        self, node: ast.AST, docstring: str, start_lineno: Optional[int] = None
    ) -> None:
        """Check that each docstring line stays within the configured length.

        args:
            node: AST node that owns the docstring.
            docstring: Extracted docstring text.
            start_lineno: Line number of the first docstring line.
        """
        base_lineno = (
            start_lineno if start_lineno is not None else getattr(node, "lineno", 1)
        )
        lines = docstring.splitlines()
        for offset, line in enumerate(lines):
            if len(line) > MAX_DOCSTRING_LINE_LENGTH:
                self.errors.append(
                    f"{self.filename}:{base_lineno + offset}: "
                    f"Docstring line exceeds {MAX_DOCSTRING_LINE_LENGTH} characters"
                )

    def _annotation_is_none(self, annotation: Optional[ast.expr]) -> bool:
        """Return whether an annotation is exactly None.

        args:
            annotation: Function return annotation node.

        returns:
            True when annotation is `None`, otherwise False.
        """
        if annotation is None:
            return False

        if isinstance(annotation, ast.Constant):
            return annotation.value is None

        if isinstance(annotation, ast.Name):
            return annotation.id == "None"

        return False


def check_file(filename: str) -> bool:
    """Check a single Python file for docstring compliance.

    args:
        filename: Path to a Python file to validate.

    returns:
        True when file passes checks, otherwise False.
    """
    checker: Optional[DocstringChecker] = None
    try:
        with open(filename, "r", encoding="utf-8") as f:
            source = f.read()
            tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        print(f"{filename}: Syntax error: {e}")
        return False

    checker = DocstringChecker(filename)
    checker.visit(tree)

    checker.errors.extend(_check_comment_lengths(source, filename))

    if checker.errors:
        for error in checker.errors:
            print(error)
        return False

    return True


def _check_comment_lengths(source: str, filename: str) -> List[str]:
    """Check that comment lines stay within the configured length.

    args:
        source: File contents to scan.
        filename: Path of the file being validated.

    returns:
        Validation errors for long comment lines.
    """
    errors: List[str] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        comment = token.string.lstrip("#").strip()
        if len(comment) > MAX_DOCSTRING_LINE_LENGTH:
            errors.append(
                f"{filename}:{token.start[0]}: Comment line exceeds "
                f"{MAX_DOCSTRING_LINE_LENGTH} characters"
            )
    return errors


def _check_code_line_lengths(source: str, tree: ast.AST, filename: str) -> List[str]:
    """Check that non-comment, non-docstring code lines stay within max length.

    args:
        source: Source code to scan.
        tree: Parsed AST of the source.
        filename: Path or label used in error messages.

    returns:
        Validation errors for long code lines.
    """
    errors: List[str] = []
    comment_lines: Set[int] = set()
    docstring_lines: Set[int] = set()

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            comment_lines.add(token.start[0])
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            ):
                start = node.body[0].lineno
                end = getattr(node.body[0], "end_lineno", start)
                for lineno in range(start, end + 1):
                    docstring_lines.add(lineno)

    for i, line in enumerate(source.splitlines(), start=1):
        if i in comment_lines or i in docstring_lines:
            continue
        if len(line) > MAX_DOCSTRING_LINE_LENGTH:
            errors.append(
                f"{filename}:{i}: Code line exceeds {MAX_DOCSTRING_LINE_LENGTH} characters"
            )

    return errors


def check_notebook_file(filename: str) -> bool:
    """Check a Jupyter notebook for docstring compliance and line length.

    args:
        filename: Path to a .ipynb file to validate.

    returns:
        True when all cells pass checks, otherwise False.
    """
    all_passed = True
    try:
        cells = extract_notebook_code_cells(filename)
    except (KeyError, ValueError) as e:
        print(f"{filename}: Could not parse notebook: {e}")
        return False

    for cell_position, source in cells:
        cell_label = f"{filename} [cell {cell_position}]"
        try:
            tree = ast.parse(source, filename=cell_label)
        except SyntaxError:
            continue

        checker = DocstringChecker(cell_label)
        checker.visit(tree)
        checker.errors.extend(_check_comment_lengths(source, cell_label))
        checker.errors.extend(_check_code_line_lengths(source, tree, cell_label))

        if checker.errors:
            for error in checker.errors:
                print(error)
            all_passed = False

    return all_passed


def main() -> int:
    """Run validation on all file paths provided by pre-commit.

    returns:
        Process exit code: 0 on success, 1 on validation failures.
    """
    all_passed = True
    if not sys.argv[1:]:
        return 0

    for filename in sys.argv[1:]:
        if filename.endswith(".py"):
            if not check_file(filename):
                all_passed = False
        elif filename.endswith(".ipynb"):
            if not check_notebook_file(filename):
                all_passed = False

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
