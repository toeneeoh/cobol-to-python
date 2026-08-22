import pytest

from cobol_to_python import (
    DataDivision,
    IntegerLiteral,
    ParseError,
    Pic9,
    PicX,
    SourceLocation,
    StringLiteral,
    parse_data_division,
)

HEADER = "DATA DIVISION.\nWORKING-STORAGE SECTION."


def test_parses_empty_working_storage_section() -> None:
    division = parse_data_division(HEADER)

    assert division == DataDivision((), division.span)
    assert division.span.start == SourceLocation(0, 1, 1)
    assert division.span.end == SourceLocation(39, 2, 25)


def test_parses_one_alphanumeric_declaration_without_value() -> None:
    division = parse_data_division(f"{HEADER}\n01 CUSTOMER-NAME PIC X(20).")
    declaration = division.declarations[0]

    assert declaration.name.spelling == "CUSTOMER-NAME"
    assert declaration.name.canonical == "CUSTOMER-NAME"
    assert declaration.initial_value is None
    assert isinstance(declaration.picture, PicX)
    assert declaration.picture.length == 20


def test_parses_one_numeric_declaration_with_integer_value() -> None:
    division = parse_data_division(f"{HEADER}\n01 Count-1 PIC 9(3) VALUE 12.")
    declaration = division.declarations[0]

    assert declaration.name.spelling == "Count-1"
    assert declaration.name.canonical == "COUNT-1"
    assert isinstance(declaration.picture, Pic9)
    assert declaration.picture.length == 3
    assert isinstance(declaration.initial_value, IntegerLiteral)
    assert declaration.initial_value.value == 12


def test_preserves_multiple_declarations_in_source_order() -> None:
    source = f'{HEADER}\n01 First-Name PIC X(8) VALUE "Ada".\n01 ITEM-COUNT PIC 9(2).'
    declarations = parse_data_division(source).declarations

    assert [item.name.spelling for item in declarations] == [
        "First-Name",
        "ITEM-COUNT",
    ]
    assert isinstance(declarations[0].initial_value, StringLiteral)
    assert declarations[1].initial_value is None


def test_keywords_are_case_insensitive() -> None:
    division = parse_data_division(
        'data division. working-storage section. 01 Name pic x(3) value "Ada".'
    )

    assert isinstance(division.declarations[0].picture, PicX)


def test_declaration_picture_literal_and_division_spans() -> None:
    source = f'{HEADER}\n01 NAME PIC X(4) VALUE "Ada".'
    division = parse_data_division(source)
    declaration = division.declarations[0]
    picture = declaration.picture
    literal = declaration.initial_value

    assert declaration.span.start == SourceLocation(40, 3, 1)
    assert declaration.span.end == SourceLocation(69, 3, 30)
    assert picture.span.start == SourceLocation(48, 3, 9)
    assert picture.span.end == SourceLocation(56, 3, 17)
    assert isinstance(literal, StringLiteral)
    assert literal.span.start == SourceLocation(63, 3, 24)
    assert literal.span.end == SourceLocation(68, 3, 29)
    assert division.span.start == SourceLocation(0, 1, 1)
    assert division.span.end == declaration.span.end


def test_both_literal_types_are_syntactically_permitted_for_either_picture() -> None:
    source = (
        f'{HEADER}\n01 NUMERIC-ITEM PIC 9(2) VALUE "X".\n01 TEXT-ITEM PIC X(2) VALUE 7.'
    )
    declarations = parse_data_division(source).declarations

    assert isinstance(declarations[0].initial_value, StringLiteral)
    assert isinstance(declarations[1].initial_value, IntegerLiteral)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("", "'DATA'"),
        ("DIVISION. WORKING-STORAGE SECTION.", "'DATA'"),
        ("DATA SECTION. WORKING-STORAGE SECTION.", "'DIVISION'"),
        ("DATA DIVISION WORKING-STORAGE SECTION.", "'.' after DATA DIVISION"),
        ("DATA DIVISION. SECTION.", "'WORKING-STORAGE'"),
        ("DATA DIVISION. WORKING-STORAGE DIVISION.", "'SECTION'"),
        ("DATA DIVISION. WORKING-STORAGE SECTION", "'.' after WORKING-STORAGE"),
    ],
)
def test_rejects_missing_or_malformed_headers(source: str, expected: str) -> None:
    with pytest.raises(ParseError) as error:
        parse_data_division(source)

    assert expected in error.value.expected


@pytest.mark.parametrize("level", ["02", "77", "1"])
def test_rejects_unsupported_level_numbers(level: str) -> None:
    with pytest.raises(ParseError) as error:
        parse_data_division(f"{HEADER} {level} NAME PIC X(1).")

    assert error.value.expected == "level number '01'"


@pytest.mark.parametrize(
    ("declaration", "expected"),
    [
        ("01 PIC X(1).", "a data name"),
        ("01 NAME X(1).", "'PIC'"),
        ("01 NAME PIC A(1).", "picture type 'X' or '9'"),
        ("01 NAME PIC X(0).", "greater than zero"),
        ("01 NAME PIC X(-1).", "a positive picture length"),
        ("01 NAME PIC X().", "a positive picture length"),
        ("01 NAME PIC X(ABC).", "a positive picture length"),
        ("01 NAME PIC X 1).", "'(' after picture type"),
        ("01 NAME PIC X(1.", "')' after picture length"),
        ("01 NAME PIC X(1)).", "declaration-ending '.'"),
        ("01 NAME PIC X(1) VALUE.", "an integer or string literal"),
        ("01 NAME PIC X(1) VALUE OTHER.", "an integer or string literal"),
        ("01 NAME PIC X(1)", "declaration-ending '.'"),
        ("01 NAME PIC X(1) PIC 9(1).", "duplicate PIC clause"),
        ("01 NAME PIC X(1) VALUE 1 VALUE 2.", "duplicate VALUE clause"),
    ],
)
def test_rejects_malformed_declarations(declaration: str, expected: str) -> None:
    with pytest.raises(ParseError) as error:
        parse_data_division(f"{HEADER} {declaration}")

    assert expected in error.value.expected
    assert error.value.token.span.start.line >= 2


def test_rejects_trailing_non_declaration_tokens_with_location() -> None:
    with pytest.raises(ParseError) as error:
        parse_data_division(f"{HEADER}\nDISPLAY 1.")

    assert error.value.token.lexeme == "DISPLAY"
    assert error.value.token.span.start == SourceLocation(40, 3, 1)
    assert "level-01 declaration or end of input" in error.value.expected
