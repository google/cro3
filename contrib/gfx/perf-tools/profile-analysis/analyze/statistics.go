// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyze

import (
	"math"
)

// Statistics stores sum, simple average, min, max and standard-deviation info
// and provides convenience methods to gather and calculate these values.
type Statistics struct {
	sum               float64
	min               float64
	max               float64
	averageAtN        float64
	averageAtNminus1  float64
	varianceAtN       float64
	varianceAtNminus1 float64
	numSamples        int
}

// DualStatistics is a generic interface that embeds the dual notion of
// GPU and CPU statistics and method to access them.
type DualStatistics interface {
	gpuStats() *Statistics
	cpuStats() *Statistics
}

// CallNameStatistics has GPU and CPU statistics associated with a specific call
// name. E.g. GPU and CPU timing statistics for function glDrawRangeElements.
type CallNameStatistics struct {
	callName string
	gpuStat  Statistics
	cpuStat  Statistics
}

// CompareStats encapsulates the ratio and difference of GPU and CPU averages.
type CompareStats struct {
	gpuAvgRatio float64
	cpuAvgRatio float64
	gpuAvgDiff  float64
	cpuAvgDiff  float64
}

// FrameTiming encapsulates a frame number with the number of api calls that
// take place within that frame and the total GPU and CPU time spent in those
// calls.
type FrameTiming struct {
	frameNum  int
	callCount int
	gpuTimeNs int
	cpuTimeNs int
}

// AddSample adds a sample value to the Statistics object.
func (stat *Statistics) AddSample(s float64) {
	stat.numSamples++

	// Numerically stable running mean and variance, per Donald Knuth’s Art of
	// Computer Programming, Vol 2.
	if stat.numSamples == 1 {
		stat.sum = s
		stat.max = s
		stat.min = s
		stat.averageAtN = s
		stat.varianceAtN = 0
	} else {
		stat.max = math.Max(stat.max, s)
		stat.min = math.Min(stat.min, s)
		stat.sum += s
		stat.averageAtN = stat.averageAtNminus1 + (s-stat.averageAtNminus1)/float64(stat.numSamples)
		stat.varianceAtN = stat.varianceAtNminus1 + (s-stat.averageAtNminus1)*(s-stat.averageAtN)
	}

	stat.averageAtNminus1 = stat.averageAtN
	stat.varianceAtNminus1 = stat.varianceAtN
}

// GetNumSamples returns the number of samples accumulated so far.
func (stat *Statistics) GetNumSamples() int {
	return stat.numSamples
}

// GetSum returns the sum of all samples added so far.
func (stat *Statistics) GetSum() float64 {
	return stat.sum
}

// GetMax returns the maximum of all samples added so far.
func (stat *Statistics) GetMax() float64 {
	return stat.max
}

// GetMin returns the minimum of all samples added so far.
func (stat *Statistics) GetMin() float64 {
	return stat.min
}

// GetAverage returns the average of all samples added so far.
func (stat *Statistics) GetAverage() float64 {
	return stat.averageAtN
}

// GetStdDeviation returns the standard deviation of all samples added so far.
func (stat *Statistics) GetStdDeviation() float64 {
	if stat.numSamples <= 1 {
		return 0
	}
	return math.Sqrt(stat.varianceAtN / float64(stat.numSamples-1))
}

// Implement interface DualStatistics on CallNameStatistics.
func (ds CallNameStatistics) gpuStats() *Statistics {
	return &ds.gpuStat
}

// Implement interface DualStatistics on CallNameStatistics.
func (ds CallNameStatistics) cpuStats() *Statistics {
	return &ds.cpuStat
}

// A sort-compare function for sorting DualStatistics samples by decreasing
// average GPU time.
func sortByDecGPUAvg(dsi DualStatistics, dsj DualStatistics) bool {
	return dsi.gpuStats().averageAtN > dsj.gpuStats().averageAtN
}

// A sort-compare function for sorting DualStatistics samples by decreasing
// average CPU time.
func sortByDecCPUAvg(dsi DualStatistics, dsj DualStatistics) bool {
	return dsi.cpuStats().averageAtN > dsj.cpuStats().averageAtN
}
