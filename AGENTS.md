# project guidance

## objective

build a cobol-to-python transpiler for a clearly documented subset of cobol.

## architecture

the translation pipeline is:

1. source text
2. lexer
3. token stream
4. parser
5. typed ast
6. python generator

keep these stages separate. do not translate directly from source text to python.

## engineering rules

- use python type hints throughout production code.
- represent ast nodes with dataclasses.
- preserve source locations on tokens and syntax errors.
- add or update tests with every behavior change.
- prefer explicit readable code over metaprogramming.
- do not add dependencies without explaining why.
- do not silently expand the supported cobol subset.
- generated python must be deterministic and formatted consistently.
- every supported construct must be documented in docs/supported-cobol.md.

## validation

before declaring work complete, run:

- pytest
- ruff check .
- ruff format --check .
- mypy src

report any checks that could not be run.

## workflow

- inspect existing code before editing.
- make focused changes limited to the requested milestone.
- do not perform unrelated refactors.
- summarize changed files and validation results.