"""Deterministic Python generation from semantically analyzed COBOL v0.2."""

import json

from cobol_to_python.ast import (
    AcceptStatement,
    AddStatement,
    ArithmeticExpression,
    ArithmeticOperator,
    Comparison,
    ComparisonOperator,
    ComputeStatement,
    Condition,
    DisplayStatement,
    Expression,
    Identifier,
    IdentifierExpression,
    IfStatement,
    IntegerLiteral,
    LogicalOperator,
    MoveStatement,
    NotCondition,
    PerformTimesStatement,
    Pic9,
    SpacesLiteral,
    Statement,
    StringLiteral,
    SubtractStatement,
    UnaryExpression,
    UnaryOperator,
    ZeroLiteral,
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


def _cobol_accept_9(width: int) -> int:
    text = input()
    digits = text.removeprefix("-")
    if not digits or any(character < "0" or character > "9" for character in digits):
        raise ValueError("PIC 9 ACCEPT requires an optional minus sign and digits")
    return _cobol_assign_9(int(text), width)


def _cobol_perform_count(value: int) -> int:
    if value < 0:
        raise ValueError("PERFORM TIMES count cannot be negative")
    return value
"""


class _PythonGenerator:
    def __init__(self, analyzed: AnalyzedProgram) -> None:
        self._analyzed = analyzed
        self._lines: list[str] = []
        self._loop_index = 0

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
            elif isinstance(initial_value, SpacesLiteral):
                value = f"' ' * {symbol.declaration.picture.length}"
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
            values = ", ".join(self._expression(value) for value in statement.values)
            separator = "" if len(statement.values) == 1 else ", sep=''"
            self._line(indentation, f"print({values}{separator})")
        elif isinstance(statement, MoveStatement):
            target = self._symbol(statement.target)
            value = (
                f"' ' * {target.declaration.picture.length}"
                if isinstance(statement.value, SpacesLiteral)
                else self._expression(statement.value)
            )
            self._line(
                indentation,
                self._assignment(target, value),
            )
        elif isinstance(statement, ComputeStatement):
            target = self._symbol(statement.target)
            self._line(
                indentation,
                self._assignment(target, self._arithmetic(statement.expression)),
            )
        elif isinstance(statement, IfStatement):
            self._line(indentation, f"if {self._condition(statement.condition)}:")
            for child in statement.then_body:
                self._statement(child, indentation + 1)
            if statement.else_body is not None:
                self._line(indentation, "else:")
                for child in statement.else_body:
                    self._statement(child, indentation + 1)
        elif isinstance(statement, AcceptStatement):
            target = self._symbol(statement.target)
            width = target.declaration.picture.length
            if target.category is DataCategory.NUMERIC:
                value = f"_cobol_accept_9({width})"
                self._line(indentation, f"{_python_name(target.name)} = {value}")
            else:
                self._line(indentation, self._assignment(target, "input()"))
        elif isinstance(statement, (AddStatement, SubtractStatement)):
            target = self._symbol(statement.target)
            operator = "+" if isinstance(statement, AddStatement) else "-"
            expression = self._arithmetic(statement.expression)
            value = f"({_python_name(target.name)} {operator} {expression})"
            self._line(indentation, self._assignment(target, value))
        elif isinstance(statement, PerformTimesStatement):
            self._loop_index += 1
            index = self._loop_index
            count = self._arithmetic(statement.count)
            self._line(
                indentation,
                f"for _cobol_index_{index} in range(_cobol_perform_count({count})):",
            )
            for child in statement.body:
                self._statement(child, indentation + 1)

    def _expression(self, expression: Expression) -> str:
        if isinstance(expression, StringLiteral):
            return json.dumps(expression.value, ensure_ascii=False)
        if isinstance(expression, IdentifierExpression):
            return _python_name(expression.name)
        if isinstance(expression, SpacesLiteral):
            raise AssertionError("SPACES requires an assignment target")
        return self._arithmetic(expression)

    def _arithmetic(self, expression: ArithmeticExpression) -> str:
        if isinstance(expression, IntegerLiteral):
            return str(expression.value)
        if isinstance(expression, ZeroLiteral):
            return "0"
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

    def _condition(self, condition: Condition) -> str:
        if isinstance(condition, Comparison):
            return self._comparison(condition)
        if isinstance(condition, NotCondition):
            return f"not ({self._condition(condition.operand)})"
        operator = "and" if condition.operator is LogicalOperator.AND else "or"
        left = self._condition(condition.left)
        right = self._condition(condition.right)
        return f"({left}) {operator} ({right})"

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
