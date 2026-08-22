"""Typed abstract syntax tree for the documented COBOL v0.1 subset."""

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from cobol_to_python.lexer import SourceSpan


@dataclass(frozen=True, slots=True)
class Identifier:
    """A COBOL name with its original spelling and case-insensitive form."""

    spelling: str
    span: SourceSpan

    @property
    def canonical(self) -> str:
        """Return the uppercase form used for case-insensitive name lookup."""

        return self.spelling.upper()


@dataclass(frozen=True, slots=True)
class PicX:
    """A fixed-width alphanumeric ``PIC X(n)`` specification."""

    length: int
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class Pic9:
    """A fixed-width numeric ``PIC 9(n)`` specification."""

    length: int
    span: SourceSpan


Picture: TypeAlias = PicX | Pic9


@dataclass(frozen=True, slots=True)
class IntegerLiteral:
    """An integer literal's semantic value."""

    value: int
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class StringLiteral:
    """A string literal's decoded semantic value."""

    value: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IdentifierExpression:
    """A reference to a data item whose category is resolved later."""

    name: Identifier
    span: SourceSpan


class UnaryOperator(Enum):
    """Operators accepted by a unary arithmetic expression."""

    PLUS = "+"
    MINUS = "-"


class ArithmeticOperator(Enum):
    """Operators accepted by a binary arithmetic expression."""

    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"


class ComparisonOperator(Enum):
    """Operators accepted by a comparison."""

    EQUAL = "="
    NOT_EQUAL = "<>"
    LESS = "<"
    LESS_EQUAL = "<="
    GREATER = ">"
    GREATER_EQUAL = ">="


@dataclass(frozen=True, slots=True)
class UnaryExpression:
    """A unary arithmetic operation."""

    operator: UnaryOperator
    operand: "ArithmeticExpression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class BinaryExpression:
    """A binary arithmetic operation."""

    left: "ArithmeticExpression"
    operator: ArithmeticOperator
    right: "ArithmeticExpression"
    span: SourceSpan


Literal: TypeAlias = IntegerLiteral | StringLiteral
ArithmeticExpression: TypeAlias = (
    IntegerLiteral | IdentifierExpression | UnaryExpression | BinaryExpression
)
Expression: TypeAlias = ArithmeticExpression | StringLiteral


@dataclass(frozen=True, slots=True)
class DataDeclaration:
    """A level-01 working-storage declaration."""

    name: Identifier
    picture: Picture
    initial_value: Literal | None
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class DataDivision:
    """A complete data division containing ordered working-storage items."""

    declarations: tuple[DataDeclaration, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class Comparison:
    """A comparison between two expressions."""

    left: Expression
    operator: ComparisonOperator
    right: Expression
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class DisplayStatement:
    """A statement that displays one expression."""

    value: Expression
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class MoveStatement:
    """A statement that moves a value into a data item."""

    value: Expression
    target: Identifier
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ComputeStatement:
    """A statement that computes an arithmetic value into a data item."""

    target: Identifier
    expression: ArithmeticExpression
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IfStatement:
    """A conditional with a non-empty then branch and optional else branch."""

    condition: Comparison
    then_body: tuple["Statement", ...]
    then_span: SourceSpan
    else_body: tuple["Statement", ...] | None
    else_span: SourceSpan | None
    span: SourceSpan


Statement: TypeAlias = DisplayStatement | MoveStatement | ComputeStatement | IfStatement


@dataclass(frozen=True, slots=True)
class StopRun:
    """The mandatory final ``STOP RUN.`` construct."""

    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ProcedureDivision:
    """A complete procedure division with its mandatory final stop."""

    statements: tuple[Statement, ...]
    stop_run: StopRun
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ProgramIdentification:
    """A program's identification division and program name."""

    name: Identifier
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class Program:
    """A complete COBOL v0.1 program."""

    identification: ProgramIdentification
    declarations: tuple[DataDeclaration, ...]
    statements: tuple[Statement, ...]
    stop_run: StopRun
    span: SourceSpan
