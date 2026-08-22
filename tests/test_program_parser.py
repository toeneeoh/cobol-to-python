import pytest

from cobol_to_python import (
    ComputeStatement,
    DisplayStatement,
    IfStatement,
    LexerError,
    MoveStatement,
    ParseError,
    Pic9,
    PicX,
    SourceLocation,
    parse_program,
)

ACCEPTED_PROGRAMS = (
    """IDENTIFICATION DIVISION.
PROGRAM-ID. HELLO.
DATA DIVISION.
WORKING-STORAGE SECTION.
PROCEDURE DIVISION.
DISPLAY "Hello, world!".
STOP RUN.""",
    """IDENTIFICATION DIVISION.
PROGRAM-ID. TOTALS.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 FIRST-NUMBER PIC 9(3) VALUE 12.
01 SECOND-NUMBER PIC 9(3) VALUE 8.
01 TOTAL PIC 9(4).
PROCEDURE DIVISION.
COMPUTE TOTAL = FIRST-NUMBER + SECOND-NUMBER * 2.
DISPLAY TOTAL.
STOP RUN.""",
    """IDENTIFICATION DIVISION.
PROGRAM-ID. GREETING.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 NAME PIC X(10) VALUE "Ada".
01 COUNT PIC 9(2) VALUE 3.
PROCEDURE DIVISION.
IF COUNT >= 1
    DISPLAY NAME.
ELSE
    DISPLAY "Nobody".
END-IF.
MOVE "Grace" TO NAME.
DISPLAY NAME.
STOP RUN.""",
    """IDENTIFICATION DIVISION.
PROGRAM-ID. CLASSIFY.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 VALUE-A PIC 9(2) VALUE 5.
01 VALUE-B PIC 9(2) VALUE 8.
PROCEDURE DIVISION.
*> Compare the two values.
IF VALUE-A < VALUE-B
    IF VALUE-A = 5
        DISPLAY "MATCH".
    ELSE
        DISPLAY "LOWER".
    END-IF.
ELSE
    DISPLAY "NOT-LOWER".
END-IF.
STOP RUN.""",
)


@pytest.mark.parametrize("source", ACCEPTED_PROGRAMS)
def test_parses_every_documented_accepted_program(source: str) -> None:
    program = parse_program(source)

    assert program.span.start == SourceLocation(0, 1, 1)
    assert program.span.end.offset == len(source)


def test_minimal_complete_program_allows_empty_data_and_statement_lists() -> None:
    source = """IDENTIFICATION DIVISION.
PROGRAM-ID. EMPTY-PROGRAM.
DATA DIVISION.
WORKING-STORAGE SECTION.
PROCEDURE DIVISION.
STOP RUN."""
    program = parse_program(source)

    assert program.identification.name.spelling == "EMPTY-PROGRAM"
    assert program.identification.name.canonical == "EMPTY-PROGRAM"
    assert program.declarations == ()
    assert program.statements == ()


def test_program_with_all_declarations_and_statements_preserves_order() -> None:
    source = """IDENTIFICATION DIVISION.
PROGRAM-ID. ALL-FORMS.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 TEXT-ITEM PIC X(5) VALUE "A".
01 NUMBER-ITEM PIC 9(3) VALUE 1.
PROCEDURE DIVISION.
DISPLAY TEXT-ITEM.
MOVE "B" TO TEXT-ITEM.
COMPUTE NUMBER-ITEM = NUMBER-ITEM + 2 * 3.
IF NUMBER-ITEM >= 1
    DISPLAY NUMBER-ITEM.
ELSE
    DISPLAY 0.
END-IF.
STOP RUN."""
    program = parse_program(source)

    assert [item.name.spelling for item in program.declarations] == [
        "TEXT-ITEM",
        "NUMBER-ITEM",
    ]
    assert isinstance(program.declarations[0].picture, PicX)
    assert isinstance(program.declarations[1].picture, Pic9)
    assert [type(statement) for statement in program.statements] == [
        DisplayStatement,
        MoveStatement,
        ComputeStatement,
        IfStatement,
    ]


def test_mixed_case_keywords_comments_and_program_id_spelling() -> None:
    source = """identification division.
program-id. Mixed-Name.
*> data follows
data division.
working-storage section.
procedure division.
*> final action
stop run."""
    program = parse_program(source)

    assert program.identification.name.spelling == "Mixed-Name"
    assert program.identification.name.canonical == "MIXED-NAME"


def test_complete_program_and_division_spans() -> None:
    source = """IDENTIFICATION DIVISION.
PROGRAM-ID. SPANS.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(1).
PROCEDURE DIVISION.
DISPLAY A.
STOP RUN."""
    program = parse_program(source)

    assert program.identification.span.start == SourceLocation(0, 1, 1)
    assert program.identification.span.end == SourceLocation(43, 2, 19)
    assert program.data_division.span.start == SourceLocation(44, 3, 1)
    assert program.data_division.span.end == SourceLocation(98, 5, 15)
    assert program.procedure_division.span.start == SourceLocation(99, 6, 1)
    assert program.procedure_division.span.end.offset == len(source)
    assert program.span.start == SourceLocation(0, 1, 1)
    assert program.span.end.offset == len(source)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("", "'IDENTIFICATION'"),
        ("DATA DIVISION. WORKING-STORAGE SECTION.", "'IDENTIFICATION'"),
        (
            "IDENTIFICATION SECTION. PROGRAM-ID. A.",
            "'DIVISION'",
        ),
        (
            "IDENTIFICATION DIVISION PROGRAM-ID. A.",
            "'.' after IDENTIFICATION DIVISION",
        ),
        (
            "IDENTIFICATION DIVISION. PROGRAM-ID A.",
            "'.' after PROGRAM-ID",
        ),
        (
            "IDENTIFICATION DIVISION. PROGRAM-ID..",
            "a program identifier",
        ),
        (
            "IDENTIFICATION DIVISION. PROGRAM-ID. A DATA DIVISION.",
            "'.' after the program identifier",
        ),
    ],
)
def test_rejects_missing_or_malformed_identification(
    source: str, expected: str
) -> None:
    with pytest.raises(ParseError) as error:
        parse_program(source)

    assert expected in error.value.expected


BASE_IDENTIFICATION = "IDENTIFICATION DIVISION. PROGRAM-ID. TEST."
DATA = "DATA DIVISION. WORKING-STORAGE SECTION."
PROCEDURE = "PROCEDURE DIVISION. STOP RUN."


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (f"{BASE_IDENTIFICATION} {PROCEDURE}", "'DATA'"),
        (f"{BASE_IDENTIFICATION} {DATA}", "'PROCEDURE'"),
        (f"{DATA} {BASE_IDENTIFICATION} {PROCEDURE}", "'IDENTIFICATION'"),
        (f"{BASE_IDENTIFICATION} {PROCEDURE} {DATA}", "'DATA'"),
        (f"{BASE_IDENTIFICATION} {DATA} {DATA} {PROCEDURE}", "'PROCEDURE'"),
        (
            f"{BASE_IDENTIFICATION} {DATA} {PROCEDURE} {PROCEDURE}",
            "end of input after the complete program",
        ),
        (
            f"{BASE_IDENTIFICATION} ENVIRONMENT DIVISION. {DATA} {PROCEDURE}",
            "'DATA'",
        ),
        (
            f"{BASE_IDENTIFICATION} {DATA} ENVIRONMENT DIVISION. {PROCEDURE}",
            "'PROCEDURE'",
        ),
        (
            f"{BASE_IDENTIFICATION} {DATA} {PROCEDURE} DISPLAY 1.",
            "end of input after the complete program",
        ),
        (
            f"{BASE_IDENTIFICATION} DATA DIVISION. {PROCEDURE}",
            "'WORKING-STORAGE'",
        ),
        (
            f"{BASE_IDENTIFICATION} {DATA} PROCEDURE DIVISION.",
            "final 'STOP RUN.'",
        ),
    ],
)
def test_enforces_required_order_and_rejects_extra_content(
    source: str, expected: str
) -> None:
    with pytest.raises(ParseError) as error:
        parse_program(source)

    assert expected in error.value.expected


def test_propagates_lexical_error_with_original_location() -> None:
    source = f"{BASE_IDENTIFICATION}\n{DATA}\n01 9COUNT PIC 9(2).\n{PROCEDURE}"

    with pytest.raises(LexerError) as error:
        parse_program(source)

    assert error.value.span.start.line == 3
    assert error.value.span.start.column == 4


def test_propagates_nested_parse_error_with_original_location() -> None:
    source = (
        f"{BASE_IDENTIFICATION}\n{DATA}\nPROCEDURE DIVISION.\n"
        'IF A = 1\nDISPLAY "A".\nSTOP RUN.'
    )

    with pytest.raises(ParseError) as error:
        parse_program(source)

    assert error.value.token.kind.name == "STOP"
    assert error.value.token.span.start.line == 6


def test_semantic_errors_remain_structurally_parseable() -> None:
    source = """IDENTIFICATION DIVISION.
PROGRAM-ID. DEFERRED.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 COUNT PIC 9(2).
PROCEDURE DIVISION.
MOVE "TEN" TO COUNT.
DISPLAY MISSING-NAME.
STOP RUN."""

    program = parse_program(source)
    assert len(program.statements) == 2


@pytest.mark.parametrize(
    "unsupported",
    [
        "PERFORM WORK.",
        "GO TO WORK.",
    ],
)
def test_unsupported_statements_are_parse_errors(unsupported: str) -> None:
    source = f"{BASE_IDENTIFICATION} {DATA} PROCEDURE DIVISION. {unsupported} STOP RUN."

    with pytest.raises(ParseError):
        parse_program(source)
