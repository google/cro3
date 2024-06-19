# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
from pathlib import Path

from analyzer.backend.test_result import ImprovementDirection
from analyzer.backend.test_result import TestResult
from analyzer.backend.test_result import TestResultKey
import click


def _load_results_from_results_chart_json(
    path: Path, json_str: str
) -> dict[TestResultKey, TestResult]:
    results_dict: dict[TestResultKey, TestResult] = {}
    # Tast results dir format is: <test run id>/tests/<test name>/
    test_run_id = path.parts[-4]
    test_name = path.parts[-2]
    for metric_name, results in json.loads(json_str).items():
        for variant, result in results.items():
            key = TestResultKey(
                run_id=test_run_id,
                test_name=test_name,
                metric_name=metric_name,
                variant=variant,
            )
            assert key not in results_dict, f"duplicate key: {key}"

            kind = result["type"]
            value: int | float | list[float]
            if kind == "scalar":
                assert isinstance(
                    result["value"], float | int
                ), f"expected int/float, got {result['value']}"
                value = result["value"]
            elif kind == "list_of_scalar_values":
                assert isinstance(
                    result["values"], list
                ), f"expected list, got {result['values']}"
                value = result["values"]
            else:
                assert False, f"unknown type: {kind}"

            results_dict[key] = TestResult(
                units=result["units"],
                improvement_direction=ImprovementDirection(
                    result["improvement_direction"]
                ),
                value=value,
            )
    return results_dict


def _load_results_from_tast_dir(path: Path) -> dict[TestResultKey, TestResult]:
    """Extracts values from results-chart.json and returns them as a dictionary."""

    paths = path.glob("*/tests/*/results-chart.json")
    all_results: dict[TestResultKey, TestResult] = {}
    for path in paths:
        results_dict = _load_results_from_results_chart_json(
            path, path.read_text()
        )
        for key in results_dict:
            assert key not in all_results, f"duplicate key: {key}"
        all_results.update(results_dict)

    return all_results


@click.command()
@click.option(
    "--output_path",
    type=click.Path(
        exists=False, dir_okay=False, resolve_path=True, path_type=Path
    ),
    default=Path("data.json"),
    help="path to output summary JSON file",
)
@click.argument(
    "input_path",
    type=click.Path(
        exists=True, file_okay=False, resolve_path=True, path_type=Path
    ),
)
def ingest_tast_results_directory(input_path: Path, output_path: Path) -> None:
    """Ingest the Tast results directory, like: /tmp/tast/results/.

    This will output a JSON file containing all the performance test results
    to `output_path'.

    Args:
        input_path: Path to the Tast results directory.
        output_path: Path to the output JSON file to create.
    """
    results = _load_results_from_tast_dir(input_path)
    json_results = {k.to_json(): v.to_json() for k, v in results.items()}
    output_path.write_text(json.dumps(json_results, indent=2))
