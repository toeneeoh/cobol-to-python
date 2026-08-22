import pytest

from cobol_to_python import (
    ArithmeticOperator,
    BinaryExpression,
    Comparison,
    ComparisonOperator,
    IdentifierExpression,
    IntegerLiteral,
    ParseError,
    SourceLocation,
    StringLiteral,
    UnaryExpression,
    UnaryOperator,
    parse_expression,
)


def test_parses_every_literal_and_identifier_expression() -> None:
    integer = parse_expression("123")
    string = parse_expression('"a""b"')
    identifier = parse_expression("Customer-Name")

    assert isinstance(integer, IntegerLiteral)
    assert integer.value == 123
    assert isinstance(string, StringLiteral)
    assert string.value == 'a"b'
    assert isinstance(identifier, IdentifierExpression)
    assert identifier.name.spelling == "Customer-Name"
    assert identifier.name.canonical == "CUSTOMER-NAME"


def test_multiplication_has_precedence_over_addition() -> None:
    expression = parse_expression("1 + 2 * 3")

    assert isinstance(expression, BinaryExpression)
    assert expression.operator is ArithmeticOperator.ADD
    assert isinstance(expression.right, BinaryExpression)
    assert expression.right.operator is ArithmeticOperator.MULTIPLY


def test_parentheses_override_precedence_and_expand_expression_span() -> None:
    expression = parse_expression("(1 + 2) * 3")

    assert isinstance(expression, BinaryExpression)
    assert expression.operator is ArithmeticOperator.MULTIPLY
    assert isinstance(expression.left, BinaryExpression)
    assert expression.left.operator is ArithmeticOperator.ADD
    assert expression.left.span.start == SourceLocation(0, 1, 1)
    assert expression.left.span.end == SourceLocation(7, 1, 8)
    assert expression.span.start == SourceLocation(0, 1, 1)
    assert expression.span.end == SourceLocation(11, 1, 12)


@pytest.mark.parametrize(
    ("source", "outer", "inner"),
    [
        ("10 - 3 - 2", ArithmeticOperator.SUBTRACT, ArithmeticOperator.SUBTRACT),
        ("20 / 5 / 2", ArithmeticOperator.DIVIDE, ArithmeticOperator.DIVIDE),
    ],
)
def test_binary_arithmetic_is_left_associative(
    source: str,
    outer: ArithmeticOperator,
    inner: ArithmeticOperator,
) -> None:
    expression = parse_expression(source)

    assert isinstance(expression, BinaryExpression)
    assert expression.operator is outer
    assert isinstance(expression.left, BinaryExpression)
    assert expression.left.operator is inner


@pytest.mark.parametrize(
    ("source_operator", "ast_operator"),
    [
        ("=", ComparisonOperator.EQUAL),
        ("<>", ComparisonOperator.NOT_EQUAL),
        ("<", ComparisonOperator.LESS),
        ("<=", ComparisonOperator.LESS_EQUAL),
        (">", ComparisonOperator.GREATER),
        (">=", ComparisonOperator.GREATER_EQUAL),
    ],
)
def test_parses_every_comparison_operator(
    source_operator: str, ast_operator: ComparisonOperator
) -> None:
    expression = parse_expression(f"1 {source_operator} 2")

    assert isinstance(expression, Comparison)
    assert expression.operator is ast_operator


def test_comparison_operands_may_be_arithmetic_expressions() -> None:
    expression = parse_expression("1 + 2 <= 3 * 4")

    assert isinstance(expression, Comparison)
    assert isinstance(expression.left, BinaryExpression)
    assert expression.left.operator is ArithmeticOperator.ADD
    assert isinstance(expression.right, BinaryExpression)
    assert expression.right.operator is ArithmeticOperator.MULTIPLY


@pytest.mark.parametrize(
    ("source", "operator"),
    [("+7", UnaryOperator.PLUS), ("-COUNT", UnaryOperator.MINUS)],
)
def test_documented_unary_expressions(source: str, operator: UnaryOperator) -> None:
    expression = parse_expression(source)

    assert isinstance(expression, UnaryExpression)
    assert expression.operator is operator


def test_nested_parentheses_expand_only_expression_span() -> None:
    expression = parse_expression("((Mixed-Case))")

    assert isinstance(expression, IdentifierExpression)
    assert expression.span.start == SourceLocation(0, 1, 1)
    assert expression.span.end == SourceLocation(14, 1, 15)
    assert expression.name.span.start == SourceLocation(2, 1, 3)
    assert expression.name.span.end == SourceLocation(12, 1, 13)
    assert expression.name.spelling == "Mixed-Case"
    assert expression.name.canonical == "MIXED-CASE"


def test_multiline_combined_source_span() -> None:
    expression = parse_expression("1 +\n  2")

    assert isinstance(expression, BinaryExpression)
    assert expression.span.start == SourceLocation(0, 1, 1)
    assert expression.span.end == SourceLocation(7, 2, 4)


@pytest.mark.parametrize(
    ("source", "expected", "location"),
    [
        ("", "an integer", SourceLocation(0, 1, 1)),
        ("* 1", "an integer", SourceLocation(0, 1, 1)),
        ("= 1", "an integer", SourceLocation(0, 1, 1)),
        ("1 +", "an integer", SourceLocation(3, 1, 4)),
        ("(1 + 2", "')'", SourceLocation(6, 1, 7)),
        ("1 2", "end of input", SourceLocation(2, 1, 3)),
    ],
)
def test_parse_errors_report_unexpected_token_expected_text_and_location(
    source: str, expected: str, location: SourceLocation
) -> None:
    with pytest.raises(ParseError) as error:
        parse_expression(source)

    assert expected in error.value.expected
    assert error.value.token.span.start == location
    assert f"line {location.line}, column {location.column}" in str(error.value)


def test_rejects_repeated_unary_operators() -> None:
    with pytest.raises(ParseError) as error:
        parse_expression("--1")

    assert error.value.token.lexeme == "-"
    assert error.value.token.span.start == SourceLocation(1, 1, 2)


def test_rejects_trailing_tokens() -> None:
    with pytest.raises(ParseError) as error:
        parse_expression("1 DISPLAY")

    assert error.value.token.lexeme == "DISPLAY"
    assert error.value.expected == "end of input"


def test_rejects_chained_comparison_explicitly() -> None:
    with pytest.raises(ParseError) as error:
        parse_expression("1 < 2 < 3")

    assert error.value.token.kind.name == "LESS"
    assert "chained comparisons are unsupported" in error.value.expected
    assert error.value.token.span.start == SourceLocation(6, 1, 7)
