# Supported COBOL in v0.2

Version 0.2 is a strict free-format teaching subset. All v0.1 programs remain
valid. The exact syntax is in [grammar.md](grammar.md).

## Program, data, and statements

Programs require identification, program-id, data, working-storage, and
procedure headers in order, then one final `STOP RUN.`. Only level-01 `PIC X(n)`
and `PIC 9(n)` items exist. X values are padded to width; numeric values are
integers with at most `n` digits excluding a minus sign. Overflow is an error.
Names resolve case-insensitively, declarations are unique, and conversions are
never implicit.

`ZERO`/`ZEROS` mean numeric zero. `SPACE`/`SPACES` fill an entire alphanumeric
target in a VALUE or MOVE context; they are not one-character strings.

- `DISPLAY A B "text".` prints operands without separators, then a newline.
- `MOVE expression TO target.` and `COMPUTE target = arithmetic-expression.`
  perform checked assignments.
- `ACCEPT target.` reads a line. PIC X input is padded and checked. PIC 9 input
  permits ASCII digits with an optional leading minus and is width checked.
- `ADD expression TO target.` and `SUBTRACT expression FROM target.` update a
  numeric target with checked arithmetic.
- `IF condition ... [ELSE ...] END-IF.` has explicit nestable scope.
- `PERFORM expression TIMES ... END-PERFORM.` repeats a non-empty inline body.
  The count is evaluated once; zero skips it and negative is a runtime error.

Integer division truncates toward zero. Conditions compare matching categories
with `= <> < <= > >=`; comparison chains are rejected. Precedence is comparison
before `NOT`, before `AND`, before `OR`.

## Python semantic mapping

| COBOL | Python behavior |
| --- | --- |
| Program | Module with `main()` |
| PIC X / PIC 9 | Checked `str` / checked `int` |
| DISPLAY operands | `print` with no inter-operand separator |
| ACCEPT | `input()` plus target validation |
| MOVE / COMPUTE | Checked assignment |
| ADD / SUBTRACT | Checked read-modify-write |
| PERFORM TIMES | `range` loop; count evaluated once |
| IF / NOT / AND / OR | Python conditional and boolean operators |
| ZERO / SPACES | `0` / target-width spaces |
| STOP RUN | Normal return from `main()` |

Generated names use a `cobol_` prefix, lowercase, and underscores for hyphens.

## Complete accepted programs

### Interactive greeting

```cobol
IDENTIFICATION DIVISION.
PROGRAM-ID. GREETER.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 USER-NAME PIC X(20).
PROCEDURE DIVISION.
DISPLAY "What is your name? ".
ACCEPT USER-NAME.
DISPLAY "Hello, " USER-NAME.
STOP RUN.
```

### Invoice total

```cobol
IDENTIFICATION DIVISION.
PROGRAM-ID. INVOICE.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 QUANTITY PIC 9(3) VALUE 4.
01 UNIT-PRICE PIC 9(3) VALUE 25.
01 TOTAL PIC 9(5) VALUE ZERO.
PROCEDURE DIVISION.
COMPUTE TOTAL = QUANTITY * UNIT-PRICE.
ADD 10 TO TOTAL.
DISPLAY "Total: " TOTAL.
STOP RUN.
```

### Countdown

```cobol
IDENTIFICATION DIVISION.
PROGRAM-ID. COUNTDOWN.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 COUNT-VALUE PIC 9(2) VALUE 3.
PROCEDURE DIVISION.
PERFORM 3 TIMES
    DISPLAY COUNT-VALUE.
    SUBTRACT 1 FROM COUNT-VALUE.
END-PERFORM.
DISPLAY "Go!".
STOP RUN.
```

### Compound eligibility and reset

```cobol
IDENTIFICATION DIVISION.
PROGRAM-ID. ELIGIBLE.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 AGE PIC 9(3) VALUE 21.
01 BLOCKED PIC 9(1) VALUE ZERO.
01 MESSAGE PIC X(12) VALUE SPACES.
PROCEDURE DIVISION.
IF AGE >= 18 AND NOT BLOCKED = 1
    MOVE "Eligible" TO MESSAGE.
ELSE
    MOVE "Not eligible" TO MESSAGE.
END-IF.
DISPLAY MESSAGE.
STOP RUN.
```

## Rejected examples

- `000100 IDENTIFICATION DIVISION.` — `UnsupportedSourceFormatError`.
- `01 9COUNT PIC 9(2).` — `LexicalError`.
- `DISPLAY "unfinished.` — `LexicalError`.
- `IF A = 1 DISPLAY A.` — `SyntaxError` (missing END-IF).
- `PERFORM WORK.` or `PERFORM 2 TIMES END-PERFORM.` — `SyntaxError`.
- `IF (A = 1 OR B = 2) ...` — `SyntaxError`.
- `ACCEPT NAME FROM CONSOLE.` — `SyntaxError`.
- `MOVE SPACES TO COUNT.` or `ADD 1 TO NAME.` — `SemanticError`.
- `DISPLAY SPACES.` — `SemanticError`; SPACES needs a target width.
- `DISPLAY MISSING-NAME.` — `SemanticError`.

## Explicitly unsupported

Fixed-column input; files; copybooks; decimals and edited/signed pictures;
REDEFINES; OCCURS; groups and levels other than 01; paragraphs and sections;
paragraph PERFORM, UNTIL, and VARYING; GO TO; MULTIPLY/DIVIDE statements;
GIVING, ROUNDED, and SIZE ERROR; EVALUATE; INITIALIZE; STRING/UNSTRING; THEN;
special ELSE IF; parenthesized compound or abbreviated conditions; advanced
ACCEPT; DISPLAY separators and NO ADVANCING; implicit scope/conversions; and
browser execution of generated code.

## Deliberate boundaries

Subtraction spacing disambiguates identifier hyphens. `NOT A = B` means
`NOT (A = B)`. Condition parentheses are deferred to avoid ambiguity with
arithmetic parentheses. SPACES is target-dependent. PERFORM counts are integer
expressions evaluated once. No other v0.2 language decision is unresolved.
