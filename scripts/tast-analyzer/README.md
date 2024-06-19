## Introduction

NOTE: This directory is currently WIP.

Performance test results (particularly from Tast tests) can be very noisy. This
software package is for when you have a feature or change and you want to see
what difference it makes on the whole (so you can't use microbenchmarks, or you
want to see a holistic picture) but the effect size is low so you can't see it
on e.g. the TPS dashboard. For example, changes of 5%, 10% etc can be impossible
to pick out easily for very noisy metrics.

This package runs statistical tests on the /tmp/tast/results directory and
compares all metrics generated. It reports the statically significant ones in
order of effect size (and other orderings).

For example, if I have a change in chrome code and I want to see how it affects
power, but it only changes it by 1% or so, I can run tast tests with and without
the change 10 to 30 times then compare the produced metrics and find the
statistically significant ones with large changes.

It's useful to do this so you can check that your changes:

1. Have the intended beneficial effect you expect.
2. Don't have unintended deleterious effects (e.g. improve FPS but regress
   power).
3. Are impactful.

It's also useful to have all the statistics done for you.

## How to build for local perf tests

This section describes how to build and deploy, assuming you want to replicate a
release environment while keeping random variation down.

### Ash-chrome
Modify
[CheckStudyPolicyRestriction](https://source.chromium.org/chromium/chromium/src/+/main:components/variations/study_filtering.cc;l=153;drc=0d5fd0dbd26e4cc48c2b5ba35412c1045ab16dfb)
to always return false.

Be careful not to just append the args to out_SDK_BOARD/Release/args.gn if you
are using shell-based simplechrome. It will work the first time, but get removed
when re-entering the simplechrome shell. Better to specify the args when
entering the shell:

`cros chrome-sdk --board=BOARD --log-level=info  --internal --cfi --thinlto``

We want these args:

```
use_goma=true
is_debug=false
is_chrome_branded=true
is_official_build=true
dcheck_always_on=false
use_thin_lto = true
is_cfi = true
is_component_build = false
```

### Lacros-chrome

Make sure to modify CheckStudyPolicyRestriction as described above.

Build flags should be like this:

```
import("//build/args/chromeos/amd64-generic-crostoolchain.gni")
target_os="chromeos"
is_chromeos_device=true
chromeos_is_browser_only=true
use_goma=true
is_debug=false
is_chrome_branded=true
is_official_build=true
dcheck_always_on=false
use_thin_lto = true
is_cfi = true
is_component_build = false
``````

Note that you need:
```
"custom_vars": {
  "checkout_pgo_profiles": True,
},
```
in .gclient.

### ChromeOS image

You need these USE flags:

```
export USE="chrome_internal -cros-debug"
```

```
build_packages --board=BOARD --withdev --use-any-chrome
build_image --board=BOARD --noenable_rootfs_verification test
```

## How to run local perf tests

Create a script like this and run it after deploying what you need to test. For
example, if you have a change that may affect both ash-chrome and lacros-chrome,
you should deploy both. The following script is for that situation:

```sh
#!/bin/sh
for i in {1..10}; do
time tast run --var=lacros.DeployedBinary=/usr/local/lacros-chrome dut-1 \
ui.DesksCUJ ui.DesksCUJ.lacros ui.OverviewPerf ui.OverviewPerf.lacros
done
```

To get enough statistical power, run at least 10 times (preferably more like
30). Replace "dut-1" with the hostname of your dut. lacros.DeployedBinary is
specified, meaning use the deployed lacros. Look for tast tests that your change
may affect.

## How to run the analysis

First direct the tool to a tast results directory (/tmp/tast/results) from
before your change and have it extract the metrics. The tool will write into a
file called `data.json`:

`python3 -m analyzer.main --gather <path>`

Then rename the data.json file to something like `before_change.json` and run
again on the tast results directory after your change.

Then, run the analysis:

`python3 -m analyzer.main --compare before_change.json after_change.json`

This will by default use a false discovery rate (FDR) of 5%, meaning that around
5% of the statistical significance results will be wrong. Think of this like a
p-value, but for a set of things.

You may find it useful to change the FDR:

`python3 -m analyzer.main --compare before_change.json after_change.json -p
0.01`

Or to disable statistical significance checking entirely by passing -1:

`python3 -m analyzer.main --compare before_change.json after_change.json -p -1`

I generally run first without statistical significance checking and look for
high percentage change metrics. This is useful if it misses out on a large
percent change due to lack of statistical power.

This software is still in development, so it's useful to read the source code.
In particular, you can change the analyses produced / graphs etc - look in
analyse.py.

### How to get more statistical power

If you have a nice improvement in metrics but it's not statistically
significant, it doesn't mean it doesn't exist. You just may not have enough
statistical power. Here's what you can do:

Run the Tast tests more times. This will give more statistical power.

Restrict the metrics analysed to a subset using the `-i` (include) or `-e`
(exclude) flag. This flag takes a regex and restricts to, or excludes metric
names matching that regex. Since the FDR is like a budget over many tests with
varying p-values, restricting to the set you are interested in can give more
statistical power. Be careful though, if you are finding yourself doing a lot of
work to restrict subsets to get a paritcular metric or set of metrics to be
statstically significant, you are probably p-hacking. It's best to decide the
set of metrics you care about /before/ looking at whether they are statistically
significant or not. c.f. the concept of pre-registered clinical trials.

## Tips

Some tests may be sensitive to device state after logout, in that case you can
reboot between tests (make sure to sudo emerge sshpass):

```
  sshpass -p test0000 ssh dut-eth reboot
  sleep 120
```

- Try to ensure a stable temperature of the room
- Do not move the dut or adjust it during the test, because it can affect the
  thermal environment (e.g. resting on a wooden desk or metal plate)
- Use the same exact device - thermal properties and performance differs even
  between the same SKU.
- Be careful of spurious results - we still need to analyse and understand the
  changes we see.
