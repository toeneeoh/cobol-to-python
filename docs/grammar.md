# COBOL v0.1 Grammar

This document defines the lexical and syntactic grammar accepted by version
0.1. The grammar is intentionally smaller and stricter than general COBOL.

## Source format

- Source is UTF-8 and free-format only.
- Fixed-column sequence areas, indicator columns, continuation rules, and
  identification areas are unsupported.
- Spaces, tabs, LF, and CRLF separate tokens.
- Newlines are otherwise insignificant, except that they terminate comments.
- A comment begins with `*>` and continues to the end of the physical line.
- Keywords and identifiers are case-insensitive.
- Periods are mandatory where shown in the grammar. In this subset, a period is
  only a terminator; it does not implicitly close scopes.

## Lexical rules

Keywords are matched case-insensitively. The reserved keywords are:

```text
COMPUTE DATA DISPLAY DIVISION ELSE END-IF IDENTIFICATION IF MOVE PIC
PROCEDURE PROGRAM-ID RUN SECTION STOP TO VALUE WORKING-STORAGE X
```

An identifier starts with an ASCII letter and may continue with ASCII letters,
digits, or hyphens. It may not end with a hyphen, contain consecutive hyphens,
or equal a reserved keyword. Identifier equality is case-insensitive.

```ebnf
identifier = letter, { letter | digit | identifier-hyphen } ;
letter = "A" | "B" | ... | "Z" | "a" | "b" | ... | "z" ;
digit = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;
identifier-hyphen = "-" ;
```

The prose restrictions on trailing and consecutive hyphens apply in addition
to the simplified production above.

Hyphens inside identifiers are scanned maximally, so `A-B` and `ITEM-1` are
identifiers. Binary subtraction must have whitespace on both sides, as in
`A - B`. Unary minus may directly precede its operand, as in `-7`, `-COUNT`, or
`-(A + B)`. A hyphen attached to the end of an identifier or a pair of
consecutive hyphens is a lexical error.

Integer literals contain one or more ASCII digits. A sign is an operator, not
part of an integer literal. A digit sequence immediately followed by a letter
or hyphen is a malformed lexical unit rather than two tokens. A
`positive-integer` has a value greater than zero.

String literals begin and end with a double quote and cannot span physical
lines. Two consecutive double quotes inside a string represent one literal
double quote. For example, `"He said ""hello"""` contains `He said "hello"`.

The punctuation and operator tokens are:

```text
. ( ) + - * / = <> < <= > >=
```

The lexer uses longest-match tokenization for `<>`, `<=`, and `>=`.

## EBNF

Quoted words are case-insensitive keywords. Braces mean zero or more,
brackets mean optional, and parentheses group grammar elements.

```ebnf
program =
    identification-division,
    program-id-paragraph,
    data-division,
    working-storage-section,
    procedure-division,
    { statement },
    stop-run,
    EOF ;

identification-division =
    "IDENTIFICATION", "DIVISION", "." ;

program-id-paragraph =
    "PROGRAM-ID", ".", identifier, "." ;

data-division =
    "DATA", "DIVISION", "." ;

working-storage-section =
    "WORKING-STORAGE", "SECTION", ".", { data-declaration } ;

data-declaration =
    "01", identifier, picture, [ value-clause ], "." ;

picture =
      "PIC", "X", "(", positive-integer, ")"
    | "PIC", "9", "(", positive-integer, ")" ;

value-clause =
    "VALUE", literal ;

procedure-division =
    "PROCEDURE", "DIVISION", "." ;

statement =
      display-statement
    | move-statement
    | compute-statement
    | if-statement ;

display-statement =
    "DISPLAY", expression, "." ;

move-statement =
    "MOVE", expression, "TO", identifier, "." ;

compute-statement =
    "COMPUTE", identifier, "=", arithmetic-expression, "." ;

if-statement =
    "IF", comparison,
    statement, { statement },
    [ "ELSE", statement, { statement } ],
    "END-IF", "." ;

stop-run =
    "STOP", "RUN", "." ;

comparison =
    expression, comparison-operator, expression ;

comparison-operator =
    "=" | "<>" | "<" | "<=" | ">" | ">=" ;

expression =
      arithmetic-expression
    | string-expression ;

string-expression =
      string-literal
    | string-identifier ;

arithmetic-expression =
    additive-expression ;

additive-expression =
    multiplicative-expression,
    { ("+" | "-"), multiplicative-expression } ;

multiplicative-expression =
    unary-expression,
    { ("*" | "/"), unary-expression } ;

unary-expression =
    [ "+" | "-" ], primary-expression ;

primary-expression =
      integer-literal
    | numeric-identifier
    | "(", arithmetic-expression, ")" ;

literal =
      integer-literal
    | string-literal ;
```

`numeric-identifier` and `string-identifier` are semantic classifications of
an `identifier`, based on its declaration. They are not distinct lexer token
kinds. Likewise, the parser may initially recognize `expression` without
knowing its category; semantic analysis must enforce the category rules in
[supported-cobol.md](supported-cobol.md).

Binary `*` and `/` bind more tightly than binary `+` and `-`. Unary `+` and `-`
bind more tightly than binary operators. Binary operators of equal precedence
associate from left to right. Parentheses override precedence.

## Structural constraints

The following constraints supplement the context-free grammar:

- The five program headers occur exactly once and in the order shown.
- The working-storage section may contain no declarations.
- Only level-01 data declarations are supported.
- A program ends with exactly one `STOP RUN.`.
- `STOP RUN.` is not a `statement`; it cannot occur early or inside an `IF`.
- An `IF` branch contains at least one statement. If `ELSE` is present, its
  branch also contains at least one statement.
- `END-IF` is mandatory, including for nested conditionals.
- `DISPLAY` accepts exactly one expression.
- `THEN` is not part of the grammar.
- A comparison has exactly two operands and one comparison operator.
