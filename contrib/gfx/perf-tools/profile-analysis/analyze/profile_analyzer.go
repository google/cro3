// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyze

import (
	"fmt"
	"math"
	"math/rand"
	"regexp"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

// CheckProfileEquivalence returns whether two profiles are equivalent. Two
// profiles are equivalent if whatever each call numbers they have in common
// calls into the same api name (call name). E.g. if call num 101 in prof1
// calls glClear then call 101 in prof2 must also call glClear.
func CheckProfileEquivalence(prof1 *ProfileData, prof2 *ProfileData) bool {
	// Iterate over the call in the smaller profile.
	if prof1.GetCallCount() > prof2.GetCallCount() {
		prof1, prof2 = prof2, prof1
	}

	// Verifying all calls would take too much time. Instead we use a random # to
	// verify about 1/10 call.
	s1 := rand.NewSource(time.Now().UnixNano())
	r1 := rand.New(s1)

	// Feed randomly selected call-info from profile1 into channel callsFromProf1.
	type callInfo struct {
		callNum  int
		callName string
	}
	var callsFromProf1 = make(chan callInfo, 32)
	go func() {
		for _, callRecord := range prof1.allCalls {
			if r1.Intn(100) >= 90 {
				var callNum = callRecord.callNum
				var callNumData = prof1.callsByCallNum[callNum]
				callsFromProf1 <- callInfo{callNum, callNumData.callName}
			}
		}
		close(callsFromProf1)
	}()

	// Compare calls selected above with the corresponding calls in profile2.
	var numCallsMatch int32 = 0
	var numCallsMismatch int32 = 0
	for c := range callsFromProf1 {
		go func(c callInfo) {
			if prof2.VerifyCallNum(c.callNum, c.callName) {
				atomic.AddInt32(&numCallsMatch, 1)
			} else {
				atomic.AddInt32(&numCallsMismatch, 1)
			}
		}(c)

		// Show progress.
		n := atomic.LoadInt32(&numCallsMatch)
		if (n & 0xffff) == 0 {
			fmt.Print(".")
		}
	}

	// The two profiles need not share all the same call nums. But we do expect
	// to verify at least some call nums to be equivalent and no call should
	// mismatch.
	fmt.Printf("\n%d api calls match and %d calls do not match.\n",
		numCallsMatch, numCallsMismatch)
	return numCallsMatch > 0 && numCallsMismatch == 0
}

// GatherStatisticsForCallNameRegex gathers statistics information for all the
// call names in the profile that match the given regex.
func GatherStatisticsForCallNameRegex(prof *ProfileData, callNameRegEx string) (
	gpuStat Statistics, cpuStat Statistics, err error) {

	// Traverse all calls in profile with a filter based on regex.
	var re *regexp.Regexp
	if re, err = regexp.Compile(callNameRegEx); err != nil {
		return
	}

	c := make(chan int, 64)
	filter := func(c CallInfo) bool {
		return re.MatchString(c.callName)
	}
	go func() {
		prof.TraverseAllCalls(filter, c)
	}()

	// Gather statistic for the calls that match regex.
	for callIndex := range c {
		call := prof.GetCallRecordByIndex(callIndex)
		gpuStat.AddSample(float64(call.gpuDurationNs))
		cpuStat.AddSample(float64(call.cpuDurationNs))
	}

	if gpuStat.GetNumSamples() == 0 {
		err = fmt.Errorf("ERROR: no call matched call-name regex %s", callNameRegEx)
	}
	return
}

// GatherStatisticsForAllCallNames gathers statistics info for all the available
// call names in the given profile.
func GatherStatisticsForAllCallNames(prof *ProfileData) (stats []CallNameStatistics) {
	var wait sync.WaitGroup

	// Gather per-call-name call data through an async goroutine that feeds into
	// callDataChan.
	callDataChan := make(chan CallNameData, 64)
	go func() { prof.TraverseByCallName(callDataChan) }()

	// Gather the per-call-name statistics through another async goroutine, which
	// get stats data from outResultChan and store into out-array stats.
	outResultChan := make(chan CallNameStatistics, 64)
	go func() {
		for r := range outResultChan {
			stats = append(stats, r)
			wait.Done()
		}
	}()

	// The limiter is used to limit the number of goroutines below.
	numCoroutines := runtime.NumCPU()
	limiter := make(chan int, numCoroutines)

	// Launch a series of async goroutines to calculate the timing statistics for
	// each call name. Each goroutine feeds the stats data to channel
	// outResultChan.
	for callData := range callDataChan {
		limiter <- 1 // Blocks if there are already too many goroutines in flight.
		wait.Add(1)

		go func(name string, callIndices []int) {
			gpuStat := Statistics{}
			cpuStat := Statistics{}
			for _, i := range callIndices {
				data := prof.GetCallRecordByIndex(i)
				gpuStat.AddSample(float64(data.gpuDurationNs))
				cpuStat.AddSample(float64(data.cpuDurationNs))
			}

			outResultChan <- CallNameStatistics{name, gpuStat, cpuStat}
			<-limiter
		}(callData.callName, callData.callIndices)
	}

	wait.Wait() // Wait until all goroutines are done.
	return
}

// GatherComparativeStats gathers comparative statistics for two profiles.
// Comparative statistics consists of the ratio and difference between the
// average GPU and CPU time by call name for up to <count> calls in the profiles.
func GatherComparativeStats(
	statsProf1 []CallNameStatistics, prof2 *ProfileData, count int) (
	statsProf2 []CallNameStatistics, compareStats []CompareStats) {

	for i, callStats := range statsProf1 {
		var callName = callStats.callName
		var gpuStat2 = Statistics{}
		var cpuStat2 = Statistics{}
		var comparison = CompareStats{}
		if callIndices := prof2.GetCallIndicesForName(callName); callIndices != nil {
			for _, callIndex := range callIndices {
				data := prof2.GetCallRecordByIndex(callIndex)
				gpuStat2.AddSample(float64(data.gpuDurationNs))
				cpuStat2.AddSample(float64(data.cpuDurationNs))
			}
		}

		comparison.gpuAvgDiff = callStats.gpuStat.GetAverage() - gpuStat2.GetAverage()
		comparison.cpuAvgDiff = callStats.cpuStat.GetAverage() - cpuStat2.GetAverage()

		// Avoid divide by zero, when there's no GPU stats.
		if math.Abs(gpuStat2.GetAverage()) >= 1e-6 {
			comparison.gpuAvgRatio = callStats.gpuStat.GetAverage() / gpuStat2.GetAverage()
		} else {
			// A very large number that the console knows to ignore.
			comparison.gpuAvgRatio = 1e200
		}
		// Avoid divide by zero, when there's no CPU stats.
		if math.Abs(cpuStat2.GetAverage()) >= 1e-6 {
			comparison.cpuAvgRatio = callStats.cpuStat.GetAverage() / cpuStat2.GetAverage()
		} else {
			// A very large number that the console knows to ignore.
			comparison.cpuAvgRatio = 1e200
		}

		statsProf2 = append(statsProf2, CallNameStatistics{callName, gpuStat2, cpuStat2})
		compareStats = append(compareStats, comparison)

		if count > 0 && i == count-1 {
			break
		}
	}

	return
}

// GatherNumCallsPerFrame calculates the number of times api function(s) that
// match the given regex are called in each frame and returns the result as
// an array indexed by frame num.
func GatherNumCallsPerFrame(prof *ProfileData, callNameRegEx string) ([]int, error) {
	// Traverse all calls in profile with a filter based on regex.
	var re *regexp.Regexp
	var err error
	if re, err = regexp.Compile(callNameRegEx); err != nil {
		return nil, err
	}

	c := make(chan int, 20)
	filter := func(c CallInfo) bool {
		return re.MatchString(c.callName)
	}
	go func() {
		prof.TraverseAllCalls(filter, c)
	}()

	callCount := make([]int, prof.GetFrameCount())
	for callIndex := range c {
		callRecord := prof.GetCallRecordByIndex(callIndex)
		callCount[callRecord.frameNum]++
	}

	return callCount, nil
}

// GatherCallDataForFrame gather the call information for all the calls in a
// frame identified by its frame number and returns it as an array of CallInfo.
func GatherCallDataForFrame(prof *ProfileData, frameNum int) []CallInfo {
	r := prof.GetCallRangeForFrame(frameNum)
	var start = r.firstIndex
	var end = r.lastIndex
	var numCalls = end - start + 1
	callData := make([]CallInfo, numCalls)
	for i := 0; i < numCalls; i++ {
		callData[i] = prof.GetCallDataByIndex(i + start)
	}

	return callData
}

// GatherFrameTiming returns the total GPU and CPU time spent in the given frame.
func GatherFrameTiming(
	prof *ProfileData, frameNum int, callNameRegEx string) (totalGPUTimeNs int, totalCPUTimeNs int) {
	r := prof.GetCallRangeForFrame(frameNum)
	if callNameRegEx == "" || callNameRegEx == "*" {
		for i := r.firstIndex; i <= r.lastIndex; i++ {
			call := prof.GetCallRecordByIndex(i)
			totalGPUTimeNs += call.gpuDurationNs
			totalCPUTimeNs += call.cpuDurationNs
		}
	} else {
		var re *regexp.Regexp
		var err error
		if re, err = regexp.Compile(callNameRegEx); err != nil {
			return
		}

		for i := r.firstIndex; i <= r.lastIndex; i++ {
			call := prof.GetCallRecordByIndex(i)
			callName := prof.GetCallDataByIndex(i).callName
			if re.MatchString(callName) {
				totalGPUTimeNs += call.gpuDurationNs
				totalCPUTimeNs += call.cpuDurationNs
			}
		}
	}
	return
}

// GatherTimingForAllFrames returns the timing information for all the frames
// in the profile. Timing info includes the total GPU and CPU time in each
// frame.
func GatherTimingForAllFrames(prof *ProfileData, callNameRegEx string) (timing []FrameTiming) {
	numCoroutines := runtime.NumCPU()
	timing = make([]FrameTiming, prof.GetFrameCount())
	limiter := make(chan int, numCoroutines)

	for f := 0; f < prof.GetFrameCount(); f++ {
		limiter <- 1
		go func(f int) {
			r := prof.GetCallRangeForFrame(f)
			gpuNs, cpuNs := GatherFrameTiming(prof, f, callNameRegEx)
			timing[f].frameNum = f
			timing[f].gpuTimeNs += gpuNs
			timing[f].cpuTimeNs += cpuNs
			timing[f].callCount = r.lastIndex - r.firstIndex + 1
			<-limiter
		}(f)
	}

	return
}
