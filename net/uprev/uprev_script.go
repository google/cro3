// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package main

import (
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
var colorRed = "\033[31m"
var colorReset = "\033[0m"

func logPanic(s string) {
	fmt.Print(s)
	log.Panicln(s)
}

func runCmd(cmd *exec.Cmd, abortOnFail bool) (string, error) {
	fmt.Printf("Executing: %q\n", cmd.String())
	log.Printf("Executing: %q\n", cmd.String())
	out, err := cmd.CombinedOutput()
	if err != nil {
		log.Printf("err: %q\n", err)
		if abortOnFail {
			logPanic(err.Error())
		}
		log.Printf("Ignoring non-fatal error")
	}
	log.Printf("Execution result: %s\n", string(out))
	return string(out), err
}

// mergeUntilConflict merges the last non conflicting merge from the upstream branch
func MergeUntilConflict(upstreamBranch string) (string, error) {
	cmd := exec.Command("git", "log", "HEAD.."+upstreamBranch, "--abbrev", "--oneline", "--format=%h")
	out, _ := runCmd(cmd, true)
	if out == "" {
		return "", nil
	}

	commits := strings.Split(out, "\n")
	// The first element of this array is the most recent commit, and we're going backwards in time until we find one that merges cleanly
	for i, commitSHA := range commits[:len(commits)-1] {
		cmd := exec.Command("git", "merge", commitSHA)
		_, e := runCmd(cmd, false)
		if e != nil {
			cmd := exec.Command("git", "merge", "--abort")
			if _, err := runCmd(cmd, false); err != nil {
				return "", fmt.Errorf("Could not abort merge: %w", e)
			}
		} else {
			if i != 0 {
				fmt.Println(colorRed, "Could not merge cros/upstream fully. Merged only until commit: ", commitSHA, colorReset)
				fmt.Println(colorRed, "Warning: CQ does not support merge commits stacked on top of other commits. Your next commit needs to be a merge of ", commitSHA, "without any commits in between.", colorReset)
			} else {
				fmt.Println(colorGreen, "Merged ", upstreamBranch, colorReset)
			}
			return fmt.Sprintf(commitSHA), nil
		}
	}
	fmt.Println(colorRed, "Could not merge any commit in cros/upstream", colorReset)
	return "", nil
}

// returns gerrit cl, cleanup function
func uprevRepo(rootDir string, repoName string, upstreamBranch string, cqDepend string, uploadFlag bool, compileFlag bool, forceFlag bool, cqP1Flag bool) (string, func()) {
	cleanupFunc := func() {}
	uprevDate := time.Now().Format("01-02-2006")
	branchName := "merge-upstream-" + uprevDate
	fmt.Println(rootDir, repoName, upstreamBranch, uprevDate)
	if err := os.Chdir(rootDir + repoName); err != nil {
		logPanic(err.Error())
	}
	newDir, _ := os.Getwd()
	fmt.Printf(colorGreen+"Working on : %s\n"+colorReset, newDir)
	var cmd *exec.Cmd

	cmd = exec.Command("git", "status", "--porcelain")
	gitStatus, _ := runCmd(cmd, true)
	if gitStatus != "" {
		if forceFlag {
			cmd = exec.Command("git", "stash", "--include-untracked")
			runCmd(cmd, false)
		} else {
			logPanic("Please ensure that there are no uncommitted changes. Or run with --force=true")
		}
	}

	// Repo start a clean branch with HEAD cros/master and merge cros/upstream
	cmd = exec.Command("git", "checkout", "cros/master")
	runCmd(cmd, !forceFlag)
	cmd = exec.Command("git", "reset", "--hard", "cros/master")
	runCmd(cmd, true)
	if forceFlag {
		cmd = exec.Command("git", "branch", "-D", branchName)
	}
	runCmd(cmd, false)
	cmd = exec.Command("repo", "sync", ".")
	runCmd(cmd, true)
	cmd = exec.Command("repo", "start", branchName)
	runCmd(cmd, true)
	cmd = exec.Command("git", "fetch", "cros", upstreamBranch)
	runCmd(cmd, true)
	commitSHA, err := MergeUntilConflict("cros/" + upstreamBranch)
	if err != nil {
		logPanic(fmt.Errorf("Could not merge: %w", err).Error())
	}
	if commitSHA == "" {
		fmt.Println(colorGreen, repoName, " is already up to date", colorReset)
		return "", cleanupFunc
	}

	cmd = exec.Command("git", "log", "cros/master.."+commitSHA, "--abbrev", "--oneline", "--format=\"%C(auto) %h %s (%an)\"")
	out, _ := runCmd(cmd, false)
	commitMsg := "Merge cros/" + upstreamBranch + " to cros/master\n\nContains the following commits:\n\n" + out + "\n\nBUG=None\nTEST=None"
	if cqDepend != "" {
		commitMsg = commitMsg + "\n\nCq-Depend: " + cqDepend
	}
	if err := os.WriteFile("/tmp/commit-msg.log", []byte(commitMsg), 0644); err != nil {
		logPanic("Cannot write commits.log")
	}
	cmd = exec.Command("git", "commit", "--amend", "-F", "/tmp/commit-msg.log")
	runCmd(cmd, true)

	if compileFlag {
		cmd = exec.Command("cros_workon", "--board=trogdor", "start", repoName)
		cmd = exec.Command("cros_workon", "--board=dedede", "start", repoName)
		runCmd(cmd, true)
		cleanupFunc = func() {
			cmd = exec.Command("cros_workon", "--board=trogdor", "stop", repoName)
			runCmd(cmd, false)
			cmd = exec.Command("cros_workon", "--board=dedede", "stop", repoName)
			runCmd(cmd, false)
		}
		cmd = exec.Command("emerge-trogdor", repoName)
		runCmd(cmd, true)
		cmd = exec.Command("emerge-dedede", repoName)
		runCmd(cmd, true)
	}

	if !uploadFlag {
		return "", cleanupFunc
	}
	cmd = exec.Command("repo", "upload", "--cbr", ".", "--no-verify", "-o", "topic="+branchName, "-y")
	cmd.Stdin = strings.NewReader("yes")
	out, err = runCmd(cmd, true)
	re := regexp.MustCompile(`\+/(.*) Merge`)
	res := re.FindStringSubmatch(out)
	fmt.Printf("%sUploaded crrev.com/c/%s\n%s", colorGreen, res[1], colorReset)

	if cqP1Flag {
		runCmd(exec.Command("gerrit", "label-v", res[1], "1"), false)
		runCmd(exec.Command("gerrit", "label-cq", res[1], "1"), false)
	}

	return "chromium:" + res[1] + " ", cleanupFunc
}

func main() {
	file, err := os.OpenFile("/tmp/uprev.log", os.O_CREATE|os.O_WRONLY, 0666)
	if err != nil {
		logPanic(err.Error())
	}
	log.SetOutput(file)
	defer fmt.Println("Uprev logs in /tmp/uprev.log")

	uploadFlag := flag.Bool("upload", true, "upload to gerrit")
	cqP1Flag := flag.Bool("cq", true, "V+1, CQ+1 on gerrit")
	forceFlag := flag.Bool("force", false, "force a reset to cros/master. You will lose all changes on the current branch. Prefer stashing your changes instead")
	compileFlag := flag.Bool("compile", false, "Compile on trogdor and dedede boards")
	skipSetupBoardForCompileFlag := flag.Bool("skip-setup-board-for-compile", false, "If --compile is true, skip executing setup_board. You will have to ensure that it's already been run before.")
	mergeUntilConflictFlag := flag.Bool("merge-until-conflict", false, "Merge the last non conflicting commit between current branch and merge-until-conflict-branch.")
	mergeUntilConflictBranchFlag := flag.String("merge-until-conflict-branch", "cros/upstream", "Upstream branch to merge when merge-until-conflict is set")
	flag.Parse()

	if *mergeUntilConflictFlag {
		commitSHA, err := MergeUntilConflict(*mergeUntilConflictBranchFlag)
		if err != nil {
			logPanic(err.Error())
			return
		}
		fmt.Println(commitSHA, "is the last commit that can be merged without conflicts")
		return
	}

	if *compileFlag && !*skipSetupBoardForCompileFlag {
		cmd := exec.Command("setup_board", "--board=trogdor")
		runCmd(cmd, true)
		cmd = exec.Command("setup_board", "--board=dedede")
		runCmd(cmd, true)
	}

	homeDir, _ := os.UserHomeDir()
	rootDir := homeDir + "/chromiumos/src/third_party/"
	cqDepend := ""
	libqrtrCl, cleanupLibqrtr := uprevRepo(rootDir, "libqrtr-glib", "upstream/main", cqDepend, *uploadFlag, *compileFlag, *forceFlag, *cqP1Flag)
	defer cleanupLibqrtr()

	libqmiCl, cleanupLibqmi := uprevRepo(rootDir, "libqmi", "upstream", cqDepend, *uploadFlag, *compileFlag, *forceFlag, *cqP1Flag)
	defer cleanupLibqmi()

	libmbimCl, cleanupLibmbim := uprevRepo(rootDir, "libmbim", "upstream", cqDepend, *uploadFlag, *compileFlag, *forceFlag, *cqP1Flag)
	defer cleanupLibmbim()

	cqDepend = libqrtrCl + libqmiCl + libmbimCl
	cqDepend = strings.ReplaceAll(strings.TrimSpace(cqDepend), " ", ",")
	_, cleanupMM := uprevRepo(rootDir, "modemmanager-next", "upstream", cqDepend, *uploadFlag, *compileFlag, *forceFlag, *cqP1Flag)
	defer cleanupMM()
}
