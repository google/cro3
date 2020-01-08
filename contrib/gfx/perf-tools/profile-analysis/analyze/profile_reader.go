// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyze

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// ProfileDataConsumer defines the interface that takes profile data from
// ProfileReader.
type ProfileDataConsumer interface {
	StartNewProfile(label string)
	EndFrame()
	AddCallData(callNum int, gpuDurationNs int, cpuDurationNs int,
		programID int, callName string) error
}

// ProfileReader reads apitrace profile data from a file, parses it and feeds
// the profile data to a ProfileDataConsumer.
type ProfileReader struct {
	// Full path name to the profile data file.
	filename string

	// Consumes the profile data produced by the reader.
	consumer ProfileDataConsumer

	// Column indices for the various profile data items in each line of data.
	idxColumnCallID      int
	idxColumnGPUDuration int
	idxColumnCPUDuration int
	idxColumnProgramID   int
	idxColumnCallName    int
	idxMax               int
}

// ReadProfile opens the profile data file, parses it line by line and feeds
// the profile data to the consumer.
func (reader *ProfileReader) ReadProfile(
	filename string, consumer ProfileDataConsumer) (err error) {

	var file *os.File
	if file, err = os.Open(filename); err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: Unable to open file <%s>!\n", filename)
		return
	}
	defer file.Close()

	reader.filename = filepath.Base(file.Name())
	reader.consumer = consumer

	var bufSize = 64 * 1024
	var buffer = make([]byte, bufSize)
	var scanner = bufio.NewScanner(file)
	scanner.Buffer(buffer, bufSize)

	if err = reader.parseHeader(scanner); err != nil {
		return
	}

	return reader.parseProfileData(scanner)
}

// Read the first, header line from the profile and extract the column indices
// for the columns we are interested in.
// Sample header from profile:
// # call no gpu_start gpu_dura cpu_start cpu_dura vsize_start vsize_dura \
//        rss_start rss_dura pixels program name
func (reader *ProfileReader) parseHeader(scanner *bufio.Scanner) (err error) {
	if !scanner.Scan() {
		return fmt.Errorf("ERROR: No header in profile <%s>", reader.filename)
	}

	var columns = strings.Split(strings.TrimLeft(scanner.Text()[1:], " "), " ")
	for idx, columnName := range columns {
		switch columnName {
		case "no":
			reader.idxColumnCallID = idx
		case "gpu_dura":
			reader.idxColumnGPUDuration = idx
		case "cpu_dura":
			reader.idxColumnCPUDuration = idx
		case "program":
			reader.idxColumnProgramID = idx
		case "name":
			reader.idxColumnCallName = idx
		case "call", "gpu_start", "cpu_start", "vsize_start", "vsize_dura",
			"rss_start", "rss_dura", "pixels":
			// Ignore those columns.
			continue
		default:
			err = fmt.Errorf("Error: unexpected column name in profile: %s", columnName)
			return
		}
		if idx > reader.idxMax {
			reader.idxMax = idx
		}
	}

	reader.consumer.StartNewProfile(reader.filename)
	return nil
}

// Parse all the profile lines that follow the header and feed the profile
// data to reader.consumer.
func (reader *ProfileReader) parseProfileData(scanner *bufio.Scanner) (err error) {
	// Asynchronously read lines from the input file and feed them to the lines
	// channel.
	var lines = make(chan string, 32)
	go func() {
		for scanner.Scan() {
			lines <- scanner.Text()
		}
		close(lines)
	}()

	var frameOpen = false
	for line := range lines {
		switch {
		case strings.HasPrefix(line, "Rendered"):
			// Ignore last line in file.
			continue
		case strings.HasPrefix(line, "#"):
			// Skip comment lines.
			continue
		case line == "frame_end":
			reader.consumer.EndFrame()
			frameOpen = false
		case strings.HasPrefix(line, "call "):
			err = reader.parseCallLine(line)
			if err != nil {
				fmt.Println(err)
				return
			}
			frameOpen = true
		default:
			err = fmt.Errorf("Error: unrecognized line in profile: %s", line)
			return
		}
	}

	// Ensure the last frame is ended.
	if frameOpen {
		reader.consumer.EndFrame()
	}

	err = scanner.Err()
	return
}

// Parse a single call line and feed the profile data to reader.consumer.
// Sample call line from profile:
// call 354 635667360 3680 594454016 59840 0 0 0 0 0 0 glClear
func (reader *ProfileReader) parseCallLine(line string) (err error) {
	var callID, gpuDuration, cpuDuration, programID int
	var tokens = strings.Split(strings.TrimRight(line, "\r\n"), " ")

	// Ensure that the number of tokens match or exceeds the column indices.
	if len(tokens) <= reader.idxMax {
		return fmt.Errorf("Error: not enough columns in call line: %s: ", line)
	}

	if callID, err = strconv.Atoi(tokens[reader.idxColumnCallID]); err != nil {
		return err
	}
	if gpuDuration, err = strconv.Atoi(tokens[reader.idxColumnGPUDuration]); err != nil {
		return err
	}
	if cpuDuration, err = strconv.Atoi(tokens[reader.idxColumnCPUDuration]); err != nil {
		return err
	}
	if programID, err = strconv.Atoi(tokens[reader.idxColumnProgramID]); err != nil {
		return err
	}

	err = reader.consumer.AddCallData(
		callID, gpuDuration, cpuDuration, programID, tokens[reader.idxColumnCallName])
	return
}
