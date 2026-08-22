import pytest

from cobol_to_python import (
    ArithmeticOperator,
    BinaryExpression,
    ComparisonOperator,
    ComputeStatement,
    DisplayStatement,
    IdentifierExpression,
    IfStatement,
    IntegerLiteral,
    MoveStatement,
    ParseError,
    ProcedureDivision,
    SourceLocation,
    StopRun,
    StringLiteral,
    UnaryExpression,
    parse_procedure_division,
)

HEADER = "PROCEDURE DIVISION."


def parse_body(body: str) -> ProcedureDivision:
    return parse_procedure_division(f"{HEADER}\n{body}\nSTOP RUN.")


def test_empty_procedure_body_contains_only_final_stop() -> None:
    division = parse_procedure_division(f"{HEADER}\nSTOP RUN.")

    assert division.statements == ()
    assert isinstance(division.stop_run, StopRun)
    assert division.span.start == SourceLocation(0, 1, 1)
    assert division.span.end == SourceLocation(29, 2, 10)


@pytest.mark.parametrize(
    ("operand", "node_type"),
    [
        ("1", IntegerLiteral),
        ('"hello"', StringLiteral),
        ("Customer-Name", IdentifierExpression),
        ("-1", UnaryExpression),
        ("1 + 2", BinaryExpression),
        ("(1 + 2)", BinaryExpression),
    ],
)
def test_display_accepts_every_documented_operand_form(
    operand: str, node_type: type[object]
) -> None:
    statement = parse_body(f"DISPLAY {operand}.").statements[0]

    assert isinstance(statement, DisplayStatement)
    assert isinstance(statement.values[0], node_type)


@pytest.mark.parametrize("source", ['"Ada"', "SOURCE-NAME", "12"])
def test_move_accepts_literal_and_identifier_sources(source: str) -> None:
    statement = parse_body(f"MOVE {source} TO Target-Name.").statements[0]

    assert isinstance(statement, MoveStatement)
    assert statement.target.spelling == "Target-Name"
    assert statement.target.canonical == "TARGET-NAME"


def test_compute_parses_mixed_precedence_expression() -> None:
    statement = parse_body("COMPUTE TOTAL = 1 + 2 * 3.").statements[0]

    assert isinstance(statement, ComputeStatement)
    assert isinstance(statement.expression, BinaryExpression)
    assert statement.expression.operator is ArithmeticOperator.ADD
    assert isinstance(statement.expression.right, BinaryExpression)
    assert statement.expression.right.operator is ArithmeticOperator.MULTIPLY


def test_multiple_statements_preserve_order() -> None:
    division = parse_body('DISPLAY "A". MOVE 1 TO COUNT. COMPUTE COUNT = COUNT + 1.')

    assert [type(statement) for statement in division.statements] == [
        DisplayStatement,
        MoveStatement,
        ComputeStatement,
    ]


def test_if_without_else_and_statement_after_end_if() -> None:
    division = parse_body('IF A = 1 DISPLAY "YES". END-IF. DISPLAY "DONE".')
    conditional = division.statements[0]

    assert isinstance(conditional, IfStatement)
    assert conditional.condition.operator is ComparisonOperator.EQUAL
    assert conditional.else_body is None
    assert conditional.else_span is None
    assert isinstance(division.statements[1], DisplayStatement)


def test_if_with_else_has_ordered_branches() -> None:
    conditional = parse_body(
        'IF A <> B DISPLAY "NO". ELSE MOVE B TO A. DISPLAY "YES". END-IF.'
    ).statements[0]

    assert isinstance(conditional, IfStatement)
    assert isinstance(conditional.then_body[0], DisplayStatement)
    assert conditional.else_body is not None
    assert [type(statement) for statement in conditional.else_body] == [
        MoveStatement,
        DisplayStatement,
    ]


def test_nested_if_binds_else_to_nearest_unclosed_if() -> None:
    conditional = parse_body(
        "IF A = 1 "
        'IF B = 2 DISPLAY "B". ELSE DISPLAY "NOT-B". END-IF. '
        'ELSE DISPLAY "NOT-A". END-IF.'
    ).statements[0]

    assert isinstance(conditional, IfStatement)
    inner = conditional.then_body[0]
    assert isinstance(inner, IfStatement)
    assert inner.else_body is not None
    assert conditional.else_body is not None


def test_keywords_are_case_insensitive() -> None:
    division = parse_procedure_division('procedure division. display "ok". stop run.')

    assert isinstance(division.statements[0], DisplayStatement)


def test_statement_branch_expression_and_division_spans() -> None:
    source = (
        "PROCEDURE DIVISION.\n"
        "IF A >= 1\n"
        '  DISPLAY "YES".\n'
        "ELSE\n"
        "  COMPUTE A = A + 1.\n"
        "END-IF.\n"
        "STOP RUN."
    )
    division = parse_procedure_division(source)
    conditional = division.statements[0]

    assert isinstance(conditional, IfStatement)
    assert conditional.span.start == SourceLocation(20, 2, 1)
    assert conditional.span.end == SourceLocation(80, 6, 8)
    assert conditional.then_span.start == SourceLocation(32, 3, 3)
    assert conditional.then_span.end == SourceLocation(46, 3, 17)
    assert conditional.else_span is not None
    assert conditional.else_span.start == SourceLocation(54, 5, 3)
    assert conditional.else_span.end == SourceLocation(72, 5, 21)
    assert conditional.condition.right.span.start == SourceLocation(28, 2, 9)
    assert conditional.condition.right.span.end == SourceLocation(29, 2, 10)
    assert division.span.start == SourceLocation(0, 1, 1)
    assert division.span.end == SourceLocation(90, 7, 10)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("", "'PROCEDURE'"),
        ("DIVISION. STOP RUN.", "'PROCEDURE'"),
        ("PROCEDURE SECTION. STOP RUN.", "'DIVISION'"),
        ("PROCEDURE DIVISION STOP RUN.", "'.' after PROCEDURE DIVISION"),
    ],
)
def test_rejects_missing_or_malformed_header(source: str, expected: str) -> None:
    with pytest.raises(ParseError) as error:
        parse_procedure_division(source)

    assert expected in error.value.expected


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("DISPLAY.", "an integer"),
        ("MOVE TO TARGET.", "an integer"),
        ("MOVE 1 TARGET.", "'TO'"),
        ("MOVE 1 TO.", "an identifier after TO"),
        ("COMPUTE = 1.", "an identifier after COMPUTE"),
        ("COMPUTE A 1.", "'='"),
        ("COMPUTE A =.", "an integer"),
        ("IF A DISPLAY A. END-IF.", "a comparison operator"),
        ("IF A = DISPLAY A. END-IF.", "an integer"),
    ],
)
def test_rejects_missing_operands_targets_and_condition_parts(
    statement: str, expected: str
) -> None:
    with pytest.raises(ParseError) as error:
        parse_body(statement)

    assert expected in error.value.expected


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('IF A = 1 DISPLAY "A".', "'ELSE' or 'END-IF'"),
        ('IF A = 1 DISPLAY "A". ELSE END-IF.', "a statement in the IF branch"),
        ("IF A = 1 END-IF.", "a statement in the IF branch"),
        ('ELSE DISPLAY "A".', "ACCEPT, ADD, SUBTRACT, DISPLAY"),
        ('END-IF. DISPLAY "A".', "ACCEPT, ADD, SUBTRACT, DISPLAY"),
        ('IF A = 1 DISPLAY "A". END-IF. END-IF.', "ACCEPT, ADD, SUBTRACT, DISPLAY"),
    ],
)
def test_rejects_malformed_if_terminators(body: str, expected: str) -> None:
    source = f"{HEADER}\n{body}"
    with pytest.raises(ParseError) as error:
        parse_procedure_division(source)

    assert expected in error.value.expected


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('DISPLAY "A" STOP RUN.', "'.' after DISPLAY operand"),
        ('DISPLAY "A".. STOP RUN.', "ACCEPT, ADD, SUBTRACT, DISPLAY"),
        ("PERFORM WORK. STOP RUN.", "'TIMES' after PERFORM count"),
        ("STOP.", "'RUN' after STOP"),
        ("STOP RUN", "'.' after STOP RUN"),
        ("STOP RUN. DISPLAY 1.", "end of input after STOP RUN"),
        ("DISPLAY 1.", "final 'STOP RUN.'"),
    ],
)
def test_rejects_invalid_starters_periods_stop_and_trailing_input(
    body: str, expected: str
) -> None:
    with pytest.raises(ParseError) as error:
        parse_procedure_division(f"{HEADER}\n{body}")

    assert expected in error.value.expected
    assert error.value.token.span.start.line >= 2
