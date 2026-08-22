# Supported COBOL in v0.1

Version 0.1 supports a deliberately small, free-format COBOL dialect. A
construct is supported only when this document and [grammar.md](grammar.md)
explicitly describe it. Compatibility with a general-purpose COBOL compiler
does not imply support here.

## Program structure

Every program contains these elements exactly once and in this order:

1. `IDENTIFICATION DIVISION.`
2. A `PROGRAM-ID.` paragraph containing one identifier.
3. `DATA DIVISION.`
4. `WORKING-STORAGE SECTION.`
5. `PROCEDURE DIVISION.`
6. Zero or more supported statements.
7. One final `STOP RUN.`

The working-storage section may be empty. `STOP RUN.` is allowed only as the
final top-level construct. See [grammar.md](grammar.md) for the complete lexical
and syntactic contract.

## Working-storage data

Only level-01 elementary items are supported:

```cobol
01 CUSTOMER-NAME PIC X(20).
01 STATUS-TEXT PIC X(8) VALUE "READY".
01 ITEM-COUNT PIC 9(3).
01 START-COUNT PIC 9(3) VALUE 12.
```

`PIC X(n)` declares a fixed-width string, where `n` is positive. Without a
`VALUE`, it begins as `n` spaces. A shorter string is right-padded with spaces
on initialization and assignment. A string longer than `n` is an error and is
never silently truncated.

`PIC 9(n)` declares an integer with at most `n` decimal digits, excluding an
optional runtime minus sign. Without a `VALUE`, it begins as zero. An initial
`VALUE` is an unsigned integer literal of no more than `n` digits. Arithmetic
may subsequently produce a negative value; the sign does not consume one of
the `n` digit positions.

The `VALUE` category must match the picture category. Declarations are unique
and references resolve case-insensitively. Every referenced data name must be
declared.

## Statements

The supported procedure statements are:

- `DISPLAY expression.` prints one string or integer followed by a newline.
- `MOVE expression TO identifier.` assigns a value after category and size
  validation.
- `COMPUTE identifier = arithmetic-expression.` evaluates integer arithmetic
  and assigns the result to a numeric target.
- `IF comparison ... [ELSE ...] END-IF.` selects a non-empty statement branch.
- `STOP RUN.` ends the program and must appear once, at the end.

Nested `IF` statements are supported. `END-IF` and the period following it are
mandatory. Periods terminate constructs but do not implicitly close scopes.

String expressions are limited to string literals and `PIC X` identifiers.
Numeric expressions support integer literals, `PIC 9` identifiers,
parentheses, unary `+` and `-`, and binary `+`, `-`, `*`, and `/`.

Comparisons support `=`, `<>`, `<`, `<=`, `>`, and `>=`. Both operands must
have the same category. Chained comparisons are unsupported.

Arithmetic uses integer values. Division truncates toward zero, so `7 / 2` is
`3` and `-7 / 2` is `-3`. Division by zero is a runtime error. A numeric result
with more digits than its target picture permits is a runtime size error.

There are no implicit conversions between strings and integers. A mismatched
assignment, comparison, `VALUE` clause, or arithmetic operand is a semantic
error.

## Python semantic mapping

Generated Python must preserve these mappings deterministically:

| COBOL | Python behavior |
| --- | --- |
| Program | A module with a `main()` function |
| `PIC X(n)` | A `str` subject to fixed-width assignment rules |
| `PIC 9(n)` | An `int` subject to digit-width assignment rules |
| Uninitialized `PIC X(n)` | `" " * n` |
| Uninitialized `PIC 9(n)` | `0` |
| `DISPLAY value` | `print(value)` |
| `MOVE source TO target` | Validated assignment |
| `COMPUTE target = expression` | Integer evaluation and validated assignment |
| `IF` / `ELSE` | Python `if` / `else` |
| `=` / `<>` | Python `==` / `!=` |
| `<` / `<=` / `>` / `>=` | Corresponding Python comparison |
| `STOP RUN` | Normal return from `main()` |

Generated data names use a `cobol_` prefix, lowercase letters, and underscores
in place of COBOL hyphens. For example, `CUSTOMER-NAME` maps to
`cobol_customer_name`. The prefix prevents collisions with Python keywords and
generator-owned names. Since source identifiers cannot contain underscores,
this mapping does not merge two valid source spellings.

## Complete accepted programs

### Minimal display

```cobol
IDENTIFICATION DIVISION.
PROGRAM-ID. HELLO.
DATA DIVISION.
WORKING-STORAGE SECTION.
PROCEDURE DIVISION.
DISPLAY "Hello, world!".
STOP RUN.
```

### Data and arithmetic

```cobol
IDENTIFICATION DIVISION.
PROGRAM-ID. TOTALS.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 FIRST-NUMBER PIC 9(3) VALUE 12.
01 SECOND-NUMBER PIC 9(3) VALUE 8.
01 TOTAL PIC 9(4).
PROCEDURE DIVISION.
COMPUTE TOTAL = FIRST-NUMBER + SECOND-NUMBER * 2.
DISPLAY TOTAL.
STOP RUN.
```

### Move and conditional

```cobol
IDENTIFICATION DIVISION.
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
STOP RUN.
```

### Nested conditionals and comments

```cobol
IDENTIFICATION DIVISION.
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
STOP RUN.
```

Each example follows the grammar exactly: all headers are present and ordered,
all declarations are level 01, every ordinary statement has its period, every
conditional has non-empty branches and `END-IF.`, and `STOP RUN.` occurs once
at the end.

## Rejected examples

The category names below define diagnostic classes conceptually; they do not
require implementation in the documentation milestone.

### Fixed-format source

```cobol
000100 IDENTIFICATION DIVISION.
000200 PROGRAM-ID. FIXED.
```

Expected category: `UnsupportedSourceFormatError`. Sequence-area source is not
part of the free-format dialect.

### Invalid identifier

```cobol
01 9COUNT PIC 9(2).
```

Expected category: `LexicalError`. An identifier cannot begin with a digit.

### Unterminated string

```cobol
DISPLAY "HELLO.
```

Expected category: `LexicalError`. A string must close on the same physical
line.

### Missing explicit scope terminator

```cobol
IF COUNT = 1
    DISPLAY "ONE".
STOP RUN.
```

Expected category: `SyntaxError`. Every `IF` requires `END-IF.`.

### Type mismatch

```cobol
MOVE "TEN" TO COUNT.
```

Expected category: `SemanticError` when `COUNT` is declared as `PIC 9`.

### Undeclared identifier

```cobol
DISPLAY MISSING-NAME.
```

Expected category: `SemanticError`. Every referenced data name must be
declared.

### Unsupported statement

```cobol
PERFORM CALCULATE-TOTAL.
```

Expected category: `UnsupportedFeatureError`. `PERFORM` and paragraphs are
outside version 0.1.

### Unsupported decimal picture

```cobol
01 PRICE PIC 9(3)V99.
```

Expected category: `UnsupportedFeatureError`. Decimal pictures are outside
version 0.1.

## Explicitly unsupported features

- Fixed-column COBOL, continuation lines, and compiler directives.
- Files and file-control clauses.
- Copybooks and `COPY`.
- Decimal, signed, edited, and other picture forms beyond `X(n)` and `9(n)`.
- `REDEFINES`.
- `OCCURS`, tables, and subscripting.
- Group items and levels other than `01`.
- `PERFORM`.
- Procedure paragraphs and sections.
- `GO TO`.
- `THEN` and `ELSE IF` as special forms.
- `ACCEPT`, `INITIALIZE`, `STRING`, and `UNSTRING`.
- Figurative constants such as `ZERO`, `SPACE`, and `HIGH-VALUE`.
- Boolean operators such as `AND`, `OR`, and `NOT`.
- Abbreviated or chained conditions.
- String concatenation.
- Multiple operands in one `DISPLAY`.
- `STOP RUN` inside a conditional or before the end of a program.
- Implicit period-based scope termination.
- Implicit conversion between string and numeric data.

## Resolved ambiguities and open decisions

Version 0.1 resolves potentially ambiguous behavior as follows:

- `/` is integer division truncated toward zero, not Python floor division.
- Negative runtime values are allowed in `PIC 9(n)`; the sign is excluded from
  `n`. Signed picture syntax remains unsupported.
- Unary signs are operators rather than part of integer literal tokens.
- Periods are mandatory terminators and never implicit scope terminators.
- `END-IF` is mandatory and `THEN` is unsupported.
- Identifiers cannot end in a hyphen or contain consecutive hyphens.
- Hyphens within identifiers are scanned maximally; binary subtraction has
  whitespace on both sides, while unary minus may touch its operand.
- A digit-leading name such as `9COUNT` is one malformed lexical unit.
- Embedded double quotes in strings use doubled quotes.
- Type mismatches and size overflow are errors, not implicit conversions or
  truncations.

There are no known unresolved language decisions within the version 0.1
contract. Behavior not explicitly defined by these two documents is
unsupported until it is documented, implemented, and tested.
