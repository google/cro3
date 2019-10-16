// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

//
// A utility to report status of a repo tree, listing all git repositories wich
// have branches or are not in sync with the upstream, works the same insde
// and outside chroot.
//
// To install it run
//
// go build -o <directory in your PATH>/willis willis.go
//
// and to use it just run 'willis'
//

package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
)

type project struct {
	Remote   string `xml:"remote,attr"`
	Path     string `xml:"path,attr"`
	Revision string `xml:"revision,attr"`
	Name     string `xml:"name,attr"`
	// Identifies the tracking branch
	Tracking string
}

type defaultTracking struct {
	Revision string `xml:"revision,attr"`
	Remote   string `xml:"remote,attr"`
}

type include struct {
	Name string `xml:"name,attr"`
}

type remoteServer struct {
	Name  string `xml:"name,attr"`
	Alias string `xml:"alias,attr"`
}

// manifest is a structure representing accumulated contents of all repo XML
// manifest files.
type manifest struct {
	XMLName  xml.Name        `xml:"manifest"`
	Dflt     defaultTracking `xml:"default"`
	Include  []include       `xml:"include"`
	Projects []project       `xml:"project"`
	Remotes  []remoteServer  `xml:"remote"`
}

// gitTreeReport is used to represent information about a single git tree.
type gitTreeReport struct {
	branches string
	status   string
	osErrors string
	errorMsg string
}

// ProjectMap maps project paths into project structures.
type ProjectMap map[string]project

var reHex = regexp.MustCompile("^[0-9a-fA-F]+$")

// reDetached and reNoBranch cover two possible default branch states.
var reDetached = regexp.MustCompile(`^\* .*\(HEAD detached (?:at|from) (?:[^ ]+)\)[^ ]* ([^ ]+)`)
var reNoBranch = regexp.MustCompile(`^\* .*\(no branch\)[^ ]* ([^ ]+) `)

type color int

const (
	colorRed color = iota
	colorBlue
)

func colorize(text string, newColor color) string {
	var code string

	switch newColor {
	case colorRed:
		code = "31"
		break
	case colorBlue:
		code = "34"
		break
	default:
		return text
	}
	return fmt.Sprintf("\x1b[%sm%s\x1b[m", code, text)
}

// getRepoManifest given the manifest directory return Chrome OS manifest.
// This function starts with 'default.xml' in the manifest root directory,
// goes through nested manifest files and returns a single manifest object
// representing current expected repo state.
func getRepoManifest(rootDir string) (*manifest, error) {
	var manifest manifest

	files := []string{path.Join(rootDir, "default.xml")}
	for len(files) > 0 {
		var file string

		file, files = files[0], files[1:]

		bytes, err := ioutil.ReadFile(file)
		if err != nil {
			return nil, err
		}

		// xml.Unmarshal keeps adding parsed data to the same manifest
		// structure instance. When invoked with a non-empty manifest,
		// xml.Unmarshal() does not zero out previously retrieved data
		// fields even if they are not present in the currently
		// supplied xml blob. Slices of objects (like project in the
		// manifest case) keep being added to.
		//
		// Note that this behavior seems to contradict the spec which in
		// https://golang.org/pkg/encoding/xml/#Unmarshal reads
		//
		// == quote ==
		// A missing element or empty attribute value will be
		// unmarshaled as a zero value.
		// == quote end ==
		//
		// Should a golang update change the implementation, the failure
		// of reading the manifests would be immediately obvious, the
		// code will have to be changed then.
		if err := xml.Unmarshal(bytes, &manifest); err != nil {
			return nil, err
		}

		for _, inc := range manifest.Include {
			files = append(files, path.Join(rootDir, inc.Name))
		}

		manifest.Include = nil
	}
	return &manifest, nil
}

func prepareProjectMap(repoRoot string) (*ProjectMap, error) {
	manifest, err := getRepoManifest(path.Join(repoRoot, ".repo", "manifests"))
	if err != nil {
		return nil, err
	}

	// Set up mapping to remote server name aliases.
	aliases := make(map[string]string)
	for _, remote := range manifest.Remotes {
		if remote.Alias != "" {
			aliases[remote.Name] = remote.Alias
		}
	}

	pm := make(ProjectMap)
	for _, p := range manifest.Projects {
		if p.Revision == "" {
			p.Revision = manifest.Dflt.Revision
		}
		if p.Remote == "" {
			p.Remote = manifest.Dflt.Remote
		} else if alias, ok := aliases[p.Remote]; ok {
			p.Remote = alias
		}

		if reHex.MatchString(p.Revision) {
			p.Tracking = p.Revision
		} else {
			p.Tracking = p.Remote + "/" + strings.TrimPrefix(p.Revision, "refs/heads/")
		}
		pm[p.Path] = p
	}
	return &pm, nil
}

func findRepoRoot() (string, error) {
	myPath, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("failed to get current directory: %v", err)
	}
	for {
		if myPath == "/" {
			return "", errors.New("not running in a repo tree")
		}
		repo := path.Join(myPath, ".repo")
		stat, err := os.Stat(repo)
		if err != nil {
			if !os.IsNotExist(err) {
				return "", fmt.Errorf("cannot stat %s: %v", repo, err)
			}
			myPath = filepath.Dir(myPath)
			continue
		}

		if !stat.IsDir() {
			myPath = filepath.Dir(myPath)
			continue
		}
		return myPath, err
	}
}

// runCommand runs a shell command.
// cmdArray is an array of strings starting with the command name and followed
//    by the command line paramters.
// Returns two strinngs (stdout and stderr) and the error value.
func runCommand(args ...string) (stdout, stderr string, err error) {
	var outbuf bytes.Buffer
	var errbuf bytes.Buffer

	cmd := exec.Command(args[0], args[1:]...)
	cmd.Stdout = &outbuf
	cmd.Stderr = &errbuf
	err = cmd.Run()

	// To keep indentation intact, we don't want to change non-error git
	// output formatting, but still want to strip the trainling newline in
	// this output. Error output formatting does not need to be preserved,
	// let's trim it on both sides.
	stdout = strings.TrimRight(outbuf.String(), "\n")
	stderr = strings.TrimSpace(errbuf.String())
	return
}

// checkGitTree generates a text describing status of a git tree.
// Status includes outputs of 'git branch' and 'git status' commands, thus
// listing all branches in the current tree as well as its state (outstanding
// files, git state, etc.).
// Ignore 'git branch -vv' output in case there are no local branches and the
// git tree is synced up with the tracking branch.
func checkGitTree(gitPath string, tracking string) gitTreeReport {
	stdout, stderr, err := runCommand("git", "-C", gitPath, "branch", "-vv", "--color")

	if err != nil {
		return gitTreeReport{
			branches: stdout,
			osErrors: stderr,
			errorMsg: fmt.Sprintf("failed to retrieve branch information: %v", err)}
	}

	branches := strings.Split(stdout, "\n")

	headOk := true
	var sha string
	for i, branch := range branches {
		// Check for both possible default branch state outputs.
		matches := reDetached.FindStringSubmatch(branch)
		if len(matches) == 0 {
			matches = reNoBranch.FindStringSubmatch(branch)
		}
		if len(matches) == 0 {
			continue
		}

		// git sha of this tree.
		sha = matches[1]

		// Check if local git sha is the same as tracking branch.
		stdout, stderr, err = runCommand("git", "-C", gitPath, "diff", sha, tracking)
		if err != nil {
			return gitTreeReport{
				branches: stdout,
				osErrors: stderr,
				errorMsg: fmt.Sprintf("failed to compare branches: %v", err)}
		}

		if stdout != "" {
			headOk = false
			branches[i] = colorize("!!!! ", colorRed) + branch
		}
		break
	}

	stdout, stderr, err = runCommand("git", "-C", gitPath, "status", "-s")

	if err != nil {
		return gitTreeReport{
			branches: stdout,
			osErrors: stderr,
			errorMsg: fmt.Sprintf("failed to retrieve status information: %v", err)}
	}

	var report gitTreeReport

	if len(branches) != 1 || sha == "" || !headOk || stdout != "" {
		report.branches = strings.Join(branches, "\n")
		report.status = stdout
	}

	return report
}

func reportProgress(startedCounter, runningCounter int) {
	fmt.Printf("Started %3d still going %3d\r", startedCounter, runningCounter)
}

func printResults(results map[string]gitTreeReport) {
	var keys []string

	for key, result := range results {
		if result.branches+result.status+result.osErrors+result.errorMsg == "" {
			continue
		}
		keys = append(keys, key)
	}

	sort.Strings(keys)

	fmt.Println() // Go down from status stats line.
	for _, key := range keys {
		fmt.Printf("%s\n", colorize(key, colorBlue))
		if results[key].errorMsg != "" {
			fmt.Printf("%s\n", colorize(results[key].errorMsg, colorRed))
		}
		if results[key].osErrors != "" {
			fmt.Printf("%s\n", colorize(results[key].osErrors, colorRed))
		}
		if results[key].branches != "" {
			fmt.Printf("%s\n", results[key].branches)
		}
		if results[key].status != "" {
			fmt.Printf("%s\n", results[key].status)
		}
		fmt.Println()
	}

}

// getMaxGoCount - suggest maximum number of concurrent go routines.
// Determine current limit of number of open files and return the suggested
// maximum number of concurrent go routines. Conservatively keep it at 10% of
// the number of open files limit.
func getMaxGoCount() (int, error) {
	stdout, _, err := runCommand("sh", "-c", "ulimit -Sn")
	if err != nil {
		return 0, err
	}
	limit, err := strconv.Atoi(stdout)
	if err != nil {
		return 0, err
	}
	// This asssumes that the max number of opened files limit exceeds 10,
	// which is deemed a very reasonable assumption.
	return (limit / 10), nil
}

func main() {
	repoRoot, err := findRepoRoot()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	pm, err := prepareProjectMap(repoRoot)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	// project map (pm) includes all projects present in xml files in
	// .repo/manifests, but not all of them might be included in the repo
	// checkout, let's trust 'repo list' command to report the correct
	// list of projects.
	repos, stderr, err := runCommand("repo", "list")
	if err != nil {
		fmt.Fprintln(os.Stderr, stderr)
		os.Exit(1)
	}

	var countMtx sync.Mutex

	startedCounter := 0
	runningCounter := 0
	results := make(map[string]gitTreeReport)
	cwd, err := os.Getwd()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	maxGoCount, err := getMaxGoCount()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to get max go routine count: %v\n", err)
		os.Exit(1)
	}

	repoList := strings.Split(repos, "\n")

	throttlingNeeded := maxGoCount < len(repoList)
	var ch chan bool
	if throttlingNeeded {
		// Create a channel to use it as a throttle to prevent from starting
		// too many git queries concurrently.
		ch = make(chan bool, maxGoCount)
		fmt.Printf("Throttling at %d concurrent checks\n", maxGoCount)
	}

	var wg sync.WaitGroup
	for _, line := range repoList {
		gitPath := strings.TrimSpace(strings.Split(line, ":")[0])
		wg.Add(1)
		go func() {
			defer func() {
				runningCounter--
				countMtx.Unlock()
				if throttlingNeeded {
					<-ch
				}
				wg.Done()
			}()
			if throttlingNeeded {
				ch <- true
			}
			countMtx.Lock()
			startedCounter++
			runningCounter++
			countMtx.Unlock()
			gitTree := path.Join(repoRoot, gitPath)
			report := checkGitTree(gitTree, (*pm)[gitPath].Tracking)

			relpath, err := filepath.Rel(cwd, gitTree)

			if err != nil {
				fmt.Fprintln(os.Stderr, stderr)
				// In the unlikely event of filepath.Rel()
				// failing, use full git path as the key in
				// the results map.
				relpath = gitPath
			}

			countMtx.Lock()
			results[relpath] = report
			reportProgress(startedCounter, runningCounter)
		}()
	}

	stillRunning := true
	for stillRunning {
		countMtx.Lock()
		reportProgress(startedCounter, runningCounter)
		if runningCounter == 0 {
			stillRunning = false
		}
		countMtx.Unlock()
	}
	wg.Wait()

	printResults(results)
}
