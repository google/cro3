# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import defaultdict
import copy
import dataclasses
import logging
from pathlib import Path
import re

from analyzer.analysis import analysis_cfg
from analyzer.analysis import analysis_results
from analyzer.analysis import metric_sample
from analyzer.backend import test_result
from statsmodels.stats import multitest


def _load_metrics_from_results_dict(
    results_dict: dict[test_result.TestResultKey, test_result.TestResult],
) -> metric_sample.SampleDict:
    metrics: metric_sample.SampleDict = {}

    logging.info(f"Examining {len(results_dict)} records")
    for key, result in sorted(results_dict.items()):
        val: float
        if isinstance(result.value, float):
            val = result.value
        elif isinstance(result.value, int):
            val = float(result.value)
        elif isinstance(result.value, list):
            # TODO(b/343114458): Consider using the entire sample somehow.
            # Currently, if there are multiple values we just take the mean.
            # Handling these as a sample is likely required to properly handle
            # TPS CUJ tests.
            val = sum(result.value) / len(result.value)
        else:
            assert False, f"Unknown value type: {result.value}"

        metric_path = key.metric_path()
        m = metrics.setdefault(
            metric_path,
            metric_sample.MetricSample(
                test_name=key.test_name,
                metric_path=metric_path,
                units=result.units,
                improvement_direction=result.improvement_direction,
                value_map={},
            ),
        )

        assert m.test_name == key.test_name
        assert m.metric_path == metric_path
        assert m.units == result.units
        assert m.improvement_direction == result.improvement_direction
        assert key.run_id not in m.value_map
        m.value_map[key.run_id] = val

    logging.info(f"Loaded {len(metrics)} metrics")
    sample_sizes: dict[int, int] = defaultdict(int)
    for v in metrics.values():
        sample_size = len(v.value_map)
        sample_sizes[sample_size] += 1
    logging.info(f"Sample size distribution: {sorted(sample_sizes.items())}")

    return metrics


def _prune_non_significant_results(
    results: list[analysis_results.AnalysisResult],
    cfg: analysis_cfg.AnalysisCfg,
) -> list[analysis_results.AnalysisResult]:
    """Prune results that are not significant."""
    out_results = []
    p_values = [r.mwu_result.p for r in results]
    rejects, p_corrected, _, _ = multitest.multipletests(
        p_values, alpha=cfg.alpha, method=cfg.multiple_test_cfg.scipy_name()
    )
    for r, reject, p in zip(results, rejects, p_corrected):
        # Reject the null hypothesis (that they are the same).
        if reject:
            r = copy.deepcopy(r)
            r.mwu_result.p = p
            out_results.append(r)
    return out_results


def _prune_regex_include(
    metrics: metric_sample.SampleDict, regex: str
) -> metric_sample.SampleDict:
    return {
        path: sample
        for path, sample in metrics.items()
        if re.search(regex, path)
    }


def _prune_regex_exclude(
    metrics: metric_sample.SampleDict, regex: str
) -> metric_sample.SampleDict:
    return {
        path: sample
        for path, sample in metrics.items()
        if not re.search(regex, path)
    }


def _prune_outliers(
    metrics: metric_sample.SampleDict,
) -> metric_sample.SampleDict:
    out_metrics = {}
    for k, v in metrics.items():
        vals = sorted(v.value_map.items(), key=lambda x: x[1])
        if len(vals):
            del vals[0]
        if len(vals):
            del vals[-1]
        out_metrics[k] = dataclasses.replace(v, value_map=dict(vals))
    return out_metrics


def analyze_results(
    sample1_path: Path, sample2_path: Path, cfg: analysis_cfg.AnalysisCfg
) -> list[analysis_results.AnalysisResult]:
    """Returns AnalysisResults for the given saved sample data paths."""
    before_results = test_result.load_test_result_dict_from_json(
        sample1_path.read_text()
    )
    after_results = test_result.load_test_result_dict_from_json(
        sample2_path.read_text()
    )
    before_samples = _load_metrics_from_results_dict(before_results)
    after_samples = _load_metrics_from_results_dict(after_results)

    if cfg.remove_outliers:
        before_samples = _prune_outliers(before_samples)
        after_samples = _prune_outliers(after_samples)

    if cfg.metric_include_regex:
        before_samples = _prune_regex_include(
            before_samples, cfg.metric_include_regex
        )
        after_samples = _prune_regex_include(
            after_samples, cfg.metric_include_regex
        )

    if cfg.metric_exclude_regex:
        before_samples = _prune_regex_exclude(
            before_samples, cfg.metric_exclude_regex
        )
        after_samples = _prune_regex_exclude(
            after_samples, cfg.metric_exclude_regex
        )

    metric_paths = analysis_results.compute_metric_paths_for_comparison(
        s1=before_samples, s2=after_samples, cfg=cfg
    )
    results = analysis_results.generate_analysis_results(
        before_samples=before_samples,
        after_samples=after_samples,
        metric_paths=metric_paths,
    )

    return _prune_non_significant_results(results, cfg)
