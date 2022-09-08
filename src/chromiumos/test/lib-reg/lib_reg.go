// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common defines shared resources across registration and test libs service.
package main

import (
	"errors"
	"strings"
)

// LibReg repsresents the information provided by a single library
// when registering.
type LibReg struct {
	Name        string   `json:"name"`
	APIType     string   `json:"api_type"`
	Version     int      `json:"version"`
	Image       string   `json:"image"`
	RunOptions  string   `json:"run_options"`
	Port        string   `json:"port"`
	Ping        string   `json:"ping"`
	Owners      []string `json:"owners"`
	Description string   `json:"description"`
}

// Validate returns an error if the registration info has any issues.
func (r *LibReg) Validate() error {
	problems := []string{}
	if r.Name == "" {
		problems = append(problems, "Name cannot be blank")
	}
	if r.APIType == "" {
		problems = append(problems, "APIType cannot be blank")
	}
	if r.APIType != "REST" {
		problems = append(problems, "Unrecognized API type of "+r.APIType)
	}
	if r.Image == "" {
		problems = append(problems, "Image name cannot be blank")
	}
	if r.Port == "" {
		problems = append(problems, "Port name cannot be blank")
	}
	if len(r.Owners) == 0 {
		problems = append(problems, "Provide at least one owner")
	}
	if r.Description == "" {
		problems = append(problems, "Description string cannot be blank")
	}
	if len(problems) != 0 {
		return errors.New(strings.Join(problems, "; "))
	}
	return nil
}
