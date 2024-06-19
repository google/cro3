# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dataclasses
import enum


class MultipleTestCfg(enum.StrEnum):
    """Configuration for how to handle ensemble statistical testing.

    We need to test many metrics against each-other. In general,
    tast-analyzer errs on the side of avoiding false positives at the expense
    of false negatives (i.e. you may miss a change, but you won't get a
    spurious change reported). Due to the nature of the Tast benchmarks, metrics
    are often non-independent (positively or negatively correlated). For
    example, improving performance is likely to make many metrics go up, so
    they are positively correlated.

    Controlling for FWER is useful if you want to minimize the number of false
    positives as much as possible. Controlling for FDR is useful if you are
    doing a more explorative comparison and want to see more things that might
    have improved or got worse.
    """

    FWER = "fwer"
    """Holm-Bonferroni procedure for controlling FWER.

    Use this for guaranteeing that the chance of one or more false positives is
    less than the significance level AnalysisCfg.alpha.

    Assumptions: None. """

    FDR = "fdr"
    """Benjamini-Yekutieli procedure for controlling FDR.

    Use this for guaranteeing that the rate of false positives is the
    significance level AnalysisCfg.alpha.

    Assumptions: None. """

    def scipy_name(self) -> str:
        """Gets the name used by SciPy for the multiple test procedure."""
        if self == self.FWER:
            return "holm"
        elif self == self.FDR:
            return "fdr_by"
        else:
            raise ValueError(f"Unknown MultipleTestCfg: {self}")


@dataclasses.dataclass(frozen=True, kw_only=True, order=True)
class AnalysisCfg:
    skip_all_zero_samples: bool = True
    """Whether to skip all zero samples in the analysis."""

    minimum_sample_size: int = 1
    """The minimum sample size required to include a sample in the analysis."""

    alpha: float = 0.05
    """The significance level for the analysis."""

    multiple_test_cfg: MultipleTestCfg = MultipleTestCfg.FWER
    """The multiple test procedure to use."""

    metric_include_regex: str | None = None
    """Filter analyzed metrics to only those that match this regex."""

    metric_exclude_regex: str | None = None
    """Filter analyzed metrics to only those that do not match this regex.
    Excluding overrides including."""

    remove_outliers: bool = False
    """Whether to remove outlier values.

    This uses a simple strategy of removing one maximum and one minimum value
    from each sample."""
