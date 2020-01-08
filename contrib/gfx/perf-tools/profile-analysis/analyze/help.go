// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyze

import (
	"fmt"
)

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
		"Syntax: show-frames [p1 | p2] n=xx [s=byGpuAvg|byCpuAvg]\n" +
		helpForProfileOption +
		helpForSortOption +
		"\nExamples: show-frames p2 n=30 s=byCpuAvg,  show-frames n=20\n")
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

func (console *Console) printHelp(args []string) error {
	// If args is not empty, look for a command name for which to print more
	// help info.
	if len(args) > 0 {
		for cmdName, dispatch := range console.cmdDispatch {
			if cmdName == args[0] {
				if dispatch.moreHelpFunc != nil {
					dispatch.moreHelpFunc(args)
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
	for cmdName, info := range console.cmdDispatch {
		fmt.Println(beginBold + cmdName + endBold + ": " + info.helpInfo)
	}

	return nil
}
