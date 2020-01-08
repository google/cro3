// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyze

import (
	"fmt"
)

// CallRecord encapsulates the data associated with each api call.
// Note: apitrace numbers each GL-api call sequentially. That number is called
// the call num.
type CallRecord struct {
	callNum       int // The call number for this data.
	frameNum      int // The number of the frame that invokes this call.
	gpuDurationNs int // Gpu duration of this call in nanoseconds.
	cpuDurationNs int // Cpu duration of this call in nanoseconds.
}

// CallRange tracks a range of calls by first and last indices.
type CallRange struct {
	firstIndex int
	lastIndex  int // Inclusive
}

// CallNumData contains basic call info associated with each call num.
type CallNumData struct {
	programID int    // ID of program that uses this call.
	callName  string // The api call name, e.g. glBegin.
}

// CallInfo all the info associated with a given call.
type CallInfo struct {
	CallNumData
	CallRecord
}

// ProfileData implements interface ProfileDataConsumer. It is used to collect
// the profile data gathered while reading a file and store that data in a
// format that makes analyzing it easier.
type ProfileData struct {
	// A label for this profile data.
	label string

	// Current frame number while accumulating profile data.
	frameNum int

	// Array of all GL-api calls stored in this profile.
	allCalls []CallRecord

	// Keep track of basic call info for each call num.
	callsByCallNum map[int](CallNumData)

	// Maps call name, such as glDrawRangeElements, to a list of all the
	// call-record indices that invoke that function.
	callsByCallName map[string]([]int)

	// Maps a frame number to a range of call indices that belong to that frame.
	callsByFrameNum []CallRange

	// Current accumulated CPU and GPU time in nanoseconds
	sumGPUTimeNs float64
	sumCPUTimeNs float64
}

// Filter function: takes calldata and return true if accepted by the filter.
// These filter functions are used by some of the traverse methods provided by
// ProfileData.
type Filter func(callData CallInfo) bool

// CallNameData encapsulates a call name and the list of all call indices
// that invoke that call-name function.
type CallNameData struct {
	callName    string
	callIndices []int
}

// StartNewProfile starts gathering a new profile. Any existing data in prof
// is cleared.
func (prof *ProfileData) StartNewProfile(label string) {
	prof.label = label
	prof.allCalls = make([]CallRecord, 0, 10000)
	prof.callsByCallNum = map[int](CallNumData){}
	prof.callsByCallName = map[string]([]int){}
	prof.callsByFrameNum = make([]CallRange, 0, 2000)
}

// EndFrame ends the current frame. Any data added after this call will be
// associated with the next sequential frame.
func (prof *ProfileData) EndFrame() {
	prof.frameNum++
}

// AddCallData adds profile info for the given call number to the profile data.
func (prof *ProfileData) AddCallData(callNum int, gpuDurationNs int,
	cpuDurationNs int, programID int, callName string) error {

	// Usually, call numbers are unique and monotonically increasing. However,
	// when a profile is generated with the last frame repeated several time
	// (--loop option in glretrace), duplicate call numbers are present. The
	// duplicate call numbers must always have the same call name and program ID.
	if existingData, isDuplicate := prof.callsByCallNum[callNum]; isDuplicate {
		if existingData.callName != callName {
			return fmt.Errorf(
				"ERROR: Duplicate call ID <%d> with mismatched call name %s v.s. %s",
				callNum, callName, existingData.callName)
		}
		if existingData.programID != programID {
			return fmt.Errorf(
				"ERROR: Duplicate call ID <%d> with mismatched program ID %d v.s. %d",
				callNum, programID, existingData.programID)
		}
	} else {
		prof.callsByCallNum[callNum] = CallNumData{programID, callName}
	}

	// Add the call info to the list of all calls.
	var callIndex = len(prof.allCalls)
	prof.allCalls = append(prof.allCalls,
		CallRecord{callNum, prof.frameNum, gpuDurationNs, cpuDurationNs})

	// Add the index for this call record to this call name.
	var callList = prof.callsByCallName[callName]
	prof.callsByCallName[callName] = append(callList, callIndex)

	if len(prof.callsByFrameNum) == prof.frameNum {
		// This is a new frame; create a new call range for it.
		prof.callsByFrameNum = append(prof.callsByFrameNum, CallRange{callIndex, callIndex})
	} else {
		// Expend the call range for the current frame to include this new call index.
		prof.callsByFrameNum[prof.frameNum].lastIndex = callIndex
	}

	// Accumulate total CPU and GPU time in nanoseconds.
	prof.sumCPUTimeNs += float64(cpuDurationNs)
	prof.sumGPUTimeNs += float64(gpuDurationNs)

	return nil
}

// GetFrameCount returns the number of frames in this profile.
func (prof *ProfileData) GetFrameCount() int {
	return prof.frameNum
}

// GetCallCount returns the total number of calls in this profile.
func (prof *ProfileData) GetCallCount() int {
	return len(prof.allCalls)
}

// GetTotalGPUTimeNs returns the accumulated time spent in the GPU in
// nanoseconds.
func (prof *ProfileData) GetTotalGPUTimeNs() float64 {
	return prof.sumGPUTimeNs
}

// GetTotalCPUTimeNs returns the accumulated time spent in the CPU in
// nanoseconds.
func (prof *ProfileData) GetTotalCPUTimeNs() float64 {
	return prof.sumCPUTimeNs
}

// GetCallDataByIndex returns the profile data for the call with the given
// call index.
func (prof *ProfileData) GetCallDataByIndex(index int) CallInfo {
	var callNum = prof.allCalls[index].callNum
	return CallInfo{prof.callsByCallNum[callNum], prof.allCalls[index]}
}

// GetCallRecordByIndex returns the call record for the given call index.
func (prof *ProfileData) GetCallRecordByIndex(index int) CallRecord {
	return prof.allCalls[index]
}

// GetCallIndicesForName returns a list of all the call indices that use the
// given call name.
func (prof *ProfileData) GetCallIndicesForName(name string) []int {
	return prof.callsByCallName[name]
}

// GetCallRangeForFrame returns the range of call indices called in the
// given frame.
func (prof *ProfileData) GetCallRangeForFrame(frameNum int) CallRange {
	if frameNum >= 0 && frameNum < len(prof.callsByFrameNum) {
		return prof.callsByFrameNum[frameNum]
	}
	return CallRange{0, 0}
}

// VerifyCallNum returns whether call callNum invokes api with callName.
// If callNum is not in this profile, then this function also returns true.
func (prof *ProfileData) VerifyCallNum(callNum int, callName string) bool {
	if call, ok := prof.callsByCallNum[callNum]; ok {
		return callName == call.callName
	}
	return true
}

// TraverseAllCalls traverses all the available profile data sequentially and
// feeds the call indices for the calls that are accepted by <filter> to channel c.
func (prof *ProfileData) TraverseAllCalls(filter Filter, c chan int) {
	for callIndex, callRecord := range prof.allCalls {
		if filter(CallInfo{prof.callsByCallNum[callRecord.callNum], callRecord}) {
			c <- callIndex
		}
	}
	close(c)
}

// TraverseByCallName traverses all the available profile data and feeds each
// call indices and associated call name to channel c.
func (prof *ProfileData) TraverseByCallName(c chan CallNameData) {
	for name, callIndices := range prof.callsByCallName {
		c <- CallNameData{name, callIndices}
	}
	close(c)
}

// TraverseCallsForFrame feeds the call info to the given channel for all the
// calls in frame <frameNum>.
func (prof *ProfileData) TraverseCallsForFrame(c chan CallInfo, frameNum int) {
	r := prof.GetCallRangeForFrame(frameNum)
	for i := r.firstIndex; i <= r.lastIndex; i++ {
		c <- prof.GetCallDataByIndex(i)
	}
	close(c)
}
