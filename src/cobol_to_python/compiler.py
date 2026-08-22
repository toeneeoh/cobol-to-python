"""End-to-end orchestration for the COBOL-to-Python pipeline."""

from cobol_to_python.generator import generate_python
from cobol_to_python.parser import parse_program
from cobol_to_python.semantic import analyze_program


def transpile(source: str) -> str:
    """Translate one documented COBOL v0.1 program into Python source.

    Lexing and parsing errors, semantic errors, and their source locations are
    preserved from their respective pipeline stages.
    """

    program = parse_program(source)
    analyzed = analyze_program(program)
    return generate_python(analyzed)
