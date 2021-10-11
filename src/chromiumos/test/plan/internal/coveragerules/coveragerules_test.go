// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package coveragerules_test

import (
	"bytes"
	"chromiumos/test/plan/internal/coveragerules"
	"strings"
	"testing"

	testpb "go.chromium.org/chromiumos/config/go/test/api"
)

func TestWriteTextSummary(t *testing.T) {
	coverageRules := []*testpb.CoverageRule{
		{
			Name: "rule1",
			DutCriteria: []*testpb.DutCriterion{
				{
					AttributeId: &testpb.DutAttribute_Id{
						Value: "attridA",
					},
					Values: []string{"verylongdutattributevalue", "attrv2"},
				},
				{
					AttributeId: &testpb.DutAttribute_Id{
						Value: "longdutattributeid",
					},
					Values: []string{"attrv70"},
				},
			},
		},
		{
			Name: "rule2withalongname",
			DutCriteria: []*testpb.DutCriterion{
				{
					AttributeId: &testpb.DutAttribute_Id{
						Value: "attridB",
					},
					Values: []string{"attrv3"},
				},
			},
		},
	}

	var output bytes.Buffer

	expectedOutput := `
name                  attribute_id          attribute_values
rule1                 attridA               attrv2|verylongdutattributevalue
rule1                 longdutattributeid    attrv70
rule2withalongname    attridB               attrv3
`

	if err := coveragerules.WriteTextSummary(&output, coverageRules); err != nil {
		t.Fatalf("coveragerules.WriteTextSummary failed: %s", err)
	}

	if strings.TrimSpace(output.String()) != strings.TrimSpace(expectedOutput) {
		t.Errorf("coverageRules.WriteTextSummary returned %s, want %s", output.String(), expectedOutput)
	}
}
