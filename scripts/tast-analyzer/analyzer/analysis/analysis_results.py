# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import dataclasses
import logging

from analyzer.analysis import analysis_cfg
from analyzer.analysis import metric_sample
from analyzer.analysis import stats
from analyzer.analysis.metric_sample import MetricSample


@dataclasses.dataclass(frozen=True, kw_only=True, order=True)
class AnalysisResult:
    before_sample: MetricSample
    """The sample corresponding to the control group."""

    after_sample: MetricSample
    """The sample corresponding to the experiment group."""

    mwu_result: stats.MannWhitneyUResult
    """The result of the analysis using the MannWhitneyU test."""

    def __post__init__(self) -> None:
        assert self.before_sample.test_name == self.after_sample.test_name
        assert self.before_sample.metric_path == self.after_sample.metric_path
        assert self.before_sample.units == self.after_sample.units
        assert (
            self.before_sample.improvement_direction
            == self.after_sample.improvement_direction
        )

    def test_name(self) -> str:
        """Returns the test name."""
        return self.before_sample.test_name

    def metric_path(self) -> str:
        """Returns the full metric path."""
        return self.before_sample.metric_path

    def is_up_better(self) -> bool:
        """Returns if going up is better for this metric."""
        return self.before_sample.improvement_direction.is_up_better()

    def summary(self) -> str:
        """Returns a human readable summary of this result."""
        s = f"{self.before_sample.metric_path}:\n"

        signed_change = stats.signed_change(
            self.before_sample.mean(), self.after_sample.mean()
        )
        s += (
            f"  {self.mwu_result.summary()}, "
            f"dir={self.before_sample.improvement_direction}, "
            f"n=({len(self.before_sample.value_map)}, "
            f"{len(self.after_sample.value_map)}), "
            f"%change={100.0*signed_change:.2f}\n"
        )
        s += self.before_sample.description() + "\n"
        s += self.after_sample.description()
        return s


def compute_metric_paths_for_comparison(
    s1: metric_sample.SampleDict,
    s2: metric_sample.SampleDict,
    cfg: analysis_cfg.AnalysisCfg,
) -> list[str]:
    """Computes a set of metric paths to compare between s1 and s2.

    Args:
        s1: The first sample.
        s2: The second sample.
        cfg: The analysis configuration.

    Returns:
        A sorted list of metric paths to compare.
    """
    paths1 = set(s1.keys())
    paths2 = set(s2.keys())
    paths = set()

    for k in paths1.intersection(paths2):
        values1 = s1[k].value_map.values()
        values2 = s2[k].value_map.values()
        # Skip any things with just zeros - seems to happen for broken tests.
        if cfg.skip_all_zero_samples and (
            all(i == 0.0 for i in values1) or all(i == 0.0 for i in values2)
        ):
            continue
        if (
            len(values1) < cfg.minimum_sample_size
            or len(values2) < cfg.minimum_sample_size
        ):
            continue
        paths.add(k)

    ignored_count = len(paths1.union(paths2)) - len(paths)
    logging.info(
        f"Ignoring {ignored_count} metrics, looking at {len(paths)} metrics"
    )
    return sorted(paths)


def generate_analysis_results(
    *,
    before_samples: metric_sample.SampleDict,
    after_samples: metric_sample.SampleDict,
    metric_paths: list[str],
) -> list[AnalysisResult]:
    """Generates a list of analysis results for the given sample dictionaries.

    Args:
        before_samples: SampleDict corresponding to the control group.
        after_samples: SampleDict corresponding to the experiment group.
        metric_paths: A set of metric paths to compare.

    Returns:
        A list of analysis results.
    """
    out = []
    for metric_path in metric_paths:
        before_sample = before_samples[metric_path]
        after_sample = after_samples[metric_path]

        mwu_result = stats.mannwhitneyu(before_sample, after_sample)
        out.append(
            AnalysisResult(
                before_sample=before_sample,
                after_sample=after_sample,
                mwu_result=mwu_result,
            )
        )
    return out


def split_better_and_worse_by_mean(
    results: list[AnalysisResult],
) -> tuple[list[AnalysisResult], list[AnalysisResult]]:
    """Splits the given AnalysisResults into ones that got better and worse.

    If a result has no change, it is skipped.

    Args:
        results: A list of AnalysisResults.

    Returns:
        A tuple of two lists of better and worse AnalysisResults.
    """
    better = []
    worse = []
    for result in results:
        result.after_sample.mean()
        sign = result.after_sample.mean() - result.before_sample.mean()
        if sign == 0.0:
            logging.warn(
                f"Skipping metric with no changes - {result.metric_path()}. "
                "This may mean a subset of the data is duplicated between the "
                "control and experiment groups (ingested data may not have "
                "been cleared between runs)."
            )
            continue
        went_up = sign > 0.0
        if went_up == result.is_up_better():
            better.append(result)
        else:
            worse.append(result)
    return better, worse
