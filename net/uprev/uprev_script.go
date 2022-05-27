// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package main

import (
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"time"
)

var colorGreen = "\033[32m"
var colorReset = "\033[0m"

func logFatal(s string) {
	fmt.Print(s)
	log.Fatal(s)
}

func runCmd(cmd *exec.Cmd, abortOnFail bool) (string, error) {
	fmt.Printf("Executing: %q\n", cmd.String())
	log.Printf("Executing: %q\n", cmd.String())
	out, err := cmd.CombinedOutput()
	if err != nil {
		log.Printf("err: %q\n", err)
		if abortOnFail {
			logFatal(err.Error())
		}
		log.Printf("Ignoring non-fatal error")
	}
	log.Printf("Execution result: %s\n", string(out))
	return string(out), nil
}

// returns gerrit cl, conflicting commit on error, error
func uprevRepo(rootDir string, repoName string, upstreamBranch string, cqDepend string, lastUpstreamCommitToMerge string, uploadFlag bool, forceFlag bool) (string, string, error) {
	uprevDate := time.Now().Format("01-02-2006")
	branchName := "merge-upstream-" + uprevDate
	fmt.Println(rootDir, repoName, upstreamBranch, uprevDate)
	if err := os.Chdir(rootDir + repoName); err != nil {
		logFatal(err.Error())
	}
	newDir, _ := os.Getwd()
	fmt.Printf(colorGreen+"Working on : %s\n"+colorReset, newDir)
	var cmd *exec.Cmd

	cmd = exec.Command("git", "status", "--porcelain")
	gitStatus, _ := runCmd(cmd, true)
	if gitStatus != "" && !forceFlag {
		logFatal("Please ensure that there are no uncommitted changes. Or run with --force=true")
	}
	if gitStatus != "" {
		cmd = exec.Command("git", "stash", "cros/master")
		runCmd(cmd, false)
	}

	// Repo start a clean branch with HEAD cros/master and merge cros/upstream
	cmd = exec.Command("git", "checkout", "cros/master")
	runCmd(cmd, !forceFlag)
	cmd = exec.Command("git", "reset", "--hard", "cros/master")
	runCmd(cmd, true)
	cmd = exec.Command("git", "branch", "-D", branchName)
	runCmd(cmd, false)
	cmd = exec.Command("rm", "-r", "-f", ".git/refs/imerge")
	runCmd(cmd, false)
	cmd = exec.Command("rm", "-r", "-f", "/tmp/imerge-"+repoName)
	runCmd(cmd, false)
	cmd = exec.Command("repo", "sync", ".")
	runCmd(cmd, true)
	cmd = exec.Command("repo", "start", branchName)
	runCmd(cmd, true)
	cmd = exec.Command("git", "checkout", "cros/master")
	runCmd(cmd, true)
	cmd = exec.Command("git", "fetch", "cros", upstreamBranch)
	runCmd(cmd, true)

	// Try to merge top of cros/upstream unless specified otherwise.
	mergeTarget := ""
	if lastUpstreamCommitToMerge == "" {
		mergeTarget = "cros/" + upstreamBranch
	} else {
		mergeTarget = lastUpstreamCommitToMerge + "~1"
	}

	// git imerge performs an incremental merge. It merges one upstream commit at a time to figure out the conflicting commit.
	cmd = exec.Command("git", "imerge", "start", "--name="+branchName, "--branch="+branchName, "--goal=merge", mergeTarget)
	imergeResult, _ := runCmd(cmd, false)

	if strings.Contains(imergeResult, "There are no commits") {
		return "", "", nil
	}

	if _, err := os.Stat(".git/MERGE_HEAD"); errors.Is(err, os.ErrNotExist) {
		// merge was successful
		cmd = exec.Command("git", "imerge", "finish")
		cmd.Stdin = strings.NewReader("\r\r\r\r:q")
		runCmd(cmd, false) // the finish will fail because we cannot open an editor, but continue nevertheless
		cmd = exec.Command("rm", "-r", "-f", ".git/refs/imerge")
		runCmd(cmd, false)
		lastCommitMerged := ""
		if lastUpstreamCommitToMerge == "" {
			lastCommitMerged = "cros/" + upstreamBranch
		} else {
			lastCommitMerged = lastUpstreamCommitToMerge + "~1"
		}

		cmd = exec.Command("git", "log", "cros/master.."+lastCommitMerged, "--abbrev", "--oneline", "--format=\"%C(auto) %h %s (%an)\"")
		out, _ := runCmd(cmd, false)
		commitMsg := "Merge cros/upstream to cros/master\n\nContains the following commits:\n\n" + out + "\n\nBUG=None\nTEST=None"
		if cqDepend != "" {
			commitMsg = commitMsg + "\n\nCq-Depend: " + cqDepend
		}
		if err := os.WriteFile("/tmp/imerge-commits.log", []byte(commitMsg), 0644); err != nil {
			logFatal("Cannot write commits.log")
		}
		cmd = exec.Command("git", "commit", "--amend", "-F", "/tmp/imerge-commits.log")
		runCmd(cmd, true)
		// imerge sets upstream to cros/upstream. We want to upload changes to gerrit
		cmd = exec.Command("git", "branch", "--set-upstream-to", "cros/master")
		runCmd(cmd, true)

		if !uploadFlag {
			return "", "", nil
		}
		cmd = exec.Command("repo", "upload", "--cbr", ".", "--no-verify", "-o", "topic="+branchName, "-y")
		cmd.Stdin = strings.NewReader("yes")
		out, err = runCmd(cmd, true)
		re := regexp.MustCompile(`\+/(.*) Merge`)
		res := re.FindStringSubmatch(out)
		fmt.Printf("%sUploaded chromium:%s\n%s", colorGreen, res[1], colorReset)
		return "chromium:" + res[1] + " ", "", nil
	}

	re := regexp.MustCompile(`commit (.{40})`)
	res := re.FindAllStringSubmatch(imergeResult, -1)
	fmt.Printf("Merge conflict found. Email at /tmp/imerge-conflict.email")
	imergeResult = "Please cherry pick " + res[1][1] + "\n\n\n\n Details:\n\n" + imergeResult
	if err := os.WriteFile("/tmp/imerge-conflict.email", []byte(strings.Split(imergeResult, "Attempting automerge")[0]), 0644); err != nil {
		logFatal("Could not write conflict email")
	}
	// return conflicting commit
	return "", res[1][1], errors.New("Conflict found")
}

func postUprevChecks(cl string, err error, cqP1Flag bool) {
	if err != nil {
		os.Exit(1)
	}
	if cl == "" || !cqP1Flag {
		return
	}
	cl = strings.TrimRight(strings.Split(cl, "chromium:")[1], " ") // Convert chromium: 12345 -> 12345
	runCmd(exec.Command("gerrit", "label-v", cl, "1"), false)
	runCmd(exec.Command("gerrit", "label-cq", cl, "1"), false)
}

func main() {
	file, err := os.OpenFile("/tmp/uprev.log", os.O_CREATE|os.O_WRONLY, 0666)
	if err != nil {
		logFatal(err.Error())
	}
	log.SetOutput(file)
	defer fmt.Println("Uprev logs in /tmp/uprev.log")

	homeDir, _ := os.UserHomeDir()
	_, err = os.Stat(homeDir + "/git-imerge/")
	if os.IsNotExist(err) {
		logFatal("~/git-imerge does not exist. Please run \n  cd ~ && git clone https://github.com/mhagger/git-imerge.git && cd git-imerge && git checkout 9bde208 && sudo python setup.py install")
	}

	uploadFlag := flag.Bool("upload", true, "upload to gerrit")
	cqP1Flag := flag.Bool("cq", true, "V+1, CQ+1 on gerrit")
	forceFlag := flag.Bool("force", false, "force a reset to cros/master. You will lose all changes on the current branch. Prefer stashing your changes instead")
	flag.Parse()

	rootDir := homeDir + "/chromiumos/src/third_party/"

	libqrtrCl, _, err := uprevRepo(rootDir, "libqrtr-glib", "upstream/main", "", "", *uploadFlag, *forceFlag)
	postUprevChecks(libqrtrCl, err, *cqP1Flag)
	libqmiCl, _, err := uprevRepo(rootDir, "libqmi", "upstream", "", "", *uploadFlag, *forceFlag)
	postUprevChecks(libqmiCl, err, *cqP1Flag)

	libmbimCl, _, err := uprevRepo(rootDir, "libmbim", "upstream", "", "", *uploadFlag, *forceFlag)
	postUprevChecks(libmbimCl, err, *cqP1Flag)

	// Attempt MM uprev to cros/upstream. If MM uprev fails, merge last conflict free commit.
	mmCl, conflictCommit, err := uprevRepo(rootDir, "modemmanager-next", "upstream", libqrtrCl+libqmiCl+libmbimCl, "", *uploadFlag, *forceFlag)
	if err == nil {
		runCmd(exec.Command("rm", "/tmp/imerge*"), false)
	}
	if conflictCommit != "" {
		mmCl, conflictCommit, err = uprevRepo(rootDir, "modemmanager-next", "upstream", libqrtrCl+libqmiCl+libmbimCl, conflictCommit, *uploadFlag, *forceFlag)
	}
	postUprevChecks(mmCl, err, *cqP1Flag)
}
