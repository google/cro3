# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dataclasses import dataclass
import math

from analyzer.backend.test_result import ImprovementDirection
import scipy


@dataclass(frozen=True, kw_only=True, order=True)
class MetricSample:
    """Represents an aggregation of a particular metric from a particular test
    run over a set of test runs."""

    test_name: str
    """The name of a test this metric is from, e.g. ui.OverviewPerf."""

    metric_path: str
    """Full metric path, e.g. ui.OverviewPerf.Memory.Total.TileMemory.summary"""

    units: str
    """Units of the metric value - e.g. 's' for seconds."""

    improvement_direction: ImprovementDirection
    """Whether this metric is better if it goes up or down."""

    value_map: dict[str, float]
    """Map from test run ID to value or average of list of values."""

    def mean(self) -> float:
        """Returns the mean of the values in this MetricSample."""
        s = 0.0
        for v in self.value_map.values():
            s += v
        return s / len(self.value_map)

    def description(self, print_vals: bool = False) -> str:
        """Returns a human readable description of this MetricSample.

        Args:
            print_vals: Whether to print the values in the description.

        Returns:
            A string describing the distribution of values.
        """
        vals = list(self.value_map.values())
        s = ""
        if print_vals:
            s = "  " + " ".join(f"{i:.3g}" for i in vals) + "\n"
        d = scipy.stats.describe(vals)
        s += f"  mean={d.mean:.2f} {self.units}, std={math.sqrt(d.variance):.2f}, "
        s += f"min={d.minmax[0]:.2f}, max={d.minmax[1]:.2f}"
        return s


SampleDict = dict[str, MetricSample]
"""Map from metric path to MetricSample"""
