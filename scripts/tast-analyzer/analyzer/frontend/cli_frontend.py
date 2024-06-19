# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import dataclasses
import enum
from pathlib import Path

from analyzer.analysis import analysis_cfg
from analyzer.analysis import analysis_results
from analyzer.analysis import analyze_results
from analyzer.analysis.analysis_results import AnalysisResult
import click


class _CliAnalysis(enum.StrEnum):
    PRINT_BETTER_WORSE = "print_better_worse"
    PRINT_TEST_BREAKDOWN = "print_test_breakdown"
    PRINT_BY_PCT_CHANGE = "print_by_pct_change"
    PRINT_BY_T_STAT = "print_by_t_stat"
    PRINT_MEAN_PCT_CHANGE = "print_mean_pct_change"


@dataclasses.dataclass(frozen=True, kw_only=True, order=True)
class _CliFrontendCfg:
    cfg: analysis_cfg.AnalysisCfg = dataclasses.field(
        default_factory=analysis_cfg.AnalysisCfg
    )
    """The configuration for the statistical analysis."""

    analyses: list[_CliAnalysis] = dataclasses.field(
        default_factory=lambda: list(_CliAnalysis)
    )
    """The CLI analyses to run."""


def _print_results(results: list[AnalysisResult]) -> None:
    """Prints a human readable summary of the analysis results."""
    for r in results:
        print(r.summary())


def _compare_results(
    *,
    s1_name: str,
    s2_name: str,
    results: list[analysis_results.AnalysisResult],
    analyses: list[_CliAnalysis],
) -> None:
    better, worse = analysis_results.split_better_and_worse_by_mean(results)

    print(f"{len(results)} metrics, {len(better)} better, {len(worse)} worse")

    if _CliAnalysis.PRINT_BETTER_WORSE in analyses:
        print(f"{len(worse)} GOT WORSE FROM {s1_name} to {s2_name}")
        _print_results(worse)
        print()

        print(f"{len(better)} GOT BETTER FROM {s1_name} to {s2_name}")
        _print_results(better)
        print()

    # TODO: implement other analyses


@click.command()
@click.option(
    "-c",
    "--compare",
    type=click.Path(
        exists=True, dir_okay=False, resolve_path=True, path_type=Path
    ),
    help="stats tests",
    nargs=2,
    required=True,
)
@click.option(
    "--skip-all-zero/--no-skip-all-zero",
    type=bool,
    help="whether to skip samples with all zero values",
    default=True,
)
@click.option(
    "--minimum-sample-size",
    type=int,
    help="minimum sample size to include in the analysis",
    default=1,
)
@click.option(
    "-p",
    "--alpha-value",
    type=float,
    help="statistical significance level to use",
    default=0.05,
)
@click.option(
    "-m",
    "--multiple-test-correction",
    type=click.Choice(list(analysis_cfg.MultipleTestCfg)),
    help="correction method to use for multiple tests",
    default=analysis_cfg.MultipleTestCfg.FWER,
)
@click.option(
    "--metric-include-regex",
    type=str,
    help="regex to include metric paths by",
    required=False,
)
@click.option(
    "--metric-exclude-regex",
    type=str,
    help="regex to exclude metric paths by",
    required=False,
)
@click.option(
    "--remove-outliers/--no-remove-outliers",
    type=bool,
    help="clip min and max values as outliers",
    default=False,
)
def print_results(
    compare: list[Path],
    skip_all_zero: bool,
    minimum_sample_size: int,
    alpha_value: float,
    multiple_test_correction: analysis_cfg.MultipleTestCfg,
    metric_include_regex: str | None,
    metric_exclude_regex: str | None,
    remove_outliers: bool,
) -> None:
    cfg = analysis_cfg.AnalysisCfg(
        skip_all_zero_samples=skip_all_zero,
        minimum_sample_size=minimum_sample_size,
        alpha=alpha_value,
        multiple_test_cfg=multiple_test_correction,
        metric_exclude_regex=metric_exclude_regex,
        metric_include_regex=metric_include_regex,
        remove_outliers=remove_outliers,
    )

    clicfg = _CliFrontendCfg(cfg=cfg)
    results = analyze_results.analyze_results(
        compare[0], compare[1], clicfg.cfg
    )
    _compare_results(
        s1_name=compare[0].name,
        s2_name=compare[1].name,
        results=results,
        analyses=clicfg.analyses,
    )
