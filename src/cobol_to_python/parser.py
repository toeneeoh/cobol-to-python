"""Recursive-descent parsing for focused COBOL v0.1 grammar fragments."""

from dataclasses import replace
from typing import TypeAlias

from cobol_to_python.ast import (
    ArithmeticExpression,
    ArithmeticOperator,
    BinaryExpression,
    Comparison,
    ComparisonOperator,
    ComputeStatement,
    DataDeclaration,
    DataDivision,
    DisplayStatement,
    Expression,
    Identifier,
    IdentifierExpression,
    IfStatement,
    IntegerLiteral,
    Literal,
    MoveStatement,
    Pic9,
    Picture,
    PicX,
    ProcedureDivision,
    Statement,
    StopRun,
    StringLiteral,
    UnaryExpression,
    UnaryOperator,
)
from cobol_to_python.lexer import SourceSpan, Token, TokenKind, tokenize

ParsedExpression: TypeAlias = Expression | Comparison


class ParseError(ValueError):
    """An unexpected token encountered while parsing COBOL source."""

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

    def check(self, kind: TokenKind) -> bool:
        return self.current.kind is kind

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
    def __init__(self, cursor: _TokenCursor) -> None:
        self._cursor = cursor

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

    def parse_required_comparison(self) -> Comparison:
        left = self._parse_expression()
        operator_token = self._cursor.match(*_COMPARISON_KINDS)
        if operator_token is None:
            raise ParseError(self._cursor.current, "a comparison operator")
        right = self._parse_expression()
        if self._cursor.current.kind in _COMPARISON_OPERATORS:
            raise ParseError(
                self._cursor.current,
                "a statement; chained comparisons are unsupported",
            )
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


class _DataDivisionParser:
    def __init__(self, tokens: list[Token]) -> None:
        self._cursor = _TokenCursor(tokens)

    def parse(self) -> DataDivision:
        start = self._cursor.expect(TokenKind.DATA, "'DATA'")
        self._cursor.expect(TokenKind.DIVISION, "'DIVISION'")
        self._cursor.expect(TokenKind.PERIOD, "'.' after DATA DIVISION")
        self._cursor.expect(TokenKind.WORKING_STORAGE, "'WORKING-STORAGE'")
        self._cursor.expect(TokenKind.SECTION, "'SECTION'")
        section_period = self._cursor.expect(
            TokenKind.PERIOD, "'.' after WORKING-STORAGE SECTION"
        )

        declarations: list[DataDeclaration] = []
        while self._cursor.current.kind is TokenKind.INTEGER:
            declarations.append(self._parse_declaration())

        self._cursor.expect(TokenKind.EOF, "a level-01 declaration or end of input")
        end = declarations[-1].span.end if declarations else section_period.span.end
        return DataDivision(tuple(declarations), SourceSpan(start.span.start, end))

    def _parse_declaration(self) -> DataDeclaration:
        level = self._cursor.advance()
        if level.lexeme != "01":
            raise ParseError(level, "level number '01'")

        name_token = self._cursor.expect(TokenKind.IDENTIFIER, "a data name")
        name = Identifier(name_token.lexeme, name_token.span)
        picture = self._parse_picture()

        if self._cursor.check(TokenKind.PIC):
            raise ParseError(
                self._cursor.current,
                "a VALUE clause or declaration-ending '.'; duplicate PIC clause",
            )

        initial_value: Literal | None = None
        if self._cursor.match(TokenKind.VALUE) is not None:
            initial_value = self._parse_literal()
            if self._cursor.check(TokenKind.VALUE):
                raise ParseError(
                    self._cursor.current,
                    "declaration-ending '.'; duplicate VALUE clause",
                )
            if self._cursor.check(TokenKind.PIC):
                raise ParseError(
                    self._cursor.current,
                    "declaration-ending '.'; duplicate PIC clause",
                )

        period = self._cursor.expect(TokenKind.PERIOD, "declaration-ending '.'")
        return DataDeclaration(
            name,
            picture,
            initial_value,
            SourceSpan(level.span.start, period.span.end),
        )

    def _parse_picture(self) -> Picture:
        start = self._cursor.expect(TokenKind.PIC, "'PIC'")
        picture_token = self._cursor.current
        picture_type: type[PicX] | type[Pic9]
        if picture_token.kind is TokenKind.X:
            self._cursor.advance()
            picture_type = PicX
        elif picture_token.kind is TokenKind.INTEGER and picture_token.lexeme == "9":
            self._cursor.advance()
            picture_type = Pic9
        else:
            raise ParseError(picture_token, "picture type 'X' or '9'")

        self._cursor.expect(TokenKind.LEFT_PAREN, "'(' after picture type")
        length_token = self._cursor.expect(
            TokenKind.INTEGER, "a positive picture length"
        )
        length = int(length_token.lexeme)
        if length == 0:
            raise ParseError(
                length_token, "a positive picture length greater than zero"
            )
        closing = self._cursor.expect(TokenKind.RIGHT_PAREN, "')' after picture length")
        return picture_type(length, SourceSpan(start.span.start, closing.span.end))

    def _parse_literal(self) -> Literal:
        token = self._cursor.current
        if token.kind is TokenKind.INTEGER:
            self._cursor.advance()
            return IntegerLiteral(int(token.lexeme), token.span)
        if token.kind is TokenKind.STRING:
            self._cursor.advance()
            return StringLiteral(_decode_string(token.lexeme), token.span)
        raise ParseError(token, "an integer or string literal after VALUE")


_STATEMENT_STARTERS = (
    TokenKind.DISPLAY,
    TokenKind.MOVE,
    TokenKind.COMPUTE,
    TokenKind.IF,
)


class _ProcedureDivisionParser:
    def __init__(self, tokens: list[Token]) -> None:
        self._cursor = _TokenCursor(tokens)
        self._expressions = _ExpressionParser(self._cursor)

    def parse(self) -> ProcedureDivision:
        start = self._cursor.expect(TokenKind.PROCEDURE, "'PROCEDURE'")
        self._cursor.expect(TokenKind.DIVISION, "'DIVISION'")
        self._cursor.expect(TokenKind.PERIOD, "'.' after PROCEDURE DIVISION")

        statements: list[Statement] = []
        while not self._cursor.check(TokenKind.STOP):
            if self._cursor.check(TokenKind.EOF):
                raise ParseError(self._cursor.current, "final 'STOP RUN.'")
            statements.append(self._parse_statement())

        stop_run = self._parse_stop_run()
        self._cursor.expect(TokenKind.EOF, "end of input after STOP RUN.")
        return ProcedureDivision(
            tuple(statements),
            stop_run,
            SourceSpan(start.span.start, stop_run.span.end),
        )

    def _parse_statement(self) -> Statement:
        kind = self._cursor.current.kind
        if kind is TokenKind.DISPLAY:
            return self._parse_display()
        if kind is TokenKind.MOVE:
            return self._parse_move()
        if kind is TokenKind.COMPUTE:
            return self._parse_compute()
        if kind is TokenKind.IF:
            return self._parse_if()
        raise ParseError(
            self._cursor.current,
            "a DISPLAY, MOVE, COMPUTE, or IF statement",
        )

    def _parse_display(self) -> DisplayStatement:
        start = self._cursor.advance()
        value = self._expressions._parse_expression()
        period = self._cursor.expect(TokenKind.PERIOD, "'.' after DISPLAY operand")
        return DisplayStatement(value, SourceSpan(start.span.start, period.span.end))

    def _parse_move(self) -> MoveStatement:
        start = self._cursor.advance()
        value = self._expressions._parse_expression()
        self._cursor.expect(TokenKind.TO, "'TO' after MOVE source")
        target_token = self._cursor.expect(
            TokenKind.IDENTIFIER, "an identifier after TO"
        )
        target = Identifier(target_token.lexeme, target_token.span)
        period = self._cursor.expect(TokenKind.PERIOD, "'.' after MOVE target")
        return MoveStatement(
            value,
            target,
            SourceSpan(start.span.start, period.span.end),
        )

    def _parse_compute(self) -> ComputeStatement:
        start = self._cursor.advance()
        target_token = self._cursor.expect(
            TokenKind.IDENTIFIER, "an identifier after COMPUTE"
        )
        target = Identifier(target_token.lexeme, target_token.span)
        self._cursor.expect(TokenKind.EQUAL, "'=' after COMPUTE target")
        expression = self._expressions._parse_additive()
        period = self._cursor.expect(TokenKind.PERIOD, "'.' after COMPUTE expression")
        return ComputeStatement(
            target,
            expression,
            SourceSpan(start.span.start, period.span.end),
        )

    def _parse_if(self) -> IfStatement:
        start = self._cursor.advance()
        condition = self._expressions.parse_required_comparison()
        then_body, then_span = self._parse_branch(TokenKind.ELSE, TokenKind.END_IF)

        else_body: tuple[Statement, ...] | None = None
        else_span: SourceSpan | None = None
        if self._cursor.match(TokenKind.ELSE) is not None:
            else_body, else_span = self._parse_branch(TokenKind.END_IF)

        self._cursor.expect(TokenKind.END_IF, "'END-IF'")
        period = self._cursor.expect(TokenKind.PERIOD, "'.' after END-IF")
        return IfStatement(
            condition,
            then_body,
            then_span,
            else_body,
            else_span,
            SourceSpan(start.span.start, period.span.end),
        )

    def _parse_branch(
        self, *terminators: TokenKind
    ) -> tuple[tuple[Statement, ...], SourceSpan]:
        if self._cursor.current.kind in terminators:
            raise ParseError(self._cursor.current, "a statement in the IF branch")

        statements: list[Statement] = []
        while self._cursor.current.kind not in terminators:
            if self._cursor.check(TokenKind.EOF):
                raise ParseError(self._cursor.current, "'ELSE' or 'END-IF'")
            statements.append(self._parse_statement())

        return (
            tuple(statements),
            SourceSpan(statements[0].span.start, statements[-1].span.end),
        )

    def _parse_stop_run(self) -> StopRun:
        start = self._cursor.expect(TokenKind.STOP, "'STOP'")
        self._cursor.expect(TokenKind.RUN, "'RUN' after STOP")
        period = self._cursor.expect(TokenKind.PERIOD, "'.' after STOP RUN")
        return StopRun(SourceSpan(start.span.start, period.span.end))


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

    return _ExpressionParser(_TokenCursor(tokenize(source))).parse()


def parse_data_division(source: str) -> DataDivision:
    """Parse one complete data division and require end of input."""

    return _DataDivisionParser(tokenize(source)).parse()


def parse_procedure_division(source: str) -> ProcedureDivision:
    """Parse one complete procedure division and require end of input."""

    return _ProcedureDivisionParser(tokenize(source)).parse()
