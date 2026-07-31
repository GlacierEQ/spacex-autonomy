from __future__ import annotations

import json

import pytest

from spacex_autonomy.__main__ import main


def test_cli_emits_standard_json_without_nan(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--position", "10", "--velocity", "2", "--target-position", "100"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    assert payload["schema"] == "glaciereq.spacex-autonomy.simulation-snapshot.v1"
    assert payload["control"]["target_position_m"] == 100.0


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("--timestamp", "nan"),
        ("--position", "inf"),
        ("--velocity", "-inf"),
        ("--target-position", "nan"),
        ("--imu-confidence", "inf"),
    ],
)
def test_cli_rejects_non_finite_numbers(argument: str, value: str) -> None:
    with pytest.raises(SystemExit) as error:
        main([argument, value])
    assert error.value.code == 2
