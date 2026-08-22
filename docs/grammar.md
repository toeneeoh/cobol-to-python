# COBOL v0.2 Grammar

This is the complete lexical and syntactic contract for version 0.2. Anything
not described here is unsupported.

## Source and lexical rules

Source is UTF-8, free-format COBOL. Fixed columns and continuation rules are
unsupported. Spaces, tabs, LF, and CRLF separate tokens; newlines otherwise
have no significance. `*>` starts a comment through the physical line end.

Keywords and identifiers are case-insensitive, while original spelling is
preserved. Reserved keywords are:

```text
ACCEPT ADD AND COMPUTE DATA DISPLAY DIVISION ELSE END-IF END-PERFORM FROM
IDENTIFICATION IF MOVE NOT OR PERFORM PIC PROCEDURE PROGRAM-ID RUN SECTION
SPACE SPACES STOP SUBTRACT TIMES TO VALUE WORKING-STORAGE X ZERO ZEROS
```

An identifier starts with an ASCII letter and continues with ASCII letters,
digits, or hyphens. It cannot end in a hyphen, contain consecutive hyphens, or
equal a keyword. Hyphens are scanned maximally: `A-B` is an identifier. Binary
subtraction requires whitespace on both sides (`A - B`); unary minus may touch
its operand. A digit-leading word is a lexical error.

Integers contain ASCII digits; signs are operators. Double-quoted strings
cannot cross a line and escape a quote by doubling it. Operators and
punctuation are `. ( ) + - * / = <> < <= > >=`, using longest match.

## EBNF

Quoted words are case-insensitive keywords. Braces mean repetition and brackets
mean optionality.

```ebnf
program = identification-division, program-id-paragraph, data-division,
          working-storage-section, procedure-division,
          { statement }, stop-run, EOF ;
identification-division = "IDENTIFICATION", "DIVISION", "." ;
program-id-paragraph = "PROGRAM-ID", ".", identifier, "." ;
data-division = "DATA", "DIVISION", "." ;
working-storage-section = "WORKING-STORAGE", "SECTION", ".",
                          { data-declaration } ;
data-declaration = "01", identifier, picture, [ value-clause ], "." ;
picture = "PIC", ( "X" | "9" ), "(", positive-integer, ")" ;
value-clause = "VALUE", literal ;

procedure-division = "PROCEDURE", "DIVISION", "." ;
statement = display | move | compute | accept | add | subtract | if | perform ;
display = "DISPLAY", expression, { expression }, "." ;
move = "MOVE", expression, "TO", identifier, "." ;
compute = "COMPUTE", identifier, "=", arithmetic-expression, "." ;
accept = "ACCEPT", identifier, "." ;
add = "ADD", arithmetic-expression, "TO", identifier, "." ;
subtract = "SUBTRACT", arithmetic-expression, "FROM", identifier, "." ;
if = "IF", condition, statement, { statement },
     [ "ELSE", statement, { statement } ], "END-IF", "." ;
perform = "PERFORM", arithmetic-expression, "TIMES",
          statement, { statement }, "END-PERFORM", "." ;
stop-run = "STOP", "RUN", "." ;

condition = or-condition ;
or-condition = and-condition, { "OR", and-condition } ;
and-condition = not-condition, { "AND", not-condition } ;
not-condition = [ "NOT" ], comparison ;
comparison = expression, ( "=" | "<>" | "<" | "<=" | ">" | ">=" ),
             expression ;

expression = arithmetic-expression | string-expression | spaces-literal ;
string-expression = string-literal | string-identifier ;
arithmetic-expression = additive-expression ;
additive-expression = multiplicative-expression,
                      { ( "+" | "-" ), multiplicative-expression } ;
multiplicative-expression = unary-expression,
                            { ( "*" | "/" ), unary-expression } ;
unary-expression = [ "+" | "-" ], primary-expression ;
primary-expression = integer-literal | zero-literal | numeric-identifier
                   | "(", arithmetic-expression, ")" ;
literal = integer-literal | string-literal | zero-literal | spaces-literal ;
zero-literal = "ZERO" | "ZEROS" ;
spaces-literal = "SPACE" | "SPACES" ;
```

Identifier categories are semantic. Operators at each level associate left.
Precedence is unary arithmetic, multiplication/division, addition/subtraction,
comparison, `NOT`, `AND`, then `OR`. Comparisons cannot chain. Parentheses group
arithmetic only; parenthesized compound conditions are unsupported.

## Structural and contextual constraints

- All divisions are required exactly once in the displayed order.
- Working-storage may be empty; only level 01 and positive lengths work.
- Each statement and explicit scope terminator has its shown period.
- IF branches and inline PERFORM bodies are non-empty and explicitly terminated.
- `STOP RUN.` occurs exactly once, last, and is not an ordinary statement.
- DISPLAY has one or more adjacent operands and inserts no separator.
- SPACE/SPACES is valid only for alphanumeric VALUE and MOVE contexts.
- ZERO/ZEROS is numeric zero.
- ACCEPT has only a target; advanced input clauses are absent.
- Inline PERFORM supports only TIMES and evaluates its count once.
