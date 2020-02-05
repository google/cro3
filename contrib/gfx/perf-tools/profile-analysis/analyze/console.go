// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyze

import (
	"fmt"
	"io"
	"strings"

	"github.com/chzyer/readline"
)

// Console is an interactive console to issues profile-analysis commands. It
// supports command completion and history.
type Console struct {
	profiles Profiles
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

	console.profiles.p1 = prof1
	console.profiles.p2 = prof2

	for {
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
			err := ExecCommand(tokens, &console.profiles)
			if err != nil {
				if err == QUIT_REQUESTED {
					break
				}
				fmt.Println(err.Error())
			}
		}
	}
}

// Create the command completer, used for tab-completion.
func createCompleter() *readline.PrefixCompleter {
	numCmd := len(cmdDispatchTable)
	pcItems := make([]readline.PrefixCompleterInterface, 0, numCmd+1)
	helpChildren := make([]readline.PrefixCompleterInterface, 0, numCmd)
	for name, cmd := range cmdDispatchTable {
		pcItems = append(pcItems, readline.PcItem(name))
		if cmd.moreHelp != nil {
			helpChildren = append(helpChildren, readline.PcItem(name))
		}
	}

	// "Help" has its own children command, to make it easier to get extra help
	// for commands that provide by typing "help" + tab.
	helpItem := readline.PcItem("help")
	helpItem.SetChildren(helpChildren)
	pcItems = append(pcItems, helpItem)

	pc := readline.NewPrefixCompleter()
	pc.SetChildren(pcItems)
	return pc
}
