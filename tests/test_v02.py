from __future__ import annotations

import builtins
from collections.abc import Iterator

import pytest

from cobol_to_python import (
    AddStatement,
    DisplayStatement,
    LogicalCondition,
    LogicalOperator,
    NotCondition,
    PerformTimesStatement,
    SemanticError,
    SpacesLiteral,
    SubtractStatement,
    TokenKind,
    ZeroLiteral,
    parse_expression,
    parse_program,
    tokenize,
    transpile,
)


def program(data: str, body: str) -> str:
    return f"""IDENTIFICATION DIVISION.
PROGRAM-ID. V-TWO.
DATA DIVISION.
WORKING-STORAGE SECTION.
{data}PROCEDURE DIVISION.
{body}STOP RUN.
"""


def execute(source: str, inputs: list[str] | None = None) -> list[str]:
    output: list[str] = []
    values: Iterator[str] = iter(inputs or [])
    namespace: dict[str, object] = {"__name__": "generated"}
    original_input = builtins.input
    original_print = builtins.print
    builtins.input = lambda: next(values)
    builtins.print = lambda *args, sep=" ", end="\n": output.append(
        sep.join(str(arg) for arg in args) + end.removesuffix("\n")
    )
    try:
        exec(transpile(source), namespace)
        namespace["main"]()  # type: ignore[index, operator]
    finally:
        builtins.input = original_input
        builtins.print = original_print
    return output


def test_all_new_keywords_are_reserved_case_insensitively() -> None:
    source = (
        "accept add and end-perform from not or perform space spaces "
        "subtract times zero zeros"
    )
    kinds = [token.kind for token in tokenize(source)[:-1]]
    assert kinds == [
        TokenKind.ACCEPT,
        TokenKind.ADD,
        TokenKind.AND,
        TokenKind.END_PERFORM,
        TokenKind.FROM,
        TokenKind.NOT,
        TokenKind.OR,
        TokenKind.PERFORM,
        TokenKind.SPACE,
        TokenKind.SPACES,
        TokenKind.SUBTRACT,
        TokenKind.TIMES,
        TokenKind.ZERO,
        TokenKind.ZEROS,
    ]


def test_figuratives_and_multiple_display_operands_parse() -> None:
    parsed = parse_program(
        program(
            "01 TEXT PIC X(4) VALUE SPACES.\n01 COUNT PIC 9(2) VALUE ZERO.\n",
            'DISPLAY "#" COUNT.\nMOVE SPACE TO TEXT.\n',
        )
    )
    assert isinstance(parsed.declarations[0].initial_value, SpacesLiteral)
    assert isinstance(parsed.declarations[1].initial_value, ZeroLiteral)
    display = parsed.statements[0]
    assert isinstance(display, DisplayStatement)
    assert len(display.values) == 2


def test_condition_precedence_and_not() -> None:
    condition = parse_expression("A = 1 OR B = 2 AND NOT C = 3")
    assert isinstance(condition, LogicalCondition)
    assert condition.operator is LogicalOperator.OR
    assert isinstance(condition.right, LogicalCondition)
    assert condition.right.operator is LogicalOperator.AND
    assert isinstance(condition.right.right, NotCondition)


def test_add_subtract_and_nested_perform_parse() -> None:
    parsed = parse_program(
        program(
            "01 N PIC 9(2) VALUE 1.\n",
            "PERFORM 2 TIMES\nADD 2 TO N.\nPERFORM 1 TIMES\n"
            "SUBTRACT 1 FROM N.\nEND-PERFORM.\nEND-PERFORM.\n",
        )
    )
    outer = parsed.statements[0]
    assert isinstance(outer, PerformTimesStatement)
    assert isinstance(outer.body[0], AddStatement)
    assert isinstance(outer.body[1], PerformTimesStatement)
    assert isinstance(outer.body[1].body[0], SubtractStatement)


def test_v02_runtime_behavior() -> None:
    source = program(
        "01 NAME PIC X(5).\n01 N PIC 9(2) VALUE ZERO.\n",
        "ACCEPT NAME.\nACCEPT N.\nPERFORM 2 TIMES\nADD 3 TO N.\n"
        'END-PERFORM.\nSUBTRACT 1 FROM N.\nDISPLAY "Hi " NAME " " N.\n',
    )
    assert execute(source, ["Ada", "4"]) == ["Hi Ada   9"]


@pytest.mark.parametrize("value", ["", "+1", "1.5", "abc"])
def test_accept_numeric_rejects_invalid_input(value: str) -> None:
    source = program("01 N PIC 9(2).\n", "ACCEPT N.\n")
    with pytest.raises(ValueError, match="PIC 9 ACCEPT"):
        execute(source, [value])


def test_negative_perform_count_is_runtime_error() -> None:
    source = program("", 'PERFORM -1 TIMES\nDISPLAY "never".\nEND-PERFORM.\n')
    with pytest.raises(ValueError, match="cannot be negative"):
        execute(source)


@pytest.mark.parametrize(
    "data, body",
    [
        ("01 NAME PIC X(4).\n", "ADD 1 TO NAME.\n"),
        ("01 N PIC 9(2).\n", "MOVE SPACES TO N.\n"),
        ("", "DISPLAY SPACES.\n"),
    ],
)
def test_new_contextual_semantic_errors(data: str, body: str) -> None:
    with pytest.raises(SemanticError):
        transpile(program(data, body))


def test_perform_count_is_evaluated_once_and_zero_is_allowed() -> None:
    source = program(
        "01 N PIC 9(2) VALUE 2.\n",
        "PERFORM N TIMES\nDISPLAY N.\nSUBTRACT 1 FROM N.\nEND-PERFORM.\n"
        'PERFORM ZERO TIMES\nDISPLAY "never".\nEND-PERFORM.\n',
    )
    assert execute(source) == ["2", "1"]
