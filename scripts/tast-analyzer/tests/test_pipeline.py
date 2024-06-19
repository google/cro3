# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import dataclasses
from pathlib import Path
import unittest

from analyzer.analysis import analysis_cfg
from analyzer.analysis import analyze_results


FILES_DIR: Path = Path(__file__).parent.absolute().joinpath("files")


class PipelineTest(unittest.TestCase):
    def test_analyze_results_pruning(self) -> None:
        cfg = analysis_cfg.AnalysisCfg(
            skip_all_zero_samples=False,
            minimum_sample_size=1,
            alpha=1.0,
            multiple_test_cfg=analysis_cfg.MultipleTestCfg.FWER,
            metric_exclude_regex=None,
            metric_include_regex=None,
            remove_outliers=False,
        )
        results_unpruned = analyze_results.analyze_results(
            FILES_DIR.joinpath("results-chart-complex1.json"),
            FILES_DIR.joinpath("results-chart-complex2.json"),
            cfg,
        )
        cfg_pruned = dataclasses.replace(
            cfg,
            metric_exclude_regex="2windows",
            metric_include_regex="TabletMode",
            remove_outliers=True,
        )
        results_pruned = analyze_results.analyze_results(
            FILES_DIR.joinpath("results-chart-complex1.json"),
            FILES_DIR.joinpath("results-chart-complex2.json"),
            cfg_pruned,
        )
        self.assertLess(len(results_pruned), len(results_unpruned))

        for unpruned in results_unpruned:
            # If excluded or not included, it should not be in the pruned results.
            if (
                "2windows" in unpruned.metric_path()
                or "TabletMode" not in unpruned.metric_path()
            ):
                self.assertTrue(
                    all(
                        unpruned.metric_path() != v.metric_path()
                        for v in results_pruned
                    ),
                    f"Expected {unpruned.metric_path()} to not be in the pruned results.",
                )
            else:
                self.assertTrue(
                    any(
                        unpruned.metric_path() == v.metric_path()
                        for v in results_pruned
                    ),
                    f"Expected {unpruned.metric_path()} to be in the pruned results.",
                )
