from collections.abc import Callable

import pytest

from cobol_to_python import analyze_program, generate_python, parse_program


def generate(data: str = "", procedure: str = "") -> str:
    source = f"""IDENTIFICATION DIVISION.
PROGRAM-ID. GENERATED.
DATA DIVISION.
WORKING-STORAGE SECTION.
{data}PROCEDURE DIVISION.
{procedure}STOP RUN."""
    return generate_python(analyze_program(parse_program(source)))


def execute(generated: str) -> Callable[[], None]:
    namespace: dict[str, object] = {"__name__": "generated_test"}
    exec(compile(generated, "<generated>", "exec"), namespace)
    main = namespace["main"]
    assert callable(main)
    return main


def test_generation_is_deterministic_and_consistently_terminated() -> None:
    first = generate(procedure='DISPLAY "Hello".\n')
    second = generate(procedure='DISPLAY "Hello".\n')

    assert first == second
    assert first.endswith("\n")
    compile(first, "<generated>", "exec")


def test_generates_canonical_collision_safe_names_and_initial_values() -> None:
    generated = generate(
        '01 Customer-Name PIC X(5) VALUE "Ada".\n'
        "01 ITEM-COUNT PIC 9(3) VALUE 12.\n"
        "01 EMPTY-TEXT PIC X(2).\n"
    )

    assert 'cobol_customer_name = _cobol_assign_x("Ada", 5)' in generated
    assert "cobol_item_count = _cobol_assign_9(12, 3)" in generated
    assert "cobol_empty_text = _cobol_assign_x('', 2)" in generated


def test_generated_display_and_string_padding(
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated = generate(
        '01 NAME PIC X(5) VALUE "Ada".\n',
        "DISPLAY NAME.\n",
    )

    execute(generated)()
    assert capsys.readouterr().out == "Ada  \n"


def test_generated_move_compute_and_arithmetic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated = generate(
        "01 COUNT PIC 9(3) VALUE 2.\n",
        "MOVE 5 TO COUNT.\nCOMPUTE COUNT = COUNT + 2 * 3.\nDISPLAY COUNT.\n",
    )

    execute(generated)()
    assert capsys.readouterr().out == "11\n"


def test_generated_nested_conditionals(capsys: pytest.CaptureFixture[str]) -> None:
    generated = generate(
        "01 COUNT PIC 9(2) VALUE 1.\n",
        """IF COUNT >= 1
    IF COUNT = 1
        DISPLAY "ONE".
    ELSE
        DISPLAY "OTHER".
    END-IF.
ELSE
    DISPLAY "ZERO".
END-IF.
""",
    )

    execute(generated)()
    assert capsys.readouterr().out == "ONE\n"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("7 / 2", "3\n"),
        ("(0 - 7) / 2", "-3\n"),
        ("7 / (0 - 2)", "-3\n"),
    ],
)
def test_generated_division_truncates_toward_zero(
    expression: str,
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated = generate(
        "01 RESULT PIC 9(2).\n",
        f"COMPUTE RESULT = {expression}.\nDISPLAY RESULT.\n",
    )

    execute(generated)()
    assert capsys.readouterr().out == expected


def test_generated_division_by_zero_is_runtime_error() -> None:
    generated = generate(
        "01 RESULT PIC 9(2).\n",
        "COMPUTE RESULT = 1 / 0.\n",
    )

    with pytest.raises(ZeroDivisionError, match="COBOL division by zero"):
        execute(generated)()


@pytest.mark.parametrize(
    ("data", "procedure", "message"),
    [
        (
            "01 TEXT PIC X(2).\n",
            'MOVE "ABC" TO TEXT.\n',
            "PIC X assignment exceeds picture width",
        ),
        (
            "01 COUNT PIC 9(2).\n",
            "COMPUTE COUNT = 99 + 1.\n",
            "PIC 9 assignment exceeds picture width",
        ),
    ],
)
def test_generated_assignments_check_runtime_width(
    data: str,
    procedure: str,
    message: str,
) -> None:
    generated = generate(data, procedure)

    with pytest.raises(ValueError, match=message):
        execute(generated)()


def test_generated_module_runs_main_when_executed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    generated = generate(procedure='DISPLAY "RUN".\n')
    namespace: dict[str, object] = {"__name__": "__main__"}

    exec(compile(generated, "<generated>", "exec"), namespace)
    assert capsys.readouterr().out == "RUN\n"
