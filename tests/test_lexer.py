import pytest

from cobol_to_python import LexerError, SourceLocation, TokenKind, tokenize

KEYWORDS = {
    "COMPUTE": TokenKind.COMPUTE,
    "DATA": TokenKind.DATA,
    "DISPLAY": TokenKind.DISPLAY,
    "DIVISION": TokenKind.DIVISION,
    "ELSE": TokenKind.ELSE,
    "END-IF": TokenKind.END_IF,
    "IDENTIFICATION": TokenKind.IDENTIFICATION,
    "IF": TokenKind.IF,
    "MOVE": TokenKind.MOVE,
    "PIC": TokenKind.PIC,
    "PROCEDURE": TokenKind.PROCEDURE,
    "PROGRAM-ID": TokenKind.PROGRAM_ID,
    "RUN": TokenKind.RUN,
    "SECTION": TokenKind.SECTION,
    "STOP": TokenKind.STOP,
    "TO": TokenKind.TO,
    "VALUE": TokenKind.VALUE,
    "WORKING-STORAGE": TokenKind.WORKING_STORAGE,
    "X": TokenKind.X,
}


def kinds(source: str) -> list[TokenKind]:
    return [token.kind for token in tokenize(source)]


@pytest.mark.parametrize(("keyword", "expected"), KEYWORDS.items())
def test_every_keyword_is_case_insensitive(keyword: str, expected: TokenKind) -> None:
    mixed_case = keyword.lower().capitalize()
    token = tokenize(mixed_case)[0]
    assert token.kind is expected
    assert token.lexeme == mixed_case


def test_identifiers_preserve_original_lexemes_and_hyphens() -> None:
    tokens = tokenize("Customer-Name item-1 plain")
    assert [(token.kind, token.lexeme) for token in tokens] == [
        (TokenKind.IDENTIFIER, "Customer-Name"),
        (TokenKind.IDENTIFIER, "item-1"),
        (TokenKind.IDENTIFIER, "plain"),
        (TokenKind.EOF, ""),
    ]


def test_hyphenated_identifier_and_spaced_subtraction_are_distinct() -> None:
    assert kinds("A-B A - B") == [
        TokenKind.IDENTIFIER,
        TokenKind.IDENTIFIER,
        TokenKind.MINUS,
        TokenKind.IDENTIFIER,
        TokenKind.EOF,
    ]


def test_unary_minus_may_touch_its_operand() -> None:
    assert kinds("-7 -COUNT -(A + B)") == [
        TokenKind.MINUS,
        TokenKind.INTEGER,
        TokenKind.MINUS,
        TokenKind.IDENTIFIER,
        TokenKind.MINUS,
        TokenKind.LEFT_PAREN,
        TokenKind.IDENTIFIER,
        TokenKind.PLUS,
        TokenKind.IDENTIFIER,
        TokenKind.RIGHT_PAREN,
        TokenKind.EOF,
    ]


def test_literals_punctuation_and_all_operators() -> None:
    tokens = tokenize('123 "a""b" . ( ) + - * / = <> < <= > >=')
    assert [token.kind for token in tokens] == [
        TokenKind.INTEGER,
        TokenKind.STRING,
        TokenKind.PERIOD,
        TokenKind.LEFT_PAREN,
        TokenKind.RIGHT_PAREN,
        TokenKind.PLUS,
        TokenKind.MINUS,
        TokenKind.STAR,
        TokenKind.SLASH,
        TokenKind.EQUAL,
        TokenKind.NOT_EQUAL,
        TokenKind.LESS,
        TokenKind.LESS_EQUAL,
        TokenKind.GREATER,
        TokenKind.GREATER_EQUAL,
        TokenKind.EOF,
    ]
    assert tokens[1].lexeme == '"a""b"'


def test_comments_and_multiline_locations() -> None:
    tokens = tokenize("DISPLAY 1. *> ignored\r\n  MOVE 2 TO A.\nSTOP RUN.")
    move = tokens[3]
    stop = tokens[8]
    assert move.kind is TokenKind.MOVE
    assert move.span.start == SourceLocation(offset=25, line=2, column=3)
    assert stop.kind is TokenKind.STOP
    assert stop.span.start == SourceLocation(offset=38, line=3, column=1)


def test_token_spans_are_half_open_and_eof_is_zero_width() -> None:
    tokens = tokenize("Ab\n12")
    assert tokens[0].span.start == SourceLocation(0, 1, 1)
    assert tokens[0].span.end == SourceLocation(2, 1, 3)
    assert tokens[1].span.start == SourceLocation(3, 2, 1)
    assert tokens[1].span.end == SourceLocation(5, 2, 3)
    assert tokens[2].span.start == SourceLocation(5, 2, 3)
    assert tokens[2].span.end == SourceLocation(5, 2, 3)


def test_empty_input_produces_only_eof() -> None:
    token = tokenize("")[0]
    assert token.kind is TokenKind.EOF
    assert token.lexeme == ""
    assert token.span.start == SourceLocation(0, 1, 1)
    assert token.span.end == token.span.start


@pytest.mark.parametrize("source", ['"unterminated', '"unterminated\n'])
def test_unterminated_string_reports_start(source: str) -> None:
    with pytest.raises(LexerError) as error:
        tokenize(source)
    assert error.value.span.start == SourceLocation(0, 1, 1)
    assert "Unterminated string literal" in str(error.value)


def test_invalid_character_reports_exact_location() -> None:
    with pytest.raises(LexerError) as error:
        tokenize("DISPLAY @")
    assert error.value.span.start == SourceLocation(8, 1, 9)
    assert error.value.span.end == SourceLocation(9, 1, 10)


@pytest.mark.parametrize("source", ["9COUNT", "A-", "A--B"])
def test_malformed_identifiers_are_lexical_errors(source: str) -> None:
    with pytest.raises(LexerError):
        tokenize(source)


@pytest.mark.parametrize(
    "fragment",
    [
        'IDENTIFICATION DIVISION. PROGRAM-ID. HELLO. DISPLAY "Hello, world!".',
        "01 FIRST-NUMBER PIC 9(3) VALUE 12. COMPUTE TOTAL = FIRST-NUMBER + 2.",
        'IF COUNT >= 1 DISPLAY NAME. ELSE DISPLAY "Nobody". END-IF.',
        '*> Compare the two values.\nIF VALUE-A < VALUE-B DISPLAY "MATCH". END-IF.',
    ],
)
def test_representative_documented_program_fragments(fragment: str) -> None:
    tokens = tokenize(fragment)
    assert len(tokens) > 1
    assert tokens[-1].kind is TokenKind.EOF
