// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package xmlrpc

import (
	"encoding/xml"
	"fmt"
	"math"
	"reflect"
	"strconv"
	"testing"
)

func TestXMLBooleanToBool(t *testing.T) {
	for _, tc := range []struct {
		input     string
		expected  bool
		expectErr bool
	}{
		{"1", true, false},
		{"0", false, false},
		{"rutabaga", false, true},
	} {
		actual, err := xmlBooleanToBool(tc.input)
		if tc.expectErr {
			if err == nil {
				t.Errorf("xmlBooleanToBool(%q) unexpectedly succeeded", tc.input)
			}
		} else {
			if err != nil {
				t.Errorf("xmlBooleanToBool(%q) failed: %v", tc.input, err)
			}
			if actual != tc.expected {
				t.Errorf("xmlBooleanToBool(%q) = %v; want %v", tc.input, actual, tc.expected)
			}
		}
	}
}

func TestBoolToXMLBoolean(t *testing.T) {
	for _, tc := range []struct {
		input    bool
		expected string
	}{
		{true, "1"},
		{false, "0"},
	} {
		actual := boolToXMLBoolean(tc.input)
		if actual != tc.expected {
			t.Errorf("boolToXMLBoolean(%v) = %q; want %q", tc.input, actual, tc.expected)
		}
	}
}

func TestXMLIntegerToInt(t *testing.T) {
	for _, tc := range []struct {
		input     string
		expected  int
		expectErr bool
	}{
		{"1", 1, false},
		{"0", 0, false},
		{"-1", -1, false},
		{"1.5", 0, true},
		{"3000000000", 0, true}, // too big for an int32
		{"easter-egg", 0, true},
		{"true", 0, true},
	} {
		actual, err := xmlIntegerToInt(tc.input)
		if tc.expectErr {
			if err == nil {
				t.Errorf("xmlIntegerToInt(%q) unexpectedly succeeded", tc.input)
			}
			continue
		}
		if err != nil {
			t.Errorf("xmlIntegerToInt(%q) failed: %v", tc.input, err)
			continue
		}
		if actual != tc.expected {
			t.Errorf("xmlIntegerToInt(%q) = %v; want %v", tc.input, actual, tc.expected)
		}
	}
}

func TestIntToXMLInteger(t *testing.T) {
	for _, tc := range []struct {
		input     int
		expected  string
		expectErr bool
	}{
		{1, "1", false},
		{0, "0", false},
		{-1, "-1", false},
		{math.MaxInt64, "", true},
	} {
		actual, err := intToXMLInteger(tc.input)
		if tc.expectErr {
			if err == nil {
				t.Errorf("intToXMLInteger(%d) unexpectedly succeeded", tc.input)
				continue
			}
		}
		if actual != tc.expected {
			t.Errorf("IntToXMLInteger(%v) = %q; want %q", tc.input, actual, tc.expected)
		}
	}
}

func TestXMLDoubleToFloat64(t *testing.T) {
	for _, tc := range []struct {
		input     string
		expected  float64
		expectErr bool
	}{
		{"1", 1.0, false},
		{"3.14", 3.14, false},
		{"-3.14", -3.14, false},
		{strconv.FormatFloat(math.MaxFloat64, 'f', -1, 64), math.MaxFloat64, false},
		{strconv.FormatFloat(math.SmallestNonzeroFloat64, 'f', -1, 64), math.SmallestNonzeroFloat64, false},
		{"", 0.0, true},
		{"easter-egg", 0.0, true},
		{"true", 0.0, true},
	} {
		actual, err := xmlDoubleToFloat64(tc.input)
		if tc.expectErr {
			if err == nil {
				t.Errorf("xmlDoubleToFloat64(%q) unexpectedly succeeded", tc.input)
			}
			continue
		}
		if err != nil {
			t.Errorf("xmlDoubleToFloat64(%q) failed: %v", tc.input, err)
			continue
		}
		if actual != tc.expected {
			t.Errorf("xmlDoubleToFloat64(%q) = %v; want %v", tc.input, actual, tc.expected)
		}
	}
}

func TestFloat64ToXMLDouble(t *testing.T) {
	for _, tc := range []struct {
		input    float64
		expected string
	}{
		{3.14, "3.14"},
		{0, "0"},
		{-1, "-1"},
	} {
		actual := float64ToXMLDouble(tc.input)
		if actual != tc.expected {
			t.Errorf("float64ToXMLDouble(%v) = %q; want %q", tc.input, actual, tc.expected)
		}
	}
}

func TestValueString(t *testing.T) {
	s := "1"
	v := value{Int: &s}
	sOut := fmt.Sprintf("%v", v)
	sWant := "(int)1"
	if sOut != sWant {
		t.Errorf("String() got %q, want %q", sOut, sWant)
	}

	s = "1"
	v = value{Boolean: &s}
	sOut = fmt.Sprintf("%v", v)
	sWant = "(boolean)1"
	if sOut != sWant {
		t.Errorf("String() got %q, want %q", sOut, sWant)
	}

	s = "1.2"
	v = value{Double: &s}
	sOut = fmt.Sprintf("%v", v)
	sWant = "(double)1.2"
	if sOut != sWant {
		t.Errorf("String() got %q, want %q", sOut, sWant)
	}

	s = "1.2"
	v = value{Str: &s}
	sOut = fmt.Sprintf("%v", v)
	sWant = "(string)1.2"
	if sOut != sWant {
		t.Errorf("String() got %q, want %q", sOut, sWant)
	}

	s1 := "2"
	s2 := "0"
	s3 := "2.1"
	s4 := "2.1"
	a := xmlArray{Values: []value{
		{Int: &s1},
		{Boolean: &s2},
		{Double: &s3},
		{Str: &s4},
	}}
	v = value{Array: &a}
	sOut = fmt.Sprintf("%v", v)
	sWant = "[(int)2, (boolean)0, (double)2.1, (string)2.1]"
	if sOut != sWant {
		t.Errorf("String() got %q, want %q", sOut, sWant)
	}

	b := xmlStruct{Members: []member{
		{Name: "key1", Value: value{Int: &s1}},
		{Name: "key2", Value: value{Boolean: &s2}},
		{Name: "key3", Value: value{Double: &s3}},
		{Name: "key4", Value: value{Str: &s4}},
	}}
	v = value{Struct: &b}
	sOut = fmt.Sprintf("%v", v)
	sWant = "{key1: (int)2, key2: (boolean)0, key3: (double)2.1, key4: (string)2.1}"
	if sOut != sWant {
		t.Errorf("String() got %q, want %q", sOut, sWant)
	}
}

func TestNewValue(t *testing.T) {
	expectedStr := "rutabaga"
	v, err := newValue(expectedStr)
	if err != nil {
		t.Errorf("newValue(%q) failed: %v", expectedStr, err)
		return
	}
	if *v.Str != expectedStr {
		t.Errorf("got %q; want %q", *v.Str, expectedStr)
	}

	expectedBool := true
	expectedBoolStr := "1"
	v, err = newValue(expectedBool)
	if err != nil {
		t.Errorf("input %v gave unexpected error: %v", expectedStr, err)
		return
	}
	if *v.Boolean != expectedBoolStr {
		t.Errorf("got %q; want %q", *v.Boolean, expectedBoolStr)
	}

	expectedInt := -1
	expectedIntStr := "-1"
	v, err = newValue(expectedInt)
	if err != nil {
		t.Errorf("input %v gave unexpected error: %v", expectedInt, err)
		return
	}
	if *v.Int != expectedIntStr {
		t.Errorf("got %q; want %q", *v.Int, expectedIntStr)
	}

	f := -3.14
	expectedDoubleStr := "-3.14"
	v, err = newValue(f)
	if err != nil {
		t.Errorf("input %f gave unexpected error: %v", f, err)
		return
	}
	if *v.Double != expectedDoubleStr {
		t.Errorf("got %q; want %q", *v.Double, expectedDoubleStr)
	}

	arrInt := []int{1, 2}
	s1 := "1"
	s2 := "2"
	expectedArrayOfInt := xmlArray{Values: []value{{Int: &s1}, {Int: &s2}}}
	v, err = newValue(arrInt)
	if err != nil {
		t.Errorf("input %v gave unexpected error: %v", arrInt, err)
		return
	}
	if !reflect.DeepEqual(*v.Array, expectedArrayOfInt) {
		t.Errorf("got %v; want %v", v.Array, expectedArrayOfInt)
	}

	expectedUnsupported := struct{}{}
	v, err = newValue(expectedUnsupported)
	if err == nil {
		t.Errorf("input %v did not throw expected error", expectedUnsupported)
	}
}

func TestNewParams(t *testing.T) {
	actual, err := newParams([]interface{}{"rutabaga", true, -3.14})

	if err != nil {
		t.Errorf("got unexpected error: %v", err)
		return
	}
	if len(actual) != 3 {
		t.Errorf("got len %d; want %d", len(actual), 3)
	}
	if *actual[0].Value.Str != "rutabaga" {
		t.Errorf("for first return value got %q; want %q", *actual[0].Value.Str, "rutabaga")
	}
	if *actual[1].Value.Boolean != "1" {
		t.Errorf("for second return value got %q; want %q", *actual[1].Value.Boolean, "1")
	}
	if *actual[2].Value.Double != "-3.14" {
		t.Errorf("for third return value got %q; want %q", *actual[2].Value.Double, "-3.14")
	}
}

func TestSerializeMethodCall(t *testing.T) {
	cl := NewCall("TestMethod", 1, false, 2.2, "lucky",
		[]int{1, 2}, []bool{false, true}, []float64{1.1, 2.2}, []string{"so", "lucky"})
	body, err := serializeMethodCall(cl)
	if err != nil {
		t.Fatal("Failed to serialize call: ", cl)
	}

	expectedBody := `<methodCall>` +
		`<methodName>TestMethod</methodName>` +
		`<params>` +
		`<param><value><int>1</int></value></param>` +
		`<param><value><boolean>0</boolean></value></param>` +
		`<param><value><double>2.2</double></value></param>` +
		`<param><value><string>lucky</string></value></param>` +
		`<param><value><array><data><value><int>1</int></value><value><int>2</int></value></data></array></value></param>` +
		`<param><value><array><data><value><boolean>0</boolean></value><value><boolean>1</boolean></value></data></array></value></param>` +
		`<param><value><array><data><value><double>1.1</double></value><value><double>2.2</double></value></data></array></value></param>` +
		`<param><value><array><data><value><string>so</string></value><value><string>lucky</string></value></data></array></value></param>` +
		`</params>` +
		`</methodCall>`

	if string(body) != expectedBody {
		t.Errorf("serializeMethodCall: got\n%s\nwant\n%s", string(body), expectedBody)
	}
}

func TestUnpack(t *testing.T) {
	resp := methodResponse{Params: nil}
	var out string
	expErr := "response contains no args; want 1"
	if err := resp.unpack([]interface{}{&out}); err == nil {
		t.Errorf("unpacking got no error")
	} else if err.Error() != expErr {
		t.Errorf("unpacking got %q; want %q", err.Error(), expErr)
	}
	if err := resp.unpack([]interface{}{}); err != nil {
		t.Errorf("unpacking got error %v", err)
	}

	arrIntIn := []int{1, 2}
	params, err := newParams([]interface{}{"rutabaga", true, 1, -3.14, arrIntIn})
	if err != nil {
		t.Fatal("creating params: ", err)
	}
	resp = methodResponse{Params: &params}
	var stringOut string
	var boolOut bool
	var intOut int
	var floatOut float64
	var arrIntOut []int
	if err := resp.unpack([]interface{}{&stringOut, &boolOut, &intOut, &floatOut, &arrIntOut}); err != nil {
		t.Fatal("unpacking:", err)
	}
	if stringOut != "rutabaga" {
		t.Errorf("unpacking %q: got %q; want %q", "rutabaga", stringOut, "rutabaga")
	}
	if boolOut != true {
		t.Errorf("unpacking %q: got %v; want %v", "true", boolOut, true)
	}
	if intOut != 1 {
		t.Errorf("unpacking %q: got %d; want %d", "1", intOut, 1)
	}
	if floatOut != -3.14 {
		t.Errorf("unpacking %q: got %f; want %f", "-3.14", floatOut, -3.14)
	}
	if !reflect.DeepEqual(arrIntIn, arrIntOut) {
		t.Errorf("unpacking %v: got %v", arrIntIn, arrIntOut)
	}
}

func TestXMLResponse(t *testing.T) {
	xmlStr := `
	<?xml version="1.0"?>
	<methodResponse>
	<params>
		<param>
			<value><double>3.14</double></value>
		</param>
		<param>
			<value><int>1</int></value>
		</param>
		<param>
			<value><string>hellow world</string></value>
		</param>
		<param>
			<value><boolean>0</boolean></value>
		</param>
		<param>
			<value>
				<array>
					<data>
						<value><int>10</int></value>
						<value><int>20</int></value>
					</data>
				</array>
			</value>
		</param>
		<param>
			<value>
				<array>
					<data>
						<value><boolean>0</boolean></value>
						<value><boolean>1</boolean></value>
					</data>
				</array>
			</value>
		</param>
		<param>
			<value>
				<array>
					<data>
						<value><double>1.1</double></value>
						<value><double>2.2</double></value>
					</data>
				</array>
			</value>
		</param>
		<param>
			<value>
				<array>
					<data>
						<value><string>10</string></value>
						<value><string>20</string></value>
					</data>
				</array>
			</value>
		</param>
	</params>
	</methodResponse>
	`
	res := methodResponse{}
	if err := xml.Unmarshal([]byte(xmlStr), &res); err != nil {
		t.Fatal("xml unmarshal:", err)
	}
	var stringOut string
	var boolOut bool
	var intOut int
	var floatOut float64
	var arrIntOut []int
	var arrBoolOut []bool
	var arrDoubleOut []float64
	var arrStrOut []string
	if err := res.unpack([]interface{}{&floatOut, &intOut, &stringOut, &boolOut,
		&arrIntOut, &arrBoolOut, &arrDoubleOut, &arrStrOut}); err != nil {
		t.Fatal("response unpack:", err)
	}
	if floatOut != 3.14 {
		t.Errorf("unpacking %q: got %f; want %f", "3.14", floatOut, 3.14)
	}
	if intOut != 1 {
		t.Errorf("unpacking %q: got %d; want %d", "1", intOut, 1)
	}
	if stringOut != "hellow world" {
		t.Errorf("unpacking %q: got %q; want %q", "hellow world", stringOut, "hellow world")
	}
	if boolOut != false {
		t.Errorf("unpacking %q: got %v; want %v", "false", boolOut, false)
	}
	arrIntIn := []int{10, 20}
	if !reflect.DeepEqual(arrIntIn, arrIntOut) {
		t.Errorf("unpacking %v: got %v", arrIntIn, arrIntOut)
	}
	arrBoolIn := []bool{false, true}
	if !reflect.DeepEqual(arrBoolIn, arrBoolOut) {
		t.Errorf("unpacking %v: got %v", arrBoolIn, arrBoolOut)
	}
	arrDoubleIn := []float64{1.1, 2.2}
	if !reflect.DeepEqual(arrDoubleIn, arrDoubleOut) {
		t.Errorf("unpacking %v: got %v", arrDoubleIn, arrDoubleOut)
	}
	arrStrIn := []string{"10", "20"}
	if !reflect.DeepEqual(arrStrIn, arrStrOut) {
		t.Errorf("unpacking %v: got %v", arrStrIn, arrStrOut)
	}
}

func TestCheckFault(t *testing.T) {
	hasFault := []byte(`<?xml version='1.0'?>
	<methodResponse>
		<fault>
			<value>
				<struct>
					<member>
						<name>faultCode</name>
						<value>
							<int>1</int>
						</value>
					</member>
					<member>
						<name>faultString</name>
						<value>
							<string>Bad XML request!</string>
						</value>
					</member>
				</struct>
			</value>
		</fault>
	</methodResponse>`)
	noFault := []byte(`<?xml version='1.0'?>
	<methodResponse>
		<params>
			<param>
				<value>
					<string>Hello, world!</string>
				</value>
			</param>
		</params>
	</methodResponse>`)
	faultWithCode0 := []byte(`<?xml version='1.0'?>
	<methodResponse>
		<fault>
			<value>
				<struct>
					<member>
						<name>faultCode</name>
						<value>
							<int>0</int>
						</value>
					</member>
					<member>
						<name>faultString</name>
						<value>
							<string>Bad XML request!</string>
						</value>
					</member>
				</struct>
			</value>
		</fault>
	</methodResponse>`)
	faultWithUnexpectedMember := []byte(`<?xml version='1.0'?>
	<methodResponse>
		<fault>
			<value>
				<struct>
					<member>
						<name>faultCode</name>
						<value>
							<int>1</int>
						</value>
					</member>
					<member>
						<name>faultString</name>
						<value>
							<string>Bad XML request!</string>
						</value>
					</member>
					<member>
						<name>unexpectedMember</name>
						<value>
							<string>Foo</string>
						</value>
					</member>
				</struct>
			</value>
		</fault>
	</methodResponse>`)
	type testCase struct {
		b                   []byte
		expectErr           bool
		expectFault         bool
		expectedFaultCode   int
		expectedFaultString string
	}
	for i, tc := range []testCase{
		{hasFault, true, true, 1, "Bad XML request!"},
		{noFault, false, false, 0, ""},
		{faultWithCode0, true, false, 0, ""},
		{faultWithUnexpectedMember, true, false, 0, ""},
	} {
		// Check the XML bytes for fault.
		r := methodResponse{}
		if err := xml.Unmarshal(tc.b, &r); err != nil {
			t.Errorf("tc #%d: failed to unmarshal bytes: %v", i, err)
			continue
		}
		e := r.checkFault()

		// Check whether we got an error if expected.
		// If no error is expected, then continue early, since the rest of the test operates on the error.
		if !tc.expectErr {
			if e != nil {
				t.Errorf("tc #%d: unexpected checkFault error response: got %v; want nil", i, e)
			}
			continue
		} else if e == nil {
			t.Errorf("tc #%d: unexpected checkFault error response: got nil; want error", i)
			continue
		}

		// Check whether we got a fault if expected.
		// If no fault is expected, then continue early, since the rest of the test operates on the error.
		fe, isFault := e.(FaultError)
		if !tc.expectFault {
			if isFault {
				t.Errorf("tc #%d: unexpected checkFault error: got '%v'; want non-Fault error", i, e)
			}
			continue
		} else if !isFault {
			t.Errorf("tc #%d: unexpected checkFault error: got '%v'; want FaultError", i, e)
		}

		// Check the Fault's attributes
		if fe.Code != tc.expectedFaultCode {
			t.Errorf("tc #%d: checkFault returned unexpected code: got %d; want %d", i, fe.Code, tc.expectedFaultCode)
		}
		if fe.Reason != tc.expectedFaultString {
			t.Errorf("tc #%d: checkFault returned unexpected reason: got %s; want %s", i, fe.Reason, tc.expectedFaultString)
		}
	}
}
