"""Check that function-local variable assignments are declared at the top of functions."""

import ast
import os
import sys
from typing import List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notebook_utils import extract_notebook_code_cells  # noqa: E402


class LocalVariablePlacementChecker(ast.NodeVisitor):
    """Check that assignments at function scope appear before other statements."""

    def __init__(self, filename: str):
        """Initialize the checker for one file.

        args:
            filename: Path of the file being validated.
        """
        self.filename = filename
        self.errors: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check one function definition for top-of-body assignments.

        args:
            node: AST node for the function definition.
        """
        self._check_function_body(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check one async function definition for top-of-body assignments.

        args:
            node: AST node for the async function definition.
        """
        self._check_function_body(node)
        self.generic_visit(node)

    def _check_function_body(self, node: ast.AST) -> None:
        """Validate that new local names are introduced in the initial block.

        args:
            node: AST function node whose body will be inspected.
        """
        index = 0
        declared_names = set()
        seen_non_declaration = False

        body = list(getattr(node, "body", []))
        if not body:
            return

        if ast.get_docstring(node):
            index = 1
        for statement in body[index:]:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                assigned_names = self._assigned_names(statement)
                if seen_non_declaration:
                    late_names = sorted(
                        name for name in assigned_names if name not in declared_names
                    )
                    if late_names:
                        self.errors.append(
                            f"{self.filename}:{statement.lineno}: "
                            f"Function '{getattr(node, 'name', '<unknown>')}' introduces new local "
                            f"variable(s) after the initial block: {', '.join(late_names)}"
                        )
                else:
                    declared_names.update(assigned_names)
                continue

            if isinstance(statement, ast.AugAssign):
                continue

            else:
                seen_non_declaration = True

    def _assigned_names(self, statement: ast.stmt) -> Set[str]:
        """Return the names assigned by a top-level assignment statement.

        args:
            statement: Assignment statement to inspect.

        returns:
            Set of assigned variable names.
        """
        names: Set[str] = set()
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                names.update(self._extract_target_names(target))
        elif isinstance(statement, ast.AnnAssign):
            names.update(self._extract_target_names(statement.target))
        return names

    def _extract_target_names(self, target: ast.expr) -> Set[str]:
        """Extract variable names from an assignment target.

        args:
            target: Assignment target node.

        returns:
            Set of target variable names.
        """
        names: Set[str] = set()
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                names.update(self._extract_target_names(element))
        return names


def check_file(filename: str) -> bool:
    """Check a single Python file for function-local variable placement.

    args:
        filename: Path to a Python file to validate.

    returns:
        True when file passes checks, otherwise False.
    """
    checker: Optional[LocalVariablePlacementChecker] = None
    try:
        with open(filename, "r", encoding="utf-8") as file_handle:
            tree = ast.parse(file_handle.read(), filename=filename)
    except SyntaxError as error:
        print(f"{filename}: Syntax error: {error}")
        return False

    checker = LocalVariablePlacementChecker(filename)
    checker.visit(tree)

    if checker.errors:
        for error in checker.errors:
            print(error)
        return False

    return True


def check_notebook_file(filename: str) -> bool:
    """Check a Jupyter notebook for function-local variable placement.

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

        checker = LocalVariablePlacementChecker(cell_label)
        checker.visit(tree)

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
