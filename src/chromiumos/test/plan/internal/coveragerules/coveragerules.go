// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package coveragerules provides utilities for working with CoverageRule protos.
package coveragerules

import (
	"fmt"
	"io"
	"sort"
	"strings"
	"text/tabwriter"

	testpb "go.chromium.org/chromiumos/config/go/test/api"
)

// WriteTextSummary writes a more easily human-readable summary of coverageRules
// to w.
//
// The summary has space-separated columns for rule name, DutCriteria id, and
// DutCriteria values. Each rule name and DutCriterion id gets it's own row,
// with valid DutCriterion values separated by "|" in the row. For example:
//
// name                  attribute_id          attribute_values
// rule1                 attridA               attrv2|verylongdutattributevalue
// rule1                 longdutattributeid    attrv70
// rule2withalongname    attridB               attrv3
func WriteTextSummary(w io.Writer, coverageRules []*testpb.CoverageRule) error {
	// Constants to control tabwriter behavior. Ideally tabwriter would use an
	// options struct so the name for each parameter was clear in the code.
	// Since we don't control the tabwriter package, just use named constants
	// instead.
	const (
		minwidth = 0
		tabwidth = 8
		padding  = 4
		padchar  = ' '
		flags    = 0
	)

	tabWriter := tabwriter.NewWriter(w, minwidth, tabwidth, padding, padchar, flags)

	if _, err := fmt.Fprintln(tabWriter, "name\tattribute_id\tattribute_values"); err != nil {
		return err
	}

	for _, rule := range coverageRules {
		for _, criterion := range rule.DutCriteria {
			sort.Strings(criterion.Values)
			valuesString := strings.Join(criterion.Values, "|")

			if _, err := fmt.Fprintf(
				tabWriter, "%s\t%s\t%s\n", rule.Name, criterion.AttributeId.Value, valuesString,
			); err != nil {
				return err
			}
		}
	}

	return tabWriter.Flush()
}
