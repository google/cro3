// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyze

import (
	"fmt"
	"io"
	"math"
	"sort"
	"strconv"
	"strings"

	"github.com/chzyer/readline"
)

type commandDispatch struct {
	helpInfo     string                    // A short help string for the command.
	dispatchFunc func(args []string) error // The dispatch function to call.
	moreHelpFunc func(args []string)       // Optional function to show more help.
}

// Map command name to command-dispatch info.
type commandDispatchTable = map[string]commandDispatch

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

// Console encapsulates an interactive console to issues profile-analysis
// commands.
type Console struct {
	profileData1  *ProfileData
	profileData2  *ProfileData
	cmdDispatch   commandDispatchTable
	exitRequested bool
}

// StartInteractive starts the console interactive mode.
func (console *Console) StartInteractive(prof1 *ProfileData, prof2 *ProfileData) {
	rl, err := readline.NewEx(&readline.Config{
		Prompt:       "-> ",
		AutoComplete: createCompleter(),
		HistoryFile:  "/tmp/_profile_analyzer_hist_.tmp",
	})

	if err != nil {
		fmt.Println(err.Error())
		return
	}
	defer rl.Close()

	console.cmdDispatch = make(map[string]commandDispatch)
	console.buildDispatchTable()
	console.profileData1 = prof1
	console.profileData2 = prof2

	for !console.exitRequested {
		cmd, err := rl.Readline()
		if err != nil {
			if err == io.EOF {
				break // Ctrl-D --> exit
			} else {
				continue // Ctrl-C --> discard cmd
			}
		}

		var tokens = strings.Fields(cmd)
		if len(tokens) > 0 {
			err := console.execCommand(tokens)
			if err != nil {
				fmt.Println(err.Error())
			}
		}
	}
}

// Create the command completer, used for tab-completion.
func createCompleter() *readline.PrefixCompleter {
	return readline.NewPrefixCompleter(
		readline.PcItem("help",
			readline.PcItem("call-stats"),
			readline.PcItem("swap-prof"),
			readline.PcItem("show-prof"),
			readline.PcItem("show-calls"),
			readline.PcItem("show-frames"),
			readline.PcItem("show-frame-details"),
			readline.PcItem("compare-profiles"),
			readline.PcItem("plot-calls"),
			readline.PcItem("quit")),
		readline.PcItem("quit"),
		readline.PcItem("call-stats"),
		readline.PcItem("swap-prof"),
		readline.PcItem("show-prof"),
		readline.PcItem("show-calls"),
		readline.PcItem("show-frames"),
		readline.PcItem("show-frame-details"),
		readline.PcItem("compare-profiles"),
		readline.PcItem("plot-calls"),
	)
}

func (console *Console) buildDispatchTable() {
	table := &console.cmdDispatch
	(*table)["help"] = commandDispatch{
		"Show help info.",
		func(args []string) error { return console.printHelp(args) },
		nil}
	(*table)["quit"] = commandDispatch{
		"Exit the console and go back to your regular life.",
		func(args []string) error { return console.doQuit(args) },
		nil}
	(*table)["call-stats"] = commandDispatch{
		"(call-stats [p1|p2] f=regex) Print call stats for the calls identified by a regex.",
		func(args []string) error { return console.doCallStats(args) },
		moreHelpForCallStats}
	(*table)["swap-prof"] = commandDispatch{
		"Swap profile1 and profile2, a no-op if there's only one profile.",
		func(args []string) error { return console.doSwapProfiles(args) },
		nil}
	(*table)["show-prof"] = commandDispatch{
		"(show-prof) Show basic information for the available profile(s).",
		func(args []string) error { return console.doShowProfileInfo(args) },
		nil}
	(*table)["show-calls"] = commandDispatch{
		"(show-calls [p1|p2]  [n=xx] [s=byGpuAvg|byCpuAvg]) Show information for xx\n" +
			"        most expensive calls for the selected profile",
		func(args []string) error { return console.doShowCalls(args) },
		moreHelpForShowCalls}
	(*table)["show-frames"] = commandDispatch{
		"(show-frames [p1|p2]  [n=xx] [s=byGpuAvg|byCpuAvg]) Show information for xx\n" +
			"        most expensive frames for the selected profile",
		func(args []string) error { return console.doShowFrames(args) },
		moreHelpForShowFrame}
	(*table)["show-frame-details"] = commandDispatch{
		"(show-frame-details N1[-N2]  [gt=xxx] [ct=xxx]) Show detailed call\n" +
			"        information for frame N1 to N2.",
		func(args []string) error { return console.doShowFrameDetail(args) },
		moreHelpForShowFrameDetails}
	(*table)["compare-profiles"] = commandDispatch{
		"(compare-profiles [n=xx] [s=byGpuAvg|byCpuAvg]) Show timing comparison information for xx\n" +
			"        most expensive calls for prof1 / prof2",
		func(args []string) error { return console.doCompareProfiles(args) },
		showMoreHelpForCompareProfile}
	(*table)["plot-calls"] = commandDispatch{
		"(plot-calls [p1|p2] f=regex) Plot call-name usage per frames.",
		func(args []string) error { return console.doGraphCallUsage(args) },
		nil}
}

func (console *Console) execCommand(args []string) error {
	for cmdName, dispatch := range console.cmdDispatch {
		if cmdName == args[0] {
			return dispatch.dispatchFunc(args[1:])
		}
	}

	if len(args) > 0 && len(strings.Trim(args[0], "\n\r ")) > 0 {
		return fmt.Errorf("%s is not a recognized command", args[0])
	}
	return nil
}

func (console *Console) parseTargetProfile(args []string, options *cmdOptions) (err error) {
	options.prof = console.profileData1
	for _, arg := range args {
		switch {
		case arg == "p1", arg == "P1":
			options.prof = console.profileData1
		case arg == "p2", arg == "P2":
			if options.prof = console.profileData2; options.prof == nil {
				err = fmt.Errorf("profile 2 is not available: %s", arg)
				return
			}
		default:
		}
	}

	return nil
}

func (console *Console) parseCommandOptions(args []string) (options cmdOptions, err error) {
	options = cmdOptions{
		prof:           console.profileData1,
		numItemsToShow: 0,
		lessThanFunc:   sortByDecCPUAvg,
		filterRegex:    "",
		sortByChoice:   "BYCPUAVG",
		gpuThresholdNs: 10000,
		cpuThresholdNs: 10000,
	}

	if err = console.parseTargetProfile(args, &options); err != nil {
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

func (console *Console) parseFrameRange(args []string) (frame1 int, frame2 int, err error) {
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

func (console *Console) doQuit(args []string) error {
	console.exitRequested = true
	return nil
}

func (console *Console) doCallStats(args []string) error {
	var err error
	var options cmdOptions
	if options, err = console.parseCommandOptions(args); err != nil {
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

func (console *Console) doSwapProfiles(args []string) error {
	if console.profileData2 != nil {
		console.profileData1, console.profileData2 = console.profileData2, console.profileData1
		fmt.Printf("Done: profile1 = %s, profile2 = %s", console.profileData1.label,
			console.profileData2.label)
	}
	return nil
}

func (console *Console) doShowProfileInfo(args []string) error {
	fmt.Printf("Profile info for p1=%s:\n", console.profileData1.label)
	fmt.Printf("  Number of frames: %d\n", console.profileData1.GetFrameCount())
	fmt.Printf("  Total number of calls: %d\n", console.profileData1.GetCallCount())

	if console.profileData2 != nil {
		fmt.Printf("Profile info for p2=%s:\n", console.profileData2.label)
		fmt.Printf("  Number of frames: %d\n", console.profileData2.GetFrameCount())
		fmt.Printf("  Total number of calls: %d\n", console.profileData2.GetCallCount())
	}
	return nil
}

func (console *Console) doShowCalls(args []string) error {
	var err error
	var options cmdOptions
	if options, err = console.parseCommandOptions(args); err != nil {
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

func (console *Console) doShowFrames(args []string) error {
	var err error
	var options cmdOptions
	if options, err = console.parseCommandOptions(args); err != nil {
		return err
	}

	timing := GatherTimingForAllFrames(options.prof)
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

func (console *Console) doShowFrameDetail(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("no frame number specified")
	}

	var firstFrame, lastFrame int
	var err error
	if firstFrame, lastFrame, err = console.parseFrameRange(args); err != nil {
		return err
	}

	var options cmdOptions
	if options, err = console.parseCommandOptions(args[1:]); err != nil {
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
		var frameData1 []CallInfo = GatherCallDataForFrame(console.profileData1, frameNum)
		var totGPUTime1, totCPUTime1 int = GatherFrameTiming(console.profileData1, frameNum)

		var frameData2 []CallInfo
		var totGPUTime2, totCPUTime2 int
		if console.profileData2 != nil {
			frameData2 = GatherCallDataForFrame(console.profileData2, frameNum)
			totGPUTime2, totCPUTime2 = GatherFrameTiming(console.profileData2, frameNum)
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

func (console *Console) doCompareProfiles(args []string) error {
	if console.profileData2 == nil {
		return fmt.Errorf("this command requires two profiles")
	}

	var err error
	var options cmdOptions
	if options, err = console.parseCommandOptions(args); err != nil {
		return err
	}

	var stats1 = GatherStatisticsForAllCallNames(console.profileData1)
	sort.Slice(stats1, func(i, j int) bool {
		return options.lessThanFunc(stats1[i], stats1[j])
	})

	var outStats, compareStats = GatherComparativeStats(
		stats1, console.profileData2, options.numItemsToShow)

	fmt.Printf("Compare statistics: %s / %s\n",
		console.profileData1.label, console.profileData2.label)
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

func (console *Console) doGraphCallUsage(args []string) error {
	var err error
	var options cmdOptions
	if options, err = console.parseCommandOptions(args); err != nil {
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
