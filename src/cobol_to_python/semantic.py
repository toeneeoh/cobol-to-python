"""Semantic analysis for parsed COBOL v0.2 programs."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from cobol_to_python.ast import (
    AcceptStatement,
    AddStatement,
    ArithmeticExpression,
    Comparison,
    ComputeStatement,
    Condition,
    DataDeclaration,
    DisplayStatement,
    Expression,
    Identifier,
    IdentifierExpression,
    IfStatement,
    IntegerLiteral,
    LogicalCondition,
    MoveStatement,
    NotCondition,
    PerformTimesStatement,
    Pic9,
    Program,
    SpacesLiteral,
    Statement,
    StringLiteral,
    SubtractStatement,
    UnaryExpression,
    ZeroLiteral,
)
from cobol_to_python.lexer import SourceSpan


class DataCategory(Enum):
    """The two data categories supported by COBOL v0.1."""

    ALPHANUMERIC = "alphanumeric"
    NUMERIC = "numeric"


@dataclass(frozen=True, slots=True)
class Symbol:
    """A resolved working-storage declaration."""

    name: Identifier
    declaration: DataDeclaration
    category: DataCategory


@dataclass(frozen=True, slots=True)
class AnalyzedProgram:
    """A parsed program paired with its immutable canonical-name symbol map."""

    program: Program
    symbols: Mapping[str, Symbol]


class SemanticError(ValueError):
    """A semantic violation associated with a source span."""

    def __init__(
        self,
        message: str,
        span: SourceSpan,
        *,
        original_span: SourceSpan | None = None,
    ) -> None:
        self.message = message
        self.span = span
        self.original_span = original_span
        location = span.start
        super().__init__(f"{message} at line {location.line}, column {location.column}")


class _Analyzer:
    def __init__(self, program: Program) -> None:
        self._program = program
        self._symbols: dict[str, Symbol] = {}

    def analyze(self) -> AnalyzedProgram:
        self._declare_symbols()
        self._check_initializers()
        for statement in self._program.statements:
            self._check_statement(statement)
        return AnalyzedProgram(
            self._program,
            MappingProxyType(self._symbols.copy()),
        )

    def _declare_symbols(self) -> None:
        for declaration in self._program.declarations:
            canonical = declaration.name.canonical
            existing = self._symbols.get(canonical)
            if existing is not None:
                raise SemanticError(
                    f"Duplicate declaration {declaration.name.spelling!r}",
                    declaration.name.span,
                    original_span=existing.name.span,
                )
            self._symbols[canonical] = Symbol(
                declaration.name,
                declaration,
                _declaration_category(declaration),
            )

    def _check_initializers(self) -> None:
        for symbol in self._symbols.values():
            declaration = symbol.declaration
            initial_value = declaration.initial_value
            if initial_value is None:
                continue
            value_category = _literal_category(initial_value)
            if value_category is not symbol.category:
                raise SemanticError(
                    f"{symbol.name.spelling!r} requires {symbol.category.value} value",
                    initial_value.span,
                )
            if isinstance(initial_value, StringLiteral):
                if len(initial_value.value) > declaration.picture.length:
                    raise SemanticError(
                        f"Initial value for {symbol.name.spelling!r} "
                        "exceeds picture width",
                        initial_value.span,
                    )
            elif (
                isinstance(initial_value, IntegerLiteral)
                and len(str(initial_value.value)) > declaration.picture.length
            ):
                raise SemanticError(
                    f"Initial value for {symbol.name.spelling!r} exceeds picture width",
                    initial_value.span,
                )

    def _check_statement(self, statement: Statement) -> None:
        if isinstance(statement, DisplayStatement):
            for value in statement.values:
                self._expression_category(value)
        elif isinstance(statement, MoveStatement):
            target = self._resolve(statement.target)
            source_category = (
                DataCategory.ALPHANUMERIC
                if isinstance(statement.value, SpacesLiteral)
                else self._expression_category(statement.value)
            )
            if source_category is not target.category:
                raise SemanticError(
                    f"Cannot move {source_category.value} value to "
                    f"{target.category.value} item {target.name.spelling!r}",
                    statement.target.span,
                )
        elif isinstance(statement, ComputeStatement):
            target = self._resolve(statement.target)
            if target.category is not DataCategory.NUMERIC:
                raise SemanticError(
                    f"COMPUTE target {target.name.spelling!r} must be numeric",
                    statement.target.span,
                )
            self._arithmetic_category(statement.expression)
        elif isinstance(statement, AcceptStatement):
            self._resolve(statement.target)
        elif isinstance(statement, (AddStatement, SubtractStatement)):
            target = self._resolve(statement.target)
            if target.category is not DataCategory.NUMERIC:
                raise SemanticError(
                    f"{type(statement).__name__.removesuffix('Statement').upper()} "
                    "target "
                    f"{target.name.spelling!r} must be numeric",
                    statement.target.span,
                )
            self._arithmetic_category(statement.expression)
        elif isinstance(statement, IfStatement):
            self._check_condition(statement.condition)
            for child in statement.then_body:
                self._check_statement(child)
            if statement.else_body is not None:
                for child in statement.else_body:
                    self._check_statement(child)
        elif isinstance(statement, PerformTimesStatement):
            self._arithmetic_category(statement.count)
            for child in statement.body:
                self._check_statement(child)

    def _check_condition(self, condition: Condition) -> None:
        if isinstance(condition, Comparison):
            self._check_comparison(condition)
        elif isinstance(condition, NotCondition):
            self._check_condition(condition.operand)
        elif isinstance(condition, LogicalCondition):
            self._check_condition(condition.left)
            self._check_condition(condition.right)

    def _check_comparison(self, comparison: Comparison) -> None:
        left = self._expression_category(comparison.left)
        right = self._expression_category(comparison.right)
        if left is not right:
            raise SemanticError(
                "Comparison operands must have the same data category",
                comparison.right.span,
            )

    def _expression_category(self, expression: Expression) -> DataCategory:
        if isinstance(expression, SpacesLiteral):
            raise SemanticError(
                "SPACE or SPACES is valid only for alphanumeric assignment "
                "or initialization",
                expression.span,
            )
        if isinstance(expression, StringLiteral):
            return DataCategory.ALPHANUMERIC
        if isinstance(expression, IdentifierExpression):
            return self._resolve(expression.name).category
        return self._arithmetic_category(expression)

    def _arithmetic_category(self, expression: ArithmeticExpression) -> DataCategory:
        if isinstance(expression, (IntegerLiteral, ZeroLiteral)):
            return DataCategory.NUMERIC
        if isinstance(expression, IdentifierExpression):
            symbol = self._resolve(expression.name)
            if symbol.category is not DataCategory.NUMERIC:
                raise SemanticError(
                    f"Arithmetic identifier {symbol.name.spelling!r} must be numeric",
                    expression.name.span,
                )
            return DataCategory.NUMERIC
        if isinstance(expression, UnaryExpression):
            return self._arithmetic_category(expression.operand)
        self._arithmetic_category(expression.left)
        self._arithmetic_category(expression.right)
        return DataCategory.NUMERIC

    def _resolve(self, name: Identifier) -> Symbol:
        symbol = self._symbols.get(name.canonical)
        if symbol is None:
            raise SemanticError(
                f"Undeclared identifier {name.spelling!r}",
                name.span,
            )
        return symbol


def _declaration_category(declaration: DataDeclaration) -> DataCategory:
    if isinstance(declaration.picture, Pic9):
        return DataCategory.NUMERIC
    return DataCategory.ALPHANUMERIC


def _literal_category(
    literal: IntegerLiteral | StringLiteral | ZeroLiteral | SpacesLiteral,
) -> DataCategory:
    if isinstance(literal, (IntegerLiteral, ZeroLiteral)):
        return DataCategory.NUMERIC
    return DataCategory.ALPHANUMERIC


def analyze_program(program: Program) -> AnalyzedProgram:
    """Resolve and validate one parsed COBOL v0.2 program."""

    return _Analyzer(program).analyze()
