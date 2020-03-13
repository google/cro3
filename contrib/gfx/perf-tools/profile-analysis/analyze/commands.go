// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyze

import (
	"errors"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"
)

// Profiles bundles two profile-data items together.
type Profiles struct {
	p1 *ProfileData
	p2 *ProfileData
}

// Bundle the name and functions related to a command together.
type cmdFunction func(args []string, profiles *Profiles) error
type helpFunction func(args []string)
type cmdDispatch struct {
	helpInfo     string       // A short help string for the command.
	dispatchFunc cmdFunction  // The function to call to execute the command.
	moreHelp     helpFunction // Optional function to show more help.
}

// All commands tend to take similar options, encapsulated in this struct.
type cmdOptions struct {
	prof           *ProfileData
	filterRegex    string
	numItemsToShow int
	lessThanFunc   func(dsi DualStatistics, dsj DualStatistics) bool
	sortByChoice   string
	gpuThresholdNs int
	cpuThresholdNs int
}

// QUIT_REQUESTED isn't really an error but instead a request to exit the application.
var QUIT_REQUESTED error = errors.New("quit-requested")

// Dispatch table for all the available command except help. (Help is handled
// separately because go doesn't like to create a loop this table and the
// doPrintHelp that iterates over this table.)
var cmdDispatchTable = map[string]cmdDispatch{
	"quit": cmdDispatch{
		"Exit the console and go back to your regular life.",
		func(args []string, _ *Profiles) error { return QUIT_REQUESTED },
		nil},
	"call-stats": cmdDispatch{
		"(call-stats [p1|p2] f=regex) Print call stats for the calls identified by a regex.",
		doCallStats,
		moreHelpForCallStats},
	"swap-prof": cmdDispatch{
		"Swap profile1 and profile2, a no-op if there's only one profile.",
		doSwapProfiles,
		nil},
	"show-prof": cmdDispatch{
		"(show-prof) Show basic information for the available profile(s).",
		doShowProfileInfo,
		nil},
	"show-calls": cmdDispatch{
		"(show-calls [p1|p2]  [n=xx] [s=byGpuAvg|byCpuAvg]) Show information for xx\n" +
			"        most expensive calls for the selected profile",
		doShowCalls,
		moreHelpForShowCalls},
	"show-frames": cmdDispatch{
		"(show-frames [p1|p2]  [n=xx] [s=byGpuAvg|byCpuAvg] [f=regex]) Show information for xx\n" +
			"        most expensive frames for the selected profile",
		doShowFrames,
		moreHelpForShowFrame},
	"show-frame-details": cmdDispatch{
		"(show-frame-details N1[-N2]  [gt=xxx] [ct=xxx]) Show detailed call\n" +
			"        information for frame N1 to N2.",
		doShowFrameDetail,
		moreHelpForShowFrameDetails},
	"compare-profiles": cmdDispatch{
		"(compare-profiles [n=xx] [s=byGpuAvg|byCpuAvg]) Show timing comparison information for xx\n" +
			"        most expensive calls for prof1 / prof2",
		doCompareProfiles,
		showMoreHelpForCompareProfile},
	"plot-calls": cmdDispatch{
		"(plot-calls [p1|p2] f=regex) Plot call-name usage per frames.",
		doGraphCallUsage,
		nil},
}

// ExecCommand is the entry point to dispatch a command.
// args: the command and options as an array of string tokens.
// profiles: the profile(s) the command acts on.
// Returns nil if the command executes successfully or an error otherwise.
// Error QUIT_REQUESTED indicates the user want sto exit the app.
func ExecCommand(args []string, profiles *Profiles) error {
	if args[0] == "help" {
		return doPrintHelp(args[1:])
	}

	for cmdName, dispatch := range cmdDispatchTable {
		if cmdName == args[0] {
			return dispatch.dispatchFunc(args[1:], profiles)
		}
	}

	if len(args) > 0 && len(strings.Trim(args[0], "\n\r ")) > 0 {
		return fmt.Errorf("%s is not a recognized command", args[0])
	}
	return nil
}

// Look for either "p1" or "p2" in the command options and pick the appropriate
// profile from profiles. The default is p1.
func pickTargetProfile(args []string, profiles *Profiles) (prof *ProfileData, err error) {
	prof = profiles.p1
	for _, arg := range args {
		switch {
		case arg == "p1", arg == "P1":
			prof = profiles.p1
		case arg == "p2", arg == "P2":
			if prof = profiles.p2; prof == nil {
				err = fmt.Errorf("profile 2 is not available: %s", arg)
				return
			}
		default:
		}
	}
	err = nil
	return
}

// Parse the commands options from args and return options populated accordingly.
func parseCommandOptions(args []string, profiles *Profiles) (options cmdOptions, err error) {
	options = cmdOptions{
		prof:           profiles.p1,
		numItemsToShow: 0,
		lessThanFunc:   sortByDecCPUAvg,
		filterRegex:    "",
		sortByChoice:   "BYCPUAVG",
		gpuThresholdNs: 10000,
		cpuThresholdNs: 10000,
	}

	if options.prof, err = pickTargetProfile(args, profiles); err != nil {
		return
	}

	// If the target profile has no GPU timing data, set the default GPU threshold
	// to 0. Likewise for CPU timing data.
	if options.prof.sumGPUTimeNs == 0 {
		options.gpuThresholdNs = 0
	}
	if options.prof.sumCPUTimeNs == 0 {
		options.cpuThresholdNs = 0
	}

	for _, arg := range args {
		switch {
		case strings.HasPrefix(arg, "n="), strings.HasPrefix(arg, "N="):
			if options.numItemsToShow, err = strconv.Atoi(arg[2:]); err != nil {
				err = fmt.Errorf("invalid item-count option: %s", arg)
				return
			}
		case strings.ToUpper(arg) == "S=BYGPUAVG":
			options.lessThanFunc = sortByDecGPUAvg
			options.sortByChoice = "BYGPUAVG"
		case strings.ToUpper(arg) == "S=BYCPUAVG":
			options.lessThanFunc = sortByDecCPUAvg
			options.sortByChoice = "BYCPUAVG"
		case strings.HasPrefix(arg, "f="), strings.HasPrefix(arg, "F="):
			options.filterRegex = arg[2:]
		case strings.HasPrefix(arg, "gt="), strings.HasPrefix(arg, "GT="):
			if options.gpuThresholdNs, err = strconv.Atoi(arg[3:]); err != nil {
				err = fmt.Errorf("invalid GPU threshold value: %s", arg)
				return
			}
		case strings.HasPrefix(arg, "ct="), strings.HasPrefix(arg, "CT="):
			if options.cpuThresholdNs, err = strconv.Atoi(arg[3:]); err != nil {
				err = fmt.Errorf("invalid CPU threshold value: %s", arg)
				return
			}
		case arg == "p1", arg == "P1", arg == "p2", arg == "P2":
			continue // Parsed above.
		default:
			err = fmt.Errorf("invalid option: %s", arg)
			return
		}
	}

	return
}

// Parse a frame range from args, either as a single number N or a range N1-N2.
func parseFrameRange(args []string) (frame1 int, frame2 int, err error) {
	if args == nil {
		err = fmt.Errorf("No frame number specified")
		return
	}

	var arg = args[0]
	var parts = strings.Split(arg, "-")
	if frame1, err = strconv.Atoi(parts[0]); err != nil {
		err = fmt.Errorf("invalid frame range: %s", arg)
		return
	}

	frame2 = frame1
	if len(parts) > 1 {
		if frame2, err = strconv.Atoi(parts[1]); err != nil {
			err = fmt.Errorf("invalid frame range: %s", arg)
			return
		}
	}

	if frame1 > frame2 {
		frame2, frame1 = frame1, frame2
	}

	err = nil
	return
}

// The do<CmdName> functions below implements each command CmdName.
func doPrintHelp(args []string) error {
	// If args is not empty, look for a command name for which to print more
	// help info.
	if len(args) > 0 {
		for cmdName, dispatch := range cmdDispatchTable {
			if cmdName == args[0] {
				if dispatch.moreHelp != nil {
					dispatch.moreHelp(args)
				} else {
					fmt.Printf("No additional available for %s\n", cmdName)
				}
				return nil
			}
		}
	}

	// Print general help.
	fmt.Println(
		"\nType commands of the form: '-> command [options]'\n" +
			"Example: '-> show-calls p2 n=30 s=bycpuavg' shows the 30 most expensive calls in profile p2\n" +
			" sorted by decreasing cpu average time.\n" +
			"Type '-> help command' for more help on a specific command.\n" +
			"\nAvailable commands:")
	for cmdName, info := range cmdDispatchTable {
		fmt.Println(beginBold + cmdName + endBold + ": " + info.helpInfo)
	}

	return nil
}

func doCallStats(args []string, profiles *Profiles) error {
	var err error
	var options cmdOptions
	if options, err = parseCommandOptions(args, profiles); err != nil {
		return err
	}

	if options.filterRegex == "" {
		options.filterRegex = ".*" // I.e. show stats for everything.
	}

	var gpuStats, cpuStats Statistics
	if gpuStats, cpuStats, err = GatherStatisticsForCallNameRegex(
		options.prof, options.filterRegex); err != nil {
		return err
	}

	if options.prof.GetTotalGPUTimeNs() > 0 {
		fmt.Printf("GPU timing statistics for %s:\n", options.prof.label)
		printStats("  ", &gpuStats, options.prof.GetTotalGPUTimeNs())
	} else {
		fmt.Printf("GPU timing not available for %s:\n", options.prof.label)
	}

	if options.prof.GetTotalCPUTimeNs() > 0 {
		fmt.Printf("CPU timing statistics for %s:\n", options.prof.label)
		printStats("  ", &cpuStats, options.prof.GetTotalCPUTimeNs())
	} else {
		fmt.Printf("CPU timing not available for %s:\n", options.prof.label)
	}
	return nil
}

func doSwapProfiles(args []string, profiles *Profiles) error {
	if profiles.p2 != nil {
		profiles.p1, profiles.p2 = profiles.p2, profiles.p1
		fmt.Printf("Done: profile1 = %s, profile2 = %s", profiles.p1.label, profiles.p2.label)
	}
	return nil
}

func doShowProfileInfo(args []string, profiles *Profiles) error {
	fmt.Printf("Profile info for p1=%s:\n", profiles.p1.label)
	fmt.Printf("  Number of frames: %d\n", profiles.p1.GetFrameCount())
	fmt.Printf("  Total number of calls: %d\n", profiles.p1.GetCallCount())

	if profiles.p2 != nil {
		fmt.Printf("Profile info for p2=%s:\n", profiles.p2.label)
		fmt.Printf("  Number of frames: %d\n", profiles.p2.GetFrameCount())
		fmt.Printf("  Total number of calls: %d\n", profiles.p2.GetCallCount())
	}
	return nil
}

func doShowCalls(args []string, profiles *Profiles) error {
	var err error
	var options cmdOptions
	if options, err = parseCommandOptions(args, profiles); err != nil {
		return err
	}

	stats := GatherStatisticsForAllCallNames(options.prof)
	sort.Slice(stats, func(i, j int) bool {
		return options.lessThanFunc(stats[i], stats[j])
	})

	var gpuPerCallWeight = 100.0 / math.Max(options.prof.GetTotalGPUTimeNs(), 1e-6)
	var cpuPerCallWeight = 100.0 / math.Max(options.prof.GetTotalCPUTimeNs(), 1e-6)

	fmt.Printf("Profile: %s\n", options.prof.label)
	fmt.Printf("%30s %7s %20s %20s %20s %20s\n", "call", "count", " GPU|CPU avg   ",
		" GPU|CPU max   ", " GPU|CPU min   ", "GPU|CPU % total")
	fmt.Printf("--------------------------------------------------------------" +
		"-----------------------------------------------------------\n")
	for n, s := range stats {
		fmt.Printf("%30s %7d %9s |%9s %9s |%9s %9s |%9s %8.1f%% |%7.1f%%\n", s.callName,
			s.gpuStat.numSamples,
			timingToString(s.gpuStat.GetAverage()), timingToString(s.cpuStat.GetAverage()),
			timingToString(s.gpuStat.GetMax()), timingToString(s.cpuStat.GetMax()),
			timingToString(s.gpuStat.GetMin()), timingToString(s.cpuStat.GetMin()),
			s.gpuStat.GetSum()*gpuPerCallWeight, s.cpuStat.GetSum()*cpuPerCallWeight)

		if options.numItemsToShow > 0 && n == options.numItemsToShow-1 {
			break
		}
	}

	return nil
}

func doShowFrames(args []string, profiles *Profiles) error {
	var err error
	var options cmdOptions
	if options, err = parseCommandOptions(args, profiles); err != nil {
		return err
	}

	timing := GatherTimingForAllFrames(options.prof, options.filterRegex)
	sortFunc := func(i int, j int) bool {
		return timing[i].cpuTimeNs > timing[j].cpuTimeNs
	}
	if options.sortByChoice == "BYGPUAVG" {
		sortFunc = func(i int, j int) bool {
			return timing[i].gpuTimeNs > timing[j].gpuTimeNs
		}
	}
	sort.Slice(timing, sortFunc)

	fmt.Printf("Profile: %s\n", options.prof.label)
	fmt.Printf("%11s %7s %20s %20s\n", "frame num", "calls", "   GPU total ", "  CPU total ")
	fmt.Printf("---------------------------------------------------------------------\n")
	for n, t := range timing {
		gpuTime := float64(t.gpuTimeNs)
		cpuTime := float64(t.cpuTimeNs)
		fmt.Printf("%11d %7d %20s %20s\n", t.frameNum, t.callCount,
			timingToString(gpuTime), timingToString(cpuTime))

		if options.numItemsToShow > 0 && n == options.numItemsToShow-1 {
			break
		}
	}

	return nil
}

func doShowFrameDetail(args []string, profiles *Profiles) error {
	if len(args) < 1 {
		return fmt.Errorf("no frame number specified")
	}

	var firstFrame, lastFrame int
	var err error
	if firstFrame, lastFrame, err = parseFrameRange(args); err != nil {
		return err
	}

	var options cmdOptions
	if options, err = parseCommandOptions(args[1:], profiles); err != nil {
		return err
	}

	fmt.Printf("Frame details for frames #%d to %d\n", firstFrame, lastFrame)
	fmt.Printf("%6s %30s %9s %9s %9s %6s %6s      %9s %9s %7s %7s\n",
		"", "", "",
		"GPU   ", "CPU   ", "GPU 1", "CPU 1",
		"GPU   ", "CPU   ", "GPU 2", "CPU 2")
	fmt.Printf("%6s %30s %9s %9s %9s %6s %6s      %9s %9s %7s %7s\n",
		"frame", "call name", "call #",
		"Prof 1", "Prof 1", "%  ", "%  ",
		"Prof 2", "Prof 2", "%  ", "%  ")
	fmt.Printf("----------------------------------------------------------------" +
		"------------------------------------------------------------\n")

	var frameCount = 0
	for frameNum := firstFrame; frameNum <= lastFrame; frameNum++ {
		var addToFrameCount = 1
		var frameData1 []CallInfo = GatherCallDataForFrame(profiles.p1, frameNum)
		var totGPUTime1, totCPUTime1 int = GatherFrameTiming(profiles.p1, frameNum, "")

		var frameData2 []CallInfo
		var totGPUTime2, totCPUTime2 int
		if profiles.p2 != nil {
			frameData2 = GatherCallDataForFrame(profiles.p2, frameNum)
			totGPUTime2, totCPUTime2 = GatherFrameTiming(profiles.p2, frameNum, "")
		}

		var callCount = len(frameData1)
		var gpuWeight1 = 1.0
		if totGPUTime1 > 0 {
			gpuWeight1 = 100.0 / float64(totGPUTime1)
		}
		var cpuWeight1 = 1.0
		if totCPUTime1 > 0 {
			cpuWeight1 = 100.0 / float64(totCPUTime1)
		}
		var gpuWeight2 = 1.0
		if totGPUTime2 > 0 {
			gpuWeight2 = 100.0 / float64(totGPUTime2)
		}
		var cpuWeight2 = 1.0
		if totCPUTime2 > 0 {
			cpuWeight2 = 100.0 / float64(totCPUTime2)
		}

		for i := 0; i < callCount; i++ {
			c1 := frameData1[i]
			if c1.gpuDurationNs >= options.gpuThresholdNs && c1.cpuDurationNs >= options.cpuThresholdNs {
				frameCount += addToFrameCount
				addToFrameCount = 0

				gpu1Ns := float64(c1.gpuDurationNs)
				cpu1Ns := float64(c1.cpuDurationNs)
				fmt.Printf("%6d %30s %9d %9s %9s %5.1f%% %5.1f%%", frameNum, c1.callName,
					c1.callNum, timingToString(gpu1Ns), timingToString(cpu1Ns),
					gpuWeight1*gpu1Ns, cpuWeight1*cpu1Ns)

				if frameData2 == nil {
					fmt.Println("")
					continue
				}

				if i >= len(frameData2) {
					fmt.Println("        Frame not available in prof 2")
					continue
				}

				c2 := frameData2[i]
				if c2.callName != c1.callName {
					fmt.Printf("      Call name mismatch: %s\n", c2.callName)
					continue
				}

				gpu2Ns := float64(c2.gpuDurationNs)
				cpu2Ns := float64(c2.cpuDurationNs)
				fmt.Printf("      %9s %9s %5.1f%% %5.1f%%",
					timingToString(gpu2Ns), timingToString(cpu2Ns),
					gpuWeight2*gpu2Ns, cpuWeight2*cpu2Ns)

				fmt.Println("")
			}
		}
	}

	var totFrames = lastFrame - firstFrame + 1
	fmt.Printf("%d frames out of %d shown, or %.1f%%\n",
		frameCount, totFrames, 100.0*float32(frameCount)/float32(totFrames))
	return nil
}

func doCompareProfiles(args []string, profiles *Profiles) error {
	if profiles.p2 == nil {
		return fmt.Errorf("this command requires two profiles")
	}

	var err error
	var options cmdOptions
	if options, err = parseCommandOptions(args, profiles); err != nil {
		return err
	}

	var stats1 = GatherStatisticsForAllCallNames(profiles.p1)
	sort.Slice(stats1, func(i, j int) bool {
		return options.lessThanFunc(stats1[i], stats1[j])
	})

	var outStats, compareStats = GatherComparativeStats(
		stats1, profiles.p2, options.numItemsToShow)

	fmt.Printf("Compare statistics: %s / %s\n", profiles.p1.label, profiles.p2.label)
	fmt.Printf("%30s %7s %20s %20s %20s %20s\n", "", "", "Prof 1     ", "Prof 2     ",
		"Ratio p1/p2  ", "Diff p1-p2  ")
	fmt.Printf("%30s %7s %20s %20s %20s %20s\n", "call", "count", "GPU|CPU      ",
		"GPU|CPU      ", "GPU|CPU      ", "GPU|CPU      ")
	fmt.Printf("---------------------------------------------------------------" +
		"-------------------------------------------------------------\n")
	for n, stat2 := range outStats {
		stat1 := stats1[n]
		comp := compareStats[n]
		fmt.Printf("%30s %7d %9s |%9s %9s |%9s %9s |%9s %9s |%9s\n",
			stat2.callName, stat2.gpuStat.numSamples,
			timingToString(stat1.gpuStat.GetAverage()), timingToString(stat1.cpuStat.GetAverage()),
			timingToString(stat2.gpuStat.GetAverage()), timingToString(stat2.cpuStat.GetAverage()),
			ratioToString(comp.gpuAvgRatio), ratioToString(comp.cpuAvgRatio),
			timingToString(comp.gpuAvgDiff), timingToString(comp.cpuAvgDiff))

		if options.numItemsToShow > 0 && n == options.numItemsToShow-1 {
			break
		}
	}

	return nil
}

func doGraphCallUsage(args []string, profiles *Profiles) error {
	var err error
	var options cmdOptions
	if options, err = parseCommandOptions(args, profiles); err != nil {
		return err
	}

	if options.filterRegex == "" {
		return fmt.Errorf("no call name specified")
	}

	return PlotCallNameUsagePerFrame(options.prof, options.filterRegex)
}

func printStats(prefix string, stats *Statistics, totalTimeNs float64) {
	fmt.Printf("%sSample count:       %d\n", prefix, stats.numSamples)
	fmt.Printf("%sAverage call time:  %s\n", prefix, timingToString(stats.GetAverage()))
	fmt.Printf("%sMax call time:      %s\n", prefix, timingToString(stats.GetMax()))
	fmt.Printf("%sMin call time:      %s\n", prefix, timingToString(stats.GetMin()))
	fmt.Printf("%sStandard dev:       %s\n", prefix, timingToString(stats.GetStdDeviation()))
	fmt.Printf("%sTotal time in call: %s\n", prefix, timingToString(stats.GetSum()))
	percentInCall := 100.0 * stats.GetSum() / totalTimeNs
	fmt.Printf("%s%% of time in call: %.1f\n", prefix, percentInCall)
}

// Convert an incoming timing value in nanoseconds to a display string of the
// form x.y<unit>, where the unit is one of "nS", "uS", "mS" or "S" depending
// on the range of the input value.
func timingToString(timing float64) string {
	var unit = "nS"
	var t = timing
	switch {
	case math.Abs(timing) >= 1e9:
		t = timing * 1e-9
		unit = "S"
	case math.Abs(timing) >= 1e6:
		t = timing * 1e-6
		unit = "mS"
	case math.Abs(timing) >= 1000.0:
		t = timing * 0.001
		unit = "uS"
	}

	return fmt.Sprintf("%.1f %s", t, unit)
}

func ratioToString(ratio float64) string {
	fmtStr := "%5.2f"
	switch {
	case ratio >= 1e50:
		return "INF!"
	case ratio >= 1000.0:
		fmtStr = "%9.0f"
	case ratio <= 1.0:
		fmtStr = "%7.5f"
	}
	return fmt.Sprintf(fmtStr, ratio)
}

// The moreHelpFor<CmdName> functions below print extra help info for
// command CmdName.
const beginBold = "\033[1m"
const endBold = "\033[0m"

const helpForProfileOption = "  [p1 | p2] is useful when more than one profile was given when launching\n" +
	"            the analyzer tool. Use 'p1' to select the first profile or 'p2'\n" +
	"            to select the second profile. Default is p1.\n"

const helpForCallNameRegex = "  call-name-regex is a regular expression that specifies the call names to\n" +
	"            gather statistics for.\n"

const helpForSortOption = "  s=byGpuAvg|byCpuAvg sorts the ouput in either decreasing average GPU-time\n" +
	"            or decreasing average CPU-time. The default is byCpuAvg. This option is not case sensitive.\n" +
	"            I.e. s=bycpuavg is the same as s=byCpuAvg.\n"

func moreHelpForCallStats(args []string) {
	fmt.Println("\nHelp for call-stats command:\n" +
		"Show basic information for all calls that match the given regular expression.\n" +
		"Syntax: call-stats [p1 | p2] f=call-name-regex\n" +
		helpForProfileOption +
		helpForCallNameRegex +
		"\nExamples: call-stats p1 f=glDraw  or  call-stats f=glDraw")
}

func moreHelpForShowCalls(args []string) {
	fmt.Println("\nHelp for show-calls command:\n" +
		"Print the xx most expensive calls in profile p1 or p2, sorted in decreasing order.\n" +
		"Syntax: show-calls [p1 | p2] n=xx [s=byGpuAvg|byCpuAvg]\n" +
		helpForProfileOption +
		helpForSortOption +
		"\nExamples: show-calls p2 n=30 s=byCpuAvg,  show-calls n=40\n")
}

func moreHelpForShowFrame(args []string) {
	fmt.Println("\nHelp for show-frames command:\n" +
		"Print the xx most expensive frames in profile p1 or p2, sorted in decreasing order.\n" +
		"Optionally gather the timing in for only the calls filtered by regex." +
		"Syntax: show-frames [p1 | p2] n=xx [s=byGpuAvg|byCpuAvg] [f=regex]\n" +
		helpForProfileOption +
		helpForSortOption +
		"\nExamples: show-frames p2 n=30 s=byCpuAvg f=glDraw,  show-frames n=20\n")
}

func moreHelpForShowFrameDetails(args []string) {
	fmt.Println("\nHelp for show-frame-details command:\n" +
		"Print individual call information for a sequence of frames. The information printed\n" +
		"includes the call name, average GPU and CPU time spent in the call and the percentage\n" +
		"of the frame time spent in that call for the GPU and CPU. If a second profile is\n" +
		"available, the corresponding information for that profile is printed side-by-side.\n" +
		"The calls are printed in the order in which they occur in the frame.\n" +
		"Syntax: show-frame-details N1[-N2] gt=nnn ct=mmm\n" +
		helpForProfileOption +
		helpForSortOption +
		"  gt=nnn  only show calls that spend nnn nanoseconds or more in the GPU.\n" +
		"          Default is 100000 or 0 if no GPU timing data is available.\n" +
		"  ct=mmm  only show calls that spend mmm nanoseconds or more in the CPU.\n" +
		"          Default is 100000 or 0 if no CPU timing data is available.\n" +
		"\nExample: show-frame-details 100-120 gt=100000 ct=500000\n")
}

func showMoreHelpForCompareProfile(args []string) {
	fmt.Println("\nHelp for compare-profiles command:\n" +
		"Show side-by-side timing comparison for the xx most expensive calls taken from profile p1.\n" +
		"The comparison shows the average CPU and GPU time for each call in both profiles as well\n" +
		"as the ratio (time-for-p1)/(time-for-p2) and difference (time-for-p1) - (time-for-p2) for both\n" +
		"profiles for each of the calls.\n" +
		"Syntax: compare-profiles n=xx [s=byGpuAvg|byCpuAvg]\n" +
		helpForProfileOption +
		helpForSortOption +
		"\nExample: compare-profiles n=30 s=byCpuAvg\n")
}
