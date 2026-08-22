"""Deterministic Python generation from semantically analyzed COBOL v0.1."""

import json

from cobol_to_python.ast import (
    ArithmeticExpression,
    ArithmeticOperator,
    Comparison,
    ComparisonOperator,
    ComputeStatement,
    DisplayStatement,
    Expression,
    Identifier,
    IdentifierExpression,
    IfStatement,
    IntegerLiteral,
    MoveStatement,
    Pic9,
    Statement,
    StringLiteral,
    UnaryExpression,
    UnaryOperator,
)
from cobol_to_python.semantic import AnalyzedProgram, DataCategory, Symbol

_ARITHMETIC_OPERATORS: dict[ArithmeticOperator, str] = {
    ArithmeticOperator.ADD: "+",
    ArithmeticOperator.SUBTRACT: "-",
    ArithmeticOperator.MULTIPLY: "*",
}

_COMPARISON_OPERATORS: dict[ComparisonOperator, str] = {
    ComparisonOperator.EQUAL: "==",
    ComparisonOperator.NOT_EQUAL: "!=",
    ComparisonOperator.LESS: "<",
    ComparisonOperator.LESS_EQUAL: "<=",
    ComparisonOperator.GREATER: ">",
    ComparisonOperator.GREATER_EQUAL: ">=",
}

_RUNTIME_HELPERS = """def _cobol_assign_x(value: str, width: int) -> str:
    if not isinstance(value, str):
        raise TypeError("PIC X assignment requires a string")
    if len(value) > width:
        raise ValueError("PIC X assignment exceeds picture width")
    return value.ljust(width)


def _cobol_assign_9(value: int, width: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("PIC 9 assignment requires an integer")
    if len(str(abs(value))) > width:
        raise ValueError("PIC 9 assignment exceeds picture width")
    return value


def _cobol_divide(left: int, right: int) -> int:
    if right == 0:
        raise ZeroDivisionError("COBOL division by zero")
    quotient = abs(left) // abs(right)
    return -quotient if (left < 0) != (right < 0) else quotient
"""


class _PythonGenerator:
    def __init__(self, analyzed: AnalyzedProgram) -> None:
        self._analyzed = analyzed
        self._lines: list[str] = []

    def generate(self) -> str:
        self._lines.extend(
            [
                _RUNTIME_HELPERS.rstrip(),
                "",
                "",
                "def main() -> None:",
            ]
        )
        for declaration in self._analyzed.program.declarations:
            symbol = self._symbol(declaration.name)
            initial_value = declaration.initial_value
            if initial_value is None:
                value = "0" if symbol.category is DataCategory.NUMERIC else "''"
            else:
                value = self._expression(initial_value)
            self._line(1, self._assignment(symbol, value))

        for statement in self._analyzed.program.statements:
            self._statement(statement, 1)
        if (
            not self._analyzed.program.declarations
            and not self._analyzed.program.statements
        ):
            self._line(1, "pass")
        self._lines.extend(
            [
                "",
                "",
                'if __name__ == "__main__":',
                "    main()",
            ]
        )
        return "\n".join(self._lines) + "\n"

    def _statement(self, statement: Statement, indentation: int) -> None:
        if isinstance(statement, DisplayStatement):
            self._line(indentation, f"print({self._expression(statement.value)})")
        elif isinstance(statement, MoveStatement):
            target = self._symbol(statement.target)
            self._line(
                indentation,
                self._assignment(target, self._expression(statement.value)),
            )
        elif isinstance(statement, ComputeStatement):
            target = self._symbol(statement.target)
            self._line(
                indentation,
                self._assignment(target, self._arithmetic(statement.expression)),
            )
        elif isinstance(statement, IfStatement):
            self._line(indentation, f"if {self._comparison(statement.condition)}:")
            for child in statement.then_body:
                self._statement(child, indentation + 1)
            if statement.else_body is not None:
                self._line(indentation, "else:")
                for child in statement.else_body:
                    self._statement(child, indentation + 1)

    def _expression(self, expression: Expression) -> str:
        if isinstance(expression, StringLiteral):
            return json.dumps(expression.value, ensure_ascii=False)
        if isinstance(expression, IdentifierExpression):
            return _python_name(expression.name)
        return self._arithmetic(expression)

    def _arithmetic(self, expression: ArithmeticExpression) -> str:
        if isinstance(expression, IntegerLiteral):
            return str(expression.value)
        if isinstance(expression, IdentifierExpression):
            return _python_name(expression.name)
        if isinstance(expression, UnaryExpression):
            operator = "+" if expression.operator is UnaryOperator.PLUS else "-"
            return f"({operator}{self._arithmetic(expression.operand)})"
        left = self._arithmetic(expression.left)
        right = self._arithmetic(expression.right)
        if expression.operator is ArithmeticOperator.DIVIDE:
            return f"_cobol_divide({left}, {right})"
        operator = _ARITHMETIC_OPERATORS[expression.operator]
        return f"({left} {operator} {right})"

    def _comparison(self, comparison: Comparison) -> str:
        left = self._expression(comparison.left)
        right = self._expression(comparison.right)
        operator = _COMPARISON_OPERATORS[comparison.operator]
        return f"{left} {operator} {right}"

    def _assignment(self, symbol: Symbol, value: str) -> str:
        name = _python_name(symbol.name)
        width = symbol.declaration.picture.length
        helper = (
            "_cobol_assign_9"
            if isinstance(symbol.declaration.picture, Pic9)
            else "_cobol_assign_x"
        )
        return f"{name} = {helper}({value}, {width})"

    def _symbol(self, name: Identifier) -> Symbol:
        return self._analyzed.symbols[name.canonical]

    def _line(self, indentation: int, text: str) -> None:
        self._lines.append(f"{'    ' * indentation}{text}")


def _python_name(identifier: Identifier) -> str:
    return f"cobol_{identifier.canonical.lower().replace('-', '_')}"


def generate_python(analyzed: AnalyzedProgram) -> str:
    """Generate deterministic, consistently formatted Python source."""

    return _PythonGenerator(analyzed).generate()
