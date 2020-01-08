// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"./analyze"
	"flag"
	"fmt"
	"os"
)

type profileData = analyze.ProfileData
type profileReader = analyze.ProfileReader
type console = analyze.Console

func printUsage() {
	fmt.Fprintf(os.Stderr, "\nUsage: %s [options] profile1 [profile2]\n", os.Args[0])
	fmt.Fprintf(os.Stderr,
		"where profile1 and optional profile2 are profile data files generated\n"+
			"with 'glretrace' using the same input trace file.\n\n"+
			"Available options:\n")
	flag.PrintDefaults()
	os.Exit(2)
}

func readProfile(filename string, readDone chan bool) (*profileData, error) {
	var profData *profileData = nil
	var err error = nil

	if filename != "" {
		var reader = new(profileReader)
		fmt.Fprintf(os.Stdout, "Reading %s.... \n", filename)
		profData = new(profileData)

		if err = reader.ReadProfile(filename, profData); err == nil {
			fmt.Printf("%d frames read from %s\n", profData.GetFrameCount(), filename)
		}
	}

	readDone <- true
	return profData, err
}

func readProfileOrExitOnFailure(filename string, readDone chan bool) *profileData {
	var err error = nil
	var profData *profileData = nil
	if profData, err = readProfile(filename, readDone); err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err.Error())
		os.Exit(1)
	}

	return profData
}

func exitIfFileMissing(filepath string) {
	if _, err := os.Stat(filepath); err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: Could not open <%s>\n", filepath)
		os.Exit(1)
	}
}

func main() {
	// Parsing the cmd-line arguments.
	var argShowHelp bool
	flag.BoolVar(&argShowHelp, "help", false, "Show this help message")
	flag.Usage = printUsage
	flag.Parse()

	if argShowHelp {
		printUsage()
	}

	// Validate the input files. Profile 1 is needed, profile 2 is optional.
	if len(flag.Args()) == 0 {
		fmt.Fprintf(os.Stderr, "ERROR: You must profile at least one profile\n")
		printUsage()
	}
	var argProfileFile1 = flag.Args()[0]
	var argProfileFile2 string
	if len(flag.Args()) > 1 {
		argProfileFile2 = flag.Args()[1]
		exitIfFileMissing(argProfileFile2)
	}

	exitIfFileMissing(argProfileFile1)

	// Read and parse profiles.
	var waitReadDone = make(chan bool, 2)
	var profData1 *profileData = nil
	var profData2 *profileData = nil
	go func() {
		profData1 = readProfileOrExitOnFailure(argProfileFile1, waitReadDone)
	}()
	go func() {
		profData2 = readProfileOrExitOnFailure(argProfileFile2, waitReadDone)
	}()

	for i := 0; i < 2; i++ {
		<-waitReadDone
	}

	// If we have two profiles, verify that they are equivalent.
	if profData2 != nil {
		fmt.Printf("Verifying profile compatibility....")
		if !analyze.CheckProfileEquivalence(profData1, profData2) {
			fmt.Fprintln(os.Stderr,
				"ERROR: these two profiles do not appear to be from the same trace.")
			os.Exit(1)
		}
	}

	cons := new(console)
	cons.StartInteractive(profData1, profData2)
}
