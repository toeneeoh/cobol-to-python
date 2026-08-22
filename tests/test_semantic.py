from types import MappingProxyType

import pytest

from cobol_to_python import (
    DataCategory,
    SemanticError,
    analyze_program,
    parse_program,
)


def program(data: str = "", procedure: str = ""):  # type: ignore[no-untyped-def]
    source = f"""IDENTIFICATION DIVISION.
PROGRAM-ID. SEMANTICS.
DATA DIVISION.
WORKING-STORAGE SECTION.
{data}PROCEDURE DIVISION.
{procedure}STOP RUN."""
    return parse_program(source)


def test_analyzes_empty_program_with_immutable_symbols() -> None:
    parsed = program()
    analyzed = analyze_program(parsed)

    assert analyzed.program is parsed
    assert analyzed.symbols == {}
    assert isinstance(analyzed.symbols, MappingProxyType)
    with pytest.raises(TypeError):
        analyzed.symbols["NEW"] = object()  # type: ignore[index,assignment]


def test_resolves_mixed_case_and_hyphenated_names() -> None:
    analyzed = analyze_program(
        program("01 Customer-Count PIC 9(2).\n", "DISPLAY customer-count.\n")
    )

    symbol = analyzed.symbols["CUSTOMER-COUNT"]
    assert symbol.name.spelling == "Customer-Count"
    assert symbol.category is DataCategory.NUMERIC


def test_duplicate_declarations_are_case_insensitive() -> None:
    parsed = program("01 Count PIC 9(1).\n01 COUNT PIC 9(1).\n")

    with pytest.raises(SemanticError) as error:
        analyze_program(parsed)

    assert "Duplicate declaration" in str(error.value)
    assert error.value.span.start.line == 6
    assert error.value.original_span is not None
    assert error.value.original_span.start.line == 5


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ("01 TEXT PIC X(3) VALUE 1.\n", "requires alphanumeric value"),
        ('01 COUNT PIC 9(2) VALUE "1".\n', "requires numeric value"),
        ('01 TEXT PIC X(2) VALUE "ABC".\n', "exceeds picture width"),
        ("01 COUNT PIC 9(2) VALUE 123.\n", "exceeds picture width"),
    ],
)
def test_rejects_invalid_initializers(data: str, message: str) -> None:
    with pytest.raises(SemanticError) as error:
        analyze_program(program(data))

    assert message in str(error.value)


@pytest.mark.parametrize(
    "procedure",
    [
        "DISPLAY MISSING.\n",
        "MOVE MISSING TO COUNT.\n",
        "MOVE 1 TO MISSING.\n",
        "COMPUTE MISSING = 1.\n",
        "IF MISSING = 1 DISPLAY 1. END-IF.\n",
    ],
)
def test_rejects_undeclared_names_in_every_statement_context(
    procedure: str,
) -> None:
    with pytest.raises(SemanticError) as error:
        analyze_program(program("01 COUNT PIC 9(2).\n", procedure))

    assert "Undeclared identifier" in str(error.value)
    assert error.value.span.start.line >= 7


def test_move_requires_matching_categories() -> None:
    parsed = program(
        "01 TEXT PIC X(3).\n01 COUNT PIC 9(2).\n",
        "MOVE TEXT TO COUNT.\n",
    )

    with pytest.raises(SemanticError) as error:
        analyze_program(parsed)

    assert "Cannot move alphanumeric value to numeric item" in str(error.value)


def test_compute_target_and_arithmetic_identifiers_must_be_numeric() -> None:
    text_target = program("01 TEXT PIC X(3).\n", "COMPUTE TEXT = 1.\n")
    text_operand = program(
        "01 TEXT PIC X(3).\n01 COUNT PIC 9(2).\n",
        "COMPUTE COUNT = TEXT + 1.\n",
    )

    with pytest.raises(SemanticError, match="COMPUTE target"):
        analyze_program(text_target)
    with pytest.raises(SemanticError, match="Arithmetic identifier"):
        analyze_program(text_operand)


def test_comparisons_require_matching_categories_in_nested_if() -> None:
    parsed = program(
        "01 TEXT PIC X(3).\n01 COUNT PIC 9(2).\n",
        'IF COUNT = 1 IF TEXT = COUNT DISPLAY "X". END-IF. END-IF.\n',
    )

    with pytest.raises(SemanticError) as error:
        analyze_program(parsed)

    assert "Comparison operands must have the same data category" in str(error.value)


def test_valid_move_compute_comparisons_and_nested_branches() -> None:
    parsed = program(
        '01 TEXT PIC X(5) VALUE "A".\n01 COUNT PIC 9(3) VALUE 1.\n',
        """MOVE "B" TO TEXT.
COMPUTE COUNT = COUNT + 2 * 3.
IF TEXT = "B"
    DISPLAY TEXT.
ELSE
    IF COUNT >= 1
        DISPLAY COUNT.
    ELSE
        DISPLAY 0.
    END-IF.
END-IF.
""",
    )

    analyzed = analyze_program(parsed)
    assert set(analyzed.symbols) == {"TEXT", "COUNT"}


def test_documented_program_analyzes_successfully() -> None:
    parsed = parse_program(
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
STOP RUN."""
    )

    analyze_program(parsed)


def test_semantic_error_reports_original_source_location() -> None:
    parsed = program("01 COUNT PIC 9(2).\n", "DISPLAY Missing-Name.\n")

    with pytest.raises(SemanticError) as error:
        analyze_program(parsed)

    location = error.value.span.start
    assert location.line == 7
    assert location.column == 9
    assert "line 7, column 9" in str(error.value)
