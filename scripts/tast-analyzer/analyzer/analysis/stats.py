# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import dataclasses

from analyzer.analysis import metric_sample
from scipy import stats


@dataclasses.dataclass(kw_only=True, order=True)
class MannWhitneyUResult:
    u: float
    """The U-statistic value."""

    p: float
    """The p-value."""

    def summary(self) -> str:
        """Returns a human readable summary of this result."""
        return f"U={self.u}, p={self.p:.6f}"


def mannwhitneyu(
    s1: metric_sample.MetricSample, s2: metric_sample.MetricSample
) -> MannWhitneyUResult:
    """Computes the Mann-Whitney U-statistic between two metric samples.

    Args:
        s1: The first metric sample.
        s2: The second metric sample.

    Returns:
        A MannWhitneyUResult with the U-statistic and p-value.
    """
    x = list(s1.value_map.values())
    y = list(s2.value_map.values())
    u, p = stats.mannwhitneyu(x, y, alternative="two-sided")
    return MannWhitneyUResult(u=u, p=p)


def signed_change(before: float, after: float) -> float:
    """Returns the signed change proportion between two values.

    Args:
        before: The value before the change.
        after: The value after the change.

    Returns:
        The signed change as a proportion.
    """
    return (after - before) / before
