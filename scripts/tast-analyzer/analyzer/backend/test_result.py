# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import dataclasses
from enum import StrEnum
import json


class ImprovementDirection(StrEnum):
    UP = "up"
    DOWN = "down"

    def is_up_better(self) -> bool:
        return self == "up"


@dataclasses.dataclass(frozen=True, kw_only=True, order=True)
class TestResultKey:
    run_id: str
    """Unique run ID for this test run."""

    test_name: str
    """Test name from Tast - e.g. ui.OverviewPerf."""

    metric_name: str
    """Metric name from Tast - e.g. Memory.Total.TileMemory."""

    variant: str
    """Variant name from Tast - usually 'summary'."""

    def metric_path(self) -> str:
        """Returns a unique identifier for the metric in the context of a set
        of test runs."""
        return self.test_name + "." + self.metric_name + "." + self.variant

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "TestResultKey":
        return TestResultKey(**json.loads(s))


@dataclasses.dataclass(frozen=True, kw_only=True, order=True)
class TestResult:
    units: str
    """Units of the metric value - e.g. 's' for seconds."""

    improvement_direction: ImprovementDirection
    """Whether this value is better if it goes up or down."""

    value: int | float | list[float]
    """The value of the test result."""

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "TestResult":
        variables = json.loads(s)
        variables["improvement_direction"] = ImprovementDirection(
            variables["improvement_direction"]
        )
        return TestResult(**variables)


def load_test_result_dict_from_json(
    json_str: str,
) -> dict[TestResultKey, TestResult]:
    """Loads a previously ingested JSON performance results file.

    Args:
        json_str: String containing the json.

    Returns:
        A dictionary of test results.
    """
    return {
        TestResultKey.from_json(k): TestResult.from_json(v)
        for k, v in json.loads(json_str).items()
    }
