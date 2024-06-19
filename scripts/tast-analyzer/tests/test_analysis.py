# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import copy
from pathlib import Path
import unittest

from analyzer.analysis import analysis_cfg
from analyzer.analysis import analysis_results
from analyzer.analysis import analyze_results
from analyzer.analysis import metric_sample
from analyzer.analysis import stats
from analyzer.backend import tast_results_dir


FILES_DIR: Path = Path(__file__).parent.absolute().joinpath("files")


class AnalysisTest(unittest.TestCase):
    def _load_samples(
        self,
    ) -> tuple[metric_sample.SampleDict, metric_sample.SampleDict]:
        before_results = tast_results_dir._load_results_from_results_chart_json(
            Path("/before/tests/ui.OverviewPerf/results-chart.json"),
            FILES_DIR.joinpath("results-chart-analysis1.json").read_text(),
        )
        after_results = tast_results_dir._load_results_from_results_chart_json(
            Path("/after/tests/ui.OverviewPerf/results-chart.json"),
            FILES_DIR.joinpath("results-chart-analysis2.json").read_text(),
        )

        before_samples = analyze_results._load_metrics_from_results_dict(
            before_results
        )
        after_samples = analyze_results._load_metrics_from_results_dict(
            after_results
        )

        return before_samples, after_samples

    def test_load_samples(self) -> None:
        before_samples, after_samples = self._load_samples()

        self.assertEqual(
            before_samples,
            {
                "ui.OverviewPerf.Test.One.average": metric_sample.MetricSample(
                    test_name="ui.OverviewPerf",
                    metric_path="ui.OverviewPerf.Test.One.average",
                    units="percent",
                    improvement_direction=metric_sample.ImprovementDirection.UP,
                    value_map={"before": 0},
                ),
                "ui.OverviewPerf.Test.Three.average": metric_sample.MetricSample(
                    test_name="ui.OverviewPerf",
                    metric_path="ui.OverviewPerf.Test.Three.average",
                    units="percent",
                    improvement_direction=metric_sample.ImprovementDirection.UP,
                    # Currently we take the arithmetic mean of lists of values.
                    value_map={"before": 2},
                ),
                "ui.OverviewPerf.Test.Two.average": metric_sample.MetricSample(
                    test_name="ui.OverviewPerf",
                    metric_path="ui.OverviewPerf.Test.Two.average",
                    units="percent",
                    improvement_direction=metric_sample.ImprovementDirection.UP,
                    value_map={"before": 2},
                ),
            },
        )

        self.assertEqual(
            after_samples,
            {
                "ui.OverviewPerf.Test.One.average": metric_sample.MetricSample(
                    test_name="ui.OverviewPerf",
                    metric_path="ui.OverviewPerf.Test.One.average",
                    units="percent",
                    improvement_direction=metric_sample.ImprovementDirection.UP,
                    value_map={"after": 1},
                ),
                "ui.OverviewPerf.Test.Three.average": metric_sample.MetricSample(
                    test_name="ui.OverviewPerf",
                    metric_path="ui.OverviewPerf.Test.Three.average",
                    units="percent",
                    improvement_direction=metric_sample.ImprovementDirection.UP,
                    # Currently we take the arithmetic mean of lists of values.
                    value_map={"after": 1},
                ),
                "ui.OverviewPerf.Test.Four.average": metric_sample.MetricSample(
                    test_name="ui.OverviewPerf",
                    metric_path="ui.OverviewPerf.Test.Four.average",
                    units="percent",
                    improvement_direction=metric_sample.ImprovementDirection.UP,
                    value_map={"after": 2},
                ),
            },
        )

    def test_compute_metric_paths_for_comparison(self) -> None:
        before_samples, after_samples = self._load_samples()

        cfg = analysis_cfg.AnalysisCfg(
            skip_all_zero_samples=False, minimum_sample_size=1
        )
        metric_paths = analysis_results.compute_metric_paths_for_comparison(
            before_samples, after_samples, cfg
        )
        # We should only look at the common metric paths.
        self.assertEqual(
            metric_paths,
            [
                "ui.OverviewPerf.Test.One.average",
                "ui.OverviewPerf.Test.Three.average",
            ],
        )

        # ui.OverviewPerf.Test.One.average has only zeros, so we should skip it.
        cfg = analysis_cfg.AnalysisCfg(
            skip_all_zero_samples=True, minimum_sample_size=1
        )
        metric_paths = analysis_results.compute_metric_paths_for_comparison(
            before_samples, after_samples, cfg
        )
        self.assertEqual(metric_paths, ["ui.OverviewPerf.Test.Three.average"])

        # Sample size is one for all metrics, so this should produce nothing.
        cfg = analysis_cfg.AnalysisCfg(
            skip_all_zero_samples=False, minimum_sample_size=2
        )
        metric_paths = analysis_results.compute_metric_paths_for_comparison(
            before_samples, after_samples, cfg
        )
        self.assertEqual(metric_paths, [])

    def test_split_better_and_worse_by_mean(self) -> None:
        before_samples, after_samples = self._load_samples()
        cfg = analysis_cfg.AnalysisCfg(
            skip_all_zero_samples=False, minimum_sample_size=1
        )
        metric_paths = analysis_results.compute_metric_paths_for_comparison(
            before_samples, after_samples, cfg
        )
        self.assertEqual(
            metric_paths,
            [
                "ui.OverviewPerf.Test.One.average",
                "ui.OverviewPerf.Test.Three.average",
            ],
        )

        results = analysis_results.generate_analysis_results(
            before_samples=before_samples,
            after_samples=after_samples,
            metric_paths=metric_paths,
        )
        better_result = analysis_results.AnalysisResult(
            before_sample=before_samples[metric_paths[0]],
            after_sample=after_samples[metric_paths[0]],
            mwu_result=stats.MannWhitneyUResult(u=0.0, p=1.0),
        )
        worse_result = analysis_results.AnalysisResult(
            before_sample=before_samples[metric_paths[1]],
            after_sample=after_samples[metric_paths[1]],
            mwu_result=stats.MannWhitneyUResult(u=1.0, p=1.0),
        )
        self.assertEqual(
            results,
            [
                better_result,
                worse_result,
            ],
        )

        better, worse = analysis_results.split_better_and_worse_by_mean(results)
        self.assertEqual(better, [better_result])
        self.assertEqual(worse, [worse_result])

    def _make_analysis_result(
        self, u: float, p: float
    ) -> analysis_results.AnalysisResult:
        placeholder = metric_sample.MetricSample(
            test_name="placeholder",
            metric_path="placeholder",
            units="placeholder",
            improvement_direction=metric_sample.ImprovementDirection.UP,
            value_map={},
        )
        return analysis_results.AnalysisResult(
            before_sample=placeholder,
            after_sample=placeholder,
            mwu_result=stats.MannWhitneyUResult(u=u, p=p),
        )

    def test_prune_non_significant_results(self) -> None:
        cfg = analysis_cfg.AnalysisCfg(
            alpha=0.01, multiple_test_cfg=analysis_cfg.MultipleTestCfg.FWER
        )
        results = [
            self._make_analysis_result(u=0.0, p=0.001),
            self._make_analysis_result(u=0.0, p=0.002),
            self._make_analysis_result(u=0.0, p=0.003),
            self._make_analysis_result(u=0.0, p=0.004),
            self._make_analysis_result(u=0.0, p=0.005),
            self._make_analysis_result(u=0.0, p=0.006),
        ]
        pruned = analyze_results._prune_non_significant_results(results, cfg)
        self.assertEqual(len(pruned), 2)
        # Check p-values were adjusted.
        self.assertEqual(pruned[0].mwu_result.p, 0.006)
        self.assertEqual(pruned[1].mwu_result.p, 0.01)

    def test_prune_regex_include(self) -> None:
        before_samples, after_samples = self._load_samples()

        test_two_path = "ui.OverviewPerf.Test.Two.average"
        test_three_path = "ui.OverviewPerf.Test.Three.average"

        self.assertEqual(
            before_samples,
            analyze_results._prune_regex_include(before_samples, "Test.*"),
        )
        self.assertEqual(
            {}, analyze_results._prune_regex_include(before_samples, "^Test$")
        )
        self.assertEqual(
            {test_three_path: before_samples[test_three_path]},
            analyze_results._prune_regex_include(
                before_samples, r"Test\.Three"
            ),
        )
        self.assertEqual(
            {test_three_path: before_samples[test_three_path]},
            analyze_results._prune_regex_include(before_samples, "Test.*ee"),
        )
        self.assertEqual(
            {test_two_path: before_samples[test_two_path]},
            analyze_results._prune_regex_include(before_samples, "Test.*o"),
        )
        self.assertEqual(
            {test_three_path: after_samples[test_three_path]},
            analyze_results._prune_regex_include(
                after_samples, r"^ui\.OverviewPerf\.Test\.Three\.average$"
            ),
        )

    def test_prune_regex_exclude(self) -> None:
        before_samples, after_samples = self._load_samples()

        test_two_path = "ui.OverviewPerf.Test.Two.average"
        test_three_path = "ui.OverviewPerf.Test.Three.average"

        self.assertEqual(
            {},
            analyze_results._prune_regex_exclude(before_samples, "Test.*"),
        )
        self.assertEqual(
            before_samples,
            analyze_results._prune_regex_exclude(before_samples, "^Test$"),
        )
        self.assertEqual(
            {k: v for k, v in before_samples.items() if k != test_three_path},
            analyze_results._prune_regex_exclude(
                before_samples, r"Test\.Three"
            ),
        )
        self.assertEqual(
            {k: v for k, v in before_samples.items() if k != test_three_path},
            analyze_results._prune_regex_exclude(before_samples, "Test.*ee"),
        )
        self.assertEqual(
            {k: v for k, v in before_samples.items() if k != test_two_path},
            analyze_results._prune_regex_exclude(before_samples, "Test.*o"),
        )
        self.assertEqual(
            {k: v for k, v in after_samples.items() if k != test_three_path},
            analyze_results._prune_regex_exclude(
                after_samples, r"^ui\.OverviewPerf\.Test\.Three\.average$"
            ),
        )

    def test_prune_outliers(self) -> None:
        samples = {
            "test.name.metric.path": metric_sample.MetricSample(
                test_name="ui.OverviewPerf",
                metric_path="test.name.metric.path",
                units="percent",
                improvement_direction=metric_sample.ImprovementDirection.UP,
                value_map={},
            )
        }
        samples_pruned = copy.deepcopy(samples)
        self.assertEqual(
            samples_pruned,
            analyze_results._prune_outliers(samples),
        )

        samples["test.name.metric.path"].value_map["test1"] = 1
        self.assertEqual(
            samples_pruned,
            analyze_results._prune_outliers(samples),
        )

        samples["test.name.metric.path"].value_map["test2"] = 2
        self.assertEqual(
            samples_pruned,
            analyze_results._prune_outliers(samples),
        )

        # Remove highest and lowest.
        samples["test.name.metric.path"].value_map["test3"] = 3
        samples_pruned["test.name.metric.path"].value_map["test2"] = 2
        self.assertEqual(
            samples_pruned,
            analyze_results._prune_outliers(samples),
        )
