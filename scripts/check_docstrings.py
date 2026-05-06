"""Check that all functions have proper docstrings with args, returns, and description."""

import ast
import sys
from typing import List


class DocstringChecker(ast.NodeVisitor):
    """Check function docstrings for required sections."""

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

        self.generic_visit(node)

    def _annotation_is_none(self, annotation: ast.expr | None) -> bool:
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
    try:
        with open(filename, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filename)
    except SyntaxError as e:
        print(f"{filename}: Syntax error: {e}")
        return False

    checker = DocstringChecker(filename)
    checker.visit(tree)

    if checker.errors:
        for error in checker.errors:
            print(error)
        return False

    return True


def main() -> int:
    """Run validation on all file paths provided by pre-commit.

    returns:
        Process exit code: 0 on success, 1 on validation failures.
    """
    if not sys.argv[1:]:
        return 0

    all_passed = True
    for filename in sys.argv[1:]:
        if filename.endswith(".py"):
            if not check_file(filename):
                all_passed = False

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
