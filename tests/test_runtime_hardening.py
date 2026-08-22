import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from cobol_to_python import transpile


def program(data: str = "", procedure: str = "") -> str:
    return f"""IDENTIFICATION DIVISION.
PROGRAM-ID. HARDENING.
DATA DIVISION.
WORKING-STORAGE SECTION.
{data}PROCEDURE DIVISION.
{procedure}STOP RUN."""


def load_main(generated: str) -> Callable[[], None]:
    namespace: dict[str, object] = {"__name__": "runtime_test"}
    exec(compile(generated, "<generated>", "exec"), namespace)
    main = namespace["main"]
    assert callable(main)
    return main


def test_repeated_execution_starts_with_fresh_working_storage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated = transpile(
        program(
            "01 COUNT PIC 9(2) VALUE 1.\n",
            "COMPUTE COUNT = COUNT + 1.\nDISPLAY COUNT.\n",
        )
    )
    main = load_main(generated)

    main()
    main()

    assert capsys.readouterr().out == "2\n2\n"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("0 - 99", "-99\n"),
        ("99", "99\n"),
    ],
)
def test_numeric_width_excludes_runtime_minus_sign_at_boundary(
    expression: str,
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated = transpile(
        program(
            "01 RESULT PIC 9(2).\n",
            f"COMPUTE RESULT = {expression}.\nDISPLAY RESULT.\n",
        )
    )

    load_main(generated)()
    assert capsys.readouterr().out == expected


def test_negative_numeric_overflow_uses_digit_width_only() -> None:
    generated = transpile(
        program(
            "01 RESULT PIC 9(2).\n",
            "COMPUTE RESULT = 0 - 100.\n",
        )
    )

    with pytest.raises(ValueError, match="PIC 9 assignment exceeds picture width"):
        load_main(generated)()


def test_division_uses_exact_integer_arithmetic_for_huge_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    numerator = 10**80 + 1
    expected = numerator // 3
    generated = transpile(
        program(
            "01 RESULT PIC 9(80).\n",
            f"COMPUTE RESULT = {numerator} / 3.\nDISPLAY RESULT.\n",
        )
    )

    load_main(generated)()
    assert capsys.readouterr().out == f"{expected}\n"


def test_strings_are_escaped_and_padded_deterministically(
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated = transpile(
        program(
            '01 MESSAGE PIC X(16) VALUE "He said ""hello""".\n',
            "DISPLAY MESSAGE.\n",
        )
    )

    assert '"He said \\"hello\\""' in generated
    load_main(generated)()
    assert capsys.readouterr().out == 'He said "hello" \n'


def test_empty_program_has_valid_repeatable_main() -> None:
    generated = transpile(program())
    main = load_main(generated)

    assert main() is None
    assert main() is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            """IDENTIFICATION DIVISION.
PROGRAM-ID. HELLO.
DATA DIVISION.
WORKING-STORAGE SECTION.
PROCEDURE DIVISION.
DISPLAY "Hello, world!".
STOP RUN.""",
            "Hello, world!\n",
        ),
        (
            """IDENTIFICATION DIVISION.
PROGRAM-ID. TOTALS.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 FIRST-NUMBER PIC 9(3) VALUE 12.
01 SECOND-NUMBER PIC 9(3) VALUE 8.
01 TOTAL PIC 9(4).
PROCEDURE DIVISION.
COMPUTE TOTAL = FIRST-NUMBER + SECOND-NUMBER * 2.
DISPLAY TOTAL.
STOP RUN.""",
            "28\n",
        ),
        (
            """IDENTIFICATION DIVISION.
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
STOP RUN.""",
            "Ada       \nGrace     \n",
        ),
        (
            """IDENTIFICATION DIVISION.
PROGRAM-ID. CLASSIFY.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 VALUE-A PIC 9(2) VALUE 5.
01 VALUE-B PIC 9(2) VALUE 8.
PROCEDURE DIVISION.
IF VALUE-A < VALUE-B
    IF VALUE-A = 5
        DISPLAY "MATCH".
    ELSE
        DISPLAY "LOWER".
    END-IF.
ELSE
    DISPLAY "NOT-LOWER".
END-IF.
STOP RUN.""",
            "MATCH\n",
        ),
    ],
)
def test_every_documented_program_has_expected_runtime_output(
    source: str,
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    load_main(transpile(source))()
    assert capsys.readouterr().out == expected


def test_representative_generated_python_passes_ruff(tmp_path: Path) -> None:
    generated = transpile(
        program(
            '01 TEXT PIC X(5) VALUE "A".\n01 COUNT PIC 9(2) VALUE 1.\n',
            "DISPLAY TEXT.\nCOMPUTE COUNT = COUNT + 1.\nDISPLAY COUNT.\n",
        )
    )
    generated_path = tmp_path / "generated.py"
    generated_path.write_text(generated, encoding="utf-8")
    ruff = Path(sys.executable).with_name(
        "ruff.exe" if sys.platform == "win32" else "ruff"
    )

    lint = subprocess.run(
        [str(ruff), "check", "--isolated", str(generated_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    formatting = subprocess.run(
        [str(ruff), "format", "--check", "--isolated", str(generated_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert formatting.returncode == 0, formatting.stdout + formatting.stderr
