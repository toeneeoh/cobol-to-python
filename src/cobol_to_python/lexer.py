"""Tokenization for the documented COBOL v0.1 source format."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    """Kinds of tokens produced by :func:`tokenize`."""

    IDENTIFIER = auto()
    INTEGER = auto()
    STRING = auto()

    COMPUTE = auto()
    DATA = auto()
    DISPLAY = auto()
    DIVISION = auto()
    ELSE = auto()
    END_IF = auto()
    IDENTIFICATION = auto()
    IF = auto()
    MOVE = auto()
    PIC = auto()
    PROCEDURE = auto()
    PROGRAM_ID = auto()
    RUN = auto()
    SECTION = auto()
    STOP = auto()
    TO = auto()
    VALUE = auto()
    WORKING_STORAGE = auto()
    X = auto()

    PERIOD = auto()
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    EQUAL = auto()
    NOT_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    EOF = auto()


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A source position with a zero-based offset and one-based line/column."""

    offset: int
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """A half-open source range from ``start`` up to but excluding ``end``."""

    start: SourceLocation
    end: SourceLocation


@dataclass(frozen=True, slots=True)
class Token:
    """A token containing its kind, exact source spelling, and source span."""

    kind: TokenKind
    lexeme: str
    span: SourceSpan


class LexerError(ValueError):
    """Raised when source text cannot be tokenized under the v0.1 contract."""

    def __init__(self, message: str, span: SourceSpan) -> None:
        self.message = message
        self.span = span
        location = span.start
        super().__init__(f"{message} at line {location.line}, column {location.column}")


_KEYWORDS: dict[str, TokenKind] = {
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

_SINGLE_CHARACTER_TOKENS: dict[str, TokenKind] = {
    ".": TokenKind.PERIOD,
    "(": TokenKind.LEFT_PAREN,
    ")": TokenKind.RIGHT_PAREN,
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "/": TokenKind.SLASH,
    "=": TokenKind.EQUAL,
    "<": TokenKind.LESS,
    ">": TokenKind.GREATER,
}

_MULTI_CHARACTER_TOKENS: dict[str, TokenKind] = {
    "<>": TokenKind.NOT_EQUAL,
    "<=": TokenKind.LESS_EQUAL,
    ">=": TokenKind.GREATER_EQUAL,
}


class _Lexer:
    def __init__(self, source: str) -> None:
        self._source = source
        self._offset = 0
        self._line = 1
        self._column = 1

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while not self._at_end:
            character = self._current
            if character in " \t\n" or character == "\r":
                self._consume_whitespace()
            elif self._starts_with("*>"):
                self._consume_comment()
            elif _is_ascii_letter(character):
                tokens.append(self._scan_word())
            elif _is_ascii_digit(character):
                tokens.append(self._scan_integer())
            elif character == '"':
                tokens.append(self._scan_string())
            else:
                tokens.append(self._scan_symbol())

        location = self._location
        tokens.append(Token(TokenKind.EOF, "", SourceSpan(location, location)))
        return tokens

    @property
    def _at_end(self) -> bool:
        return self._offset >= len(self._source)

    @property
    def _current(self) -> str:
        return self._source[self._offset]

    @property
    def _location(self) -> SourceLocation:
        return SourceLocation(self._offset, self._line, self._column)

    def _starts_with(self, text: str) -> bool:
        return self._source.startswith(text, self._offset)

    def _advance(self) -> None:
        character = self._current
        self._offset += 1
        if character == "\n":
            self._line += 1
            self._column = 1
        else:
            self._column += 1

    def _consume_whitespace(self) -> None:
        if self._current == "\r":
            start = self._location
            self._advance()
            if self._at_end or self._current != "\n":
                raise LexerError(
                    "Carriage return must be followed by a line feed",
                    SourceSpan(start, self._location),
                )
            self._advance()
            return
        self._advance()

    def _consume_comment(self) -> None:
        while not self._at_end and self._current not in "\r\n":
            self._advance()

    def _scan_word(self) -> Token:
        start = self._location
        while not self._at_end and _is_ascii_alphanumeric(self._current):
            self._advance()

        while not self._at_end and self._current == "-":
            hyphen = self._location
            self._advance()
            if self._at_end or not _is_ascii_alphanumeric(self._current):
                end = self._location
                message = "Identifier cannot contain consecutive or trailing hyphens"
                raise LexerError(message, SourceSpan(hyphen, end))
            while not self._at_end and _is_ascii_alphanumeric(self._current):
                self._advance()

        return self._token(
            _KEYWORDS.get(self._lexeme(start).upper(), TokenKind.IDENTIFIER), start
        )

    def _scan_integer(self) -> Token:
        start = self._location
        while not self._at_end and _is_ascii_digit(self._current):
            self._advance()
        if not self._at_end and (
            _is_ascii_letter(self._current) or self._current == "-"
        ):
            while not self._at_end and (
                _is_ascii_alphanumeric(self._current) or self._current == "-"
            ):
                self._advance()
            raise LexerError("Identifier cannot begin with a digit", self._span(start))
        return self._token(TokenKind.INTEGER, start)

    def _scan_string(self) -> Token:
        start = self._location
        self._advance()
        while not self._at_end:
            if self._current in "\r\n":
                raise LexerError("Unterminated string literal", self._span(start))
            if self._current == '"':
                self._advance()
                if not self._at_end and self._current == '"':
                    self._advance()
                    continue
                return self._token(TokenKind.STRING, start)
            self._advance()
        raise LexerError("Unterminated string literal", self._span(start))

    def _scan_symbol(self) -> Token:
        start = self._location
        for lexeme, multi_kind in _MULTI_CHARACTER_TOKENS.items():
            if self._starts_with(lexeme):
                self._advance()
                self._advance()
                return self._token(multi_kind, start)

        single_kind = _SINGLE_CHARACTER_TOKENS.get(self._current)
        if single_kind is None:
            self._advance()
            raise LexerError("Invalid character", self._span(start))
        self._advance()
        return self._token(single_kind, start)

    def _lexeme(self, start: SourceLocation) -> str:
        return self._source[start.offset : self._offset]

    def _span(self, start: SourceLocation) -> SourceSpan:
        return SourceSpan(start, self._location)

    def _token(self, kind: TokenKind, start: SourceLocation) -> Token:
        return Token(kind, self._lexeme(start), self._span(start))


def _is_ascii_letter(character: str) -> bool:
    return "A" <= character <= "Z" or "a" <= character <= "z"


def _is_ascii_digit(character: str) -> bool:
    return "0" <= character <= "9"


def _is_ascii_alphanumeric(character: str) -> bool:
    return _is_ascii_letter(character) or _is_ascii_digit(character)


def tokenize(source: str) -> list[Token]:
    """Tokenize free-format COBOL source and append one zero-width EOF token.

    Token lexemes preserve their exact source spelling. Locations use zero-based
    character offsets and one-based line and column numbers. Invalid input raises
    :class:`LexerError` with the offending source span.
    """

    return _Lexer(source).tokenize()
