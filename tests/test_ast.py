from dataclasses import FrozenInstanceError

import pytest

from cobol_to_python import (
    ArithmeticOperator,
    BinaryExpression,
    Comparison,
    ComparisonOperator,
    ComputeStatement,
    DataDeclaration,
    DataDivision,
    DisplayStatement,
    Identifier,
    IdentifierExpression,
    IfStatement,
    IntegerLiteral,
    MoveStatement,
    Pic9,
    PicX,
    ProcedureDivision,
    Program,
    ProgramIdentification,
    SourceLocation,
    SourceSpan,
    StopRun,
    StringLiteral,
    UnaryExpression,
    UnaryOperator,
)


def span(start: int = 0, end: int = 1) -> SourceSpan:
    return SourceSpan(
        SourceLocation(start, 1, start + 1),
        SourceLocation(end, 1, end + 1),
    )


def test_identifier_preserves_spelling_and_provides_canonical_form() -> None:
    name = Identifier("Customer-Name", span())
    same_canonical_name = Identifier("CUSTOMER-NAME", span())

    assert name.spelling == "Customer-Name"
    assert name.canonical == "CUSTOMER-NAME"
    assert same_canonical_name.canonical == name.canonical


def test_picture_and_literal_nodes() -> None:
    node_span = span()
    assert PicX(10, node_span).length == 10
    assert Pic9(4, node_span).length == 4
    assert IntegerLiteral(12, node_span).value == 12
    assert StringLiteral('He said "hello"', node_span).value == 'He said "hello"'


def test_data_declarations_with_and_without_initial_values() -> None:
    node_span = span()
    name = Identifier("COUNT", node_span)
    initial = IntegerLiteral(3, node_span)

    initialized = DataDeclaration(name, Pic9(2, node_span), initial, node_span)
    uninitialized = DataDeclaration(name, PicX(8, node_span), None, node_span)

    assert initialized.initial_value is initial
    assert uninitialized.initial_value is None


def test_nested_arithmetic_expressions() -> None:
    node_span = span()
    one = IntegerLiteral(1, node_span)
    two = IntegerLiteral(2, node_span)
    negative_two = UnaryExpression(UnaryOperator.MINUS, two, node_span)
    expression = BinaryExpression(
        one,
        ArithmeticOperator.ADD,
        BinaryExpression(
            negative_two,
            ArithmeticOperator.MULTIPLY,
            IntegerLiteral(3, node_span),
            node_span,
        ),
        node_span,
    )

    assert expression.right.left == negative_two
    assert expression.span is node_span


def test_comparison_and_simple_statement_nodes() -> None:
    node_span = span()
    target = Identifier("TOTAL", node_span)
    reference = IdentifierExpression(target, node_span)
    integer = IntegerLiteral(10, node_span)
    comparison = Comparison(
        reference, ComparisonOperator.GREATER_EQUAL, integer, node_span
    )

    assert DisplayStatement((reference,), node_span).values == (reference,)
    assert MoveStatement(integer, target, node_span).target is target
    assert ComputeStatement(target, integer, node_span).expression is integer
    assert comparison.operator is ComparisonOperator.GREATER_EQUAL


def test_nested_conditionals_and_optional_else_branches() -> None:
    node_span = span()
    condition = Comparison(
        IntegerLiteral(1, node_span),
        ComparisonOperator.EQUAL,
        IntegerLiteral(1, node_span),
        node_span,
    )
    display = DisplayStatement((StringLiteral("YES", node_span),), node_span)
    inner = IfStatement(condition, (display,), node_span, None, None, node_span)
    outer = IfStatement(
        condition,
        (inner,),
        node_span,
        (display,),
        node_span,
        node_span,
    )

    assert inner.else_body is None
    assert outer.then_body == (inner,)
    assert outer.else_body == (display,)


def test_complete_program_and_stop_run() -> None:
    node_span = span(0, 100)
    name = Identifier("Example", span(20, 27))
    identification = ProgramIdentification(name, span(0, 28))
    declaration = DataDeclaration(name, PicX(10, span()), None, span())
    statement = DisplayStatement((IdentifierExpression(name, span()),), span())
    stop_run = StopRun(span(90, 99))
    data_division = DataDivision((declaration,), node_span)
    procedure_division = ProcedureDivision((statement,), stop_run, node_span)
    program = Program(identification, data_division, procedure_division, node_span)

    assert program.identification is identification
    assert program.data_division is data_division
    assert program.procedure_division is procedure_division
    assert program.declarations == (declaration,)
    assert program.statements == (statement,)
    assert program.stop_run is stop_run
    assert program.span is node_span


def test_nodes_have_structural_equality() -> None:
    node_span = span()
    left = IntegerLiteral(42, node_span)
    right = IntegerLiteral(42, node_span)

    assert left == right
    assert left != IntegerLiteral(43, node_span)


def test_nodes_are_immutable_and_slotted() -> None:
    literal = IntegerLiteral(1, span())

    with pytest.raises(FrozenInstanceError):
        literal.value = 2  # type: ignore[misc]
    assert not hasattr(literal, "__dict__")


def test_every_documented_operator_has_an_enum_member() -> None:
    assert {operator.value for operator in UnaryOperator} == {"+", "-"}
    assert {operator.value for operator in ArithmeticOperator} == {
        "+",
        "-",
        "*",
        "/",
    }
    assert {operator.value for operator in ComparisonOperator} == {
        "=",
        "<>",
        "<",
        "<=",
        ">",
        ">=",
    }
