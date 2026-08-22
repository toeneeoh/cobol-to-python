"""Recursive-descent parsing for standalone COBOL v0.1 expressions."""

from dataclasses import replace
from typing import TypeAlias

from cobol_to_python.ast import (
    ArithmeticExpression,
    ArithmeticOperator,
    BinaryExpression,
    Comparison,
    ComparisonOperator,
    Expression,
    Identifier,
    IdentifierExpression,
    IntegerLiteral,
    StringLiteral,
    UnaryExpression,
    UnaryOperator,
)
from cobol_to_python.lexer import SourceSpan, Token, TokenKind, tokenize

ParsedExpression: TypeAlias = Expression | Comparison


class ParseError(ValueError):
    """An unexpected token encountered while parsing an expression."""

    def __init__(self, token: Token, expected: str) -> None:
        self.token = token
        self.span = token.span
        self.expected = expected
        found = "end of input" if token.kind is TokenKind.EOF else repr(token.lexeme)
        location = token.span.start
        super().__init__(
            f"Unexpected {found} at line {location.line}, column {location.column}; "
            f"expected {expected}"
        )


class _TokenCursor:
    """Minimal token navigation shared by recursive-descent parser levels."""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._index = 0

    @property
    def current(self) -> Token:
        return self._tokens[self._index]

    def advance(self) -> Token:
        token = self.current
        if token.kind is not TokenKind.EOF:
            self._index += 1
        return token

    def match(self, *kinds: TokenKind) -> Token | None:
        if self.current.kind not in kinds:
            return None
        return self.advance()

    def expect(self, kind: TokenKind, expected: str) -> Token:
        if self.current.kind is not kind:
            raise ParseError(self.current, expected)
        return self.advance()


_ARITHMETIC_OPERATORS: dict[TokenKind, ArithmeticOperator] = {
    TokenKind.PLUS: ArithmeticOperator.ADD,
    TokenKind.MINUS: ArithmeticOperator.SUBTRACT,
    TokenKind.STAR: ArithmeticOperator.MULTIPLY,
    TokenKind.SLASH: ArithmeticOperator.DIVIDE,
}

_COMPARISON_OPERATORS: dict[TokenKind, ComparisonOperator] = {
    TokenKind.EQUAL: ComparisonOperator.EQUAL,
    TokenKind.NOT_EQUAL: ComparisonOperator.NOT_EQUAL,
    TokenKind.LESS: ComparisonOperator.LESS,
    TokenKind.LESS_EQUAL: ComparisonOperator.LESS_EQUAL,
    TokenKind.GREATER: ComparisonOperator.GREATER,
    TokenKind.GREATER_EQUAL: ComparisonOperator.GREATER_EQUAL,
}

_COMPARISON_KINDS = tuple(_COMPARISON_OPERATORS)


class _ExpressionParser:
    def __init__(self, tokens: list[Token]) -> None:
        self._cursor = _TokenCursor(tokens)

    def parse(self) -> ParsedExpression:
        left = self._parse_expression()
        operator_token = self._cursor.match(*_COMPARISON_KINDS)
        if operator_token is None:
            self._expect_eof()
            return left

        right = self._parse_expression()
        if self._cursor.current.kind in _COMPARISON_OPERATORS:
            raise ParseError(
                self._cursor.current,
                "end of input; chained comparisons are unsupported",
            )
        self._expect_eof()
        return Comparison(
            left,
            _COMPARISON_OPERATORS[operator_token.kind],
            right,
            _combined_span(left.span, right.span),
        )

    def _parse_expression(self) -> Expression:
        if self._cursor.current.kind is TokenKind.STRING:
            token = self._cursor.advance()
            return StringLiteral(_decode_string(token.lexeme), token.span)
        return self._parse_additive()

    def _parse_additive(self) -> ArithmeticExpression:
        expression = self._parse_multiplicative()
        while operator_token := self._cursor.match(TokenKind.PLUS, TokenKind.MINUS):
            right = self._parse_multiplicative()
            expression = BinaryExpression(
                expression,
                _ARITHMETIC_OPERATORS[operator_token.kind],
                right,
                _combined_span(expression.span, right.span),
            )
        return expression

    def _parse_multiplicative(self) -> ArithmeticExpression:
        expression = self._parse_unary()
        while operator_token := self._cursor.match(TokenKind.STAR, TokenKind.SLASH):
            right = self._parse_unary()
            expression = BinaryExpression(
                expression,
                _ARITHMETIC_OPERATORS[operator_token.kind],
                right,
                _combined_span(expression.span, right.span),
            )
        return expression

    def _parse_unary(self) -> ArithmeticExpression:
        operator_token = self._cursor.match(TokenKind.PLUS, TokenKind.MINUS)
        if operator_token is None:
            return self._parse_primary()
        operand = self._parse_primary()
        operator = (
            UnaryOperator.PLUS
            if operator_token.kind is TokenKind.PLUS
            else UnaryOperator.MINUS
        )
        return UnaryExpression(
            operator,
            operand,
            SourceSpan(operator_token.span.start, operand.span.end),
        )

    def _parse_primary(self) -> ArithmeticExpression:
        token = self._cursor.current
        if token.kind is TokenKind.INTEGER:
            self._cursor.advance()
            return IntegerLiteral(int(token.lexeme), token.span)
        if token.kind is TokenKind.IDENTIFIER:
            self._cursor.advance()
            name = Identifier(token.lexeme, token.span)
            return IdentifierExpression(name, token.span)
        if token.kind is TokenKind.LEFT_PAREN:
            opening = self._cursor.advance()
            expression = self._parse_additive()
            closing = self._cursor.expect(TokenKind.RIGHT_PAREN, "')'")
            return _with_span(
                expression,
                SourceSpan(opening.span.start, closing.span.end),
            )
        raise ParseError(token, "an integer, identifier, unary sign, or '('")

    def _expect_eof(self) -> None:
        self._cursor.expect(TokenKind.EOF, "end of input")


def _combined_span(left: SourceSpan, right: SourceSpan) -> SourceSpan:
    return SourceSpan(left.start, right.end)


def _with_span(
    expression: ArithmeticExpression, span: SourceSpan
) -> ArithmeticExpression:
    return replace(expression, span=span)


def _decode_string(lexeme: str) -> str:
    return lexeme[1:-1].replace('""', '"')


def parse_expression(source: str) -> ParsedExpression:
    """Parse one standalone expression or comparison and require end of input."""

    return _ExpressionParser(tokenize(source)).parse()
