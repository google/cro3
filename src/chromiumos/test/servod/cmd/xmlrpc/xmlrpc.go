// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package xmlrpc implements the XML-RPC client library.
package xmlrpc

import (
	"bytes"
	"context"
	"encoding/xml"
	"fmt"
	"io/ioutil"
	"math"
	"net/http"
	"reflect"
	"strconv"
	"strings"
	"time"

	"go.chromium.org/chromiumos/config/go/api/test/xmlrpc"
	"go.chromium.org/luci/common/errors"
)

const (
	// defaultRPCTimeout is expected time to get response from servo for most regular commands.
	defaultRPCTimeout = 10 * time.Second
	// maxRPCTimeout is very long, because some of the servo calls are really slow.
	maxRPCTimeout = 1 * time.Hour
)

// XMLRpc holds the XML-RPC information.
type XMLRpc struct {
	host string
	port int
}

// New creates a new XMLRpc object for communicating with XML-RPC server.
func New(host string, port int) *XMLRpc {
	return &XMLRpc{host: host, port: port}
}

// Call represents a XML-RPC call request.
type Call struct {
	method  string
	args    []interface{}
	timeout time.Duration
}

// methodCall mirrors the structure of an XML-RPC method call.
type methodCall struct {
	XMLName    xml.Name `xml:"methodCall"`
	MethodName string   `xml:"methodName"`
	Params     *[]param `xml:"params>param"`
}

// methodResponse is an XML-RPC response.
type methodResponse struct {
	XMLName xml.Name `xml:"methodResponse"`
	Params  *[]param `xml:"params>param,omitempty"`
	Fault   *fault   `xml:"fault,omitempty"`
}

// param is an XML-RPC param.
type param struct {
	Value value `xml:"value"`
}

// fault is an XML-RPC fault.
// If present, it usually contains in its value a struct of two members:
// faultCode (an int) and faultString (a string).
type fault struct {
	Value value `xml:"value"`
}

// Value is an XML-RPC value.
type value struct {
	Boolean *string    `xml:"boolean,omitempty"`
	Double  *string    `xml:"double,omitempty"`
	Int     *string    `xml:"int,omitempty"`
	Str     *string    `xml:"string,omitempty"`
	Array   *xmlArray  `xml:"array,omitempty"`
	Struct  *xmlStruct `xml:"struct,omitempty"`
}

// xmlArray is an XML-RPC array.
type xmlArray struct {
	Values []value `xml:"data>value,omitempty"`
}

// xmlStruct is an XML-RPC struct.
type xmlStruct struct {
	Members []member `xml:"member,omitempty"`
}

// member is an XML-RPC object containing a name and a value.
type member struct {
	Name  string `xml:"name"`
	Value value  `xml:"value"`
}

// String implements the String() interface of value.
// Example:
//  "test-string" : (string)test-string
//        4       : (int)4
//        1.25    : (double)1.25
func (v value) String() string {
	if v.Boolean != nil {
		return "(boolean)" + *v.Boolean
	}
	if v.Double != nil {
		return "(double)" + *v.Double
	}
	if v.Int != nil {
		return "(int)" + *v.Int
	}
	if v.Str != nil {
		return "(string)" + *v.Str
	}
	if v.Array != nil {
		var values []string
		for _, e := range v.Array.Values {
			values = append(values, e.String())
		}
		return "[" + strings.Join(values, ", ") + "]"
	}
	if v.Struct != nil {
		var values []string
		for _, m := range v.Struct.Members {
			values = append(values, fmt.Sprintf("%s: %s", m.Name, m.Value.String()))
		}
		return "{" + strings.Join(values, ", ") + "}"
	}
	return "<empty>"
}

// FaultError is a type of error representing an XML-RPC fault.
type FaultError struct {
	Code   int
	Reason string
}

// Error represent error message generation.
func (e FaultError) Error() string {
	return fmt.Sprintf("Fault %d:%s", e.Code, e.Reason)
}

// NewFaultError creates a FaultError.
func NewFaultError(code int, reason string) FaultError {
	return FaultError{
		Code:   code,
		Reason: reason,
	}
}

// xmlBooleanToBool converts the strings '1' or '0' into boolean.
func xmlBooleanToBool(xmlBool string) (bool, error) {
	if len(xmlBool) != 1 {
		return false, errors.Reason("xmlBooleanToBool got %q; expected '1' or '0'", xmlBool).Err()
	}
	switch xmlBool[0] {
	case '1':
		return true, nil
	case '0':
		return false, nil
	default:
		return false, errors.Reason("xmlBooleanToBool got %q; expected '1' or '0'", xmlBool).Err()
	}
}

// boolToXMLBoolean converts a Go boolean to an XML-RPC boolean string.
func boolToXMLBoolean(v bool) string {
	if v {
		return "1"
	}
	return "0"
}

// xmlIntegerToInt converts numeric strings such as '-1' into integers.
func xmlIntegerToInt(xmlInt string) (int, error) {
	if len(xmlInt) == 0 {
		return 0, errors.New("xmlIntegerToInt got empty xml value")
	}
	i, err := strconv.ParseInt(xmlInt, 10, 32)
	if err != nil {
		return 0, err
	}
	return int(i), nil
}

// intToXMLInteger converts a Go integer to an XML-RPC integer string.
func intToXMLInteger(i int) (string, error) {
	if i > math.MaxInt32 || i < math.MinInt32 {
		return "", errors.Reason("intToXMLInteger needs a value that can fit in an int32: got %d, want between %d and %d", i, math.MinInt32, math.MaxInt32).Err()
	}
	return strconv.FormatInt(int64(i), 10), nil
}

// xmlDoubleToFloat64 converts double-like strings such as "1.5" into float64s.
func xmlDoubleToFloat64(s string) (float64, error) {
	if len(s) == 0 {
		return 0.0, errors.Reason("xmlDoubleToFloat64 got empty xml value").Err()
	}
	return strconv.ParseFloat(s, 64)
}

// float64ToXMLDouble converts a Go float64 to an XML-RPC double-like string.
func float64ToXMLDouble(f float64) string {
	return strconv.FormatFloat(f, 'f', -1, 64)
}

// newValue creates an XML-RPC <value>.
func newValue(in interface{}) (value, error) {
	if reflect.TypeOf(in).Kind() == reflect.Slice || reflect.TypeOf(in).Kind() == reflect.Array {
		v := reflect.ValueOf(in)
		var a xmlArray
		for i := 0; i < v.Len(); i++ {
			val, err := newValue(v.Index(i).Interface())
			if err != nil {
				return value{}, err
			}
			a.Values = append(a.Values, val)
		}
		return value{Array: &a}, nil
	}
	switch v := in.(type) {
	case string:
		s := v
		return value{Str: &s}, nil
	case bool:
		b := boolToXMLBoolean(v)
		return value{Boolean: &b}, nil
	case int:
		i, err := intToXMLInteger(v)
		if err != nil {
			return value{}, err
		}
		return value{Int: &i}, nil
	case float64:
		f := float64ToXMLDouble(v)
		return value{Double: &f}, nil
	case *xmlrpc.Value:
		sv := v.GetScalarOneof()
		if x, ok := sv.(*xmlrpc.Value_Int); ok {
			return newValue(x.Int)
		} else if x, ok := sv.(*xmlrpc.Value_Boolean); ok {
			return newValue(x.Boolean)
		} else if x, ok := sv.(*xmlrpc.Value_String_); ok {
			return newValue(x.String_)
		} else if x, ok := sv.(*xmlrpc.Value_Double); ok {
			return newValue(x.Double)
		}
	}
	return value{}, errors.Reason("%q is not a supported type for newValue", reflect.TypeOf(in)).Err()
}

// newParams creates a list of XML-RPC <params>.
func newParams(args []interface{}) ([]param, error) {
	var params []param
	for _, arg := range args {
		v, err := newValue(arg)
		if err != nil {
			return nil, err
		}
		params = append(params, param{v})
	}
	return params, nil
}

// NewCall creates a XML-RPC call.
func NewCall(method string, args ...interface{}) Call {
	return NewCallTimeout(method, defaultRPCTimeout, args...)
}

// NewCallTimeout creates a XML-RPC call.
func NewCallTimeout(method string, timeout time.Duration, args ...interface{}) Call {
	return Call{
		method:  method,
		args:    args,
		timeout: timeout,
	}
}

// serializeMethodCall turns a method and args into a serialized XML-RPC method call.
func serializeMethodCall(cl Call) ([]byte, error) {
	params, err := newParams(cl.args)
	if err != nil {
		return nil, err
	}
	return xml.Marshal(&methodCall{MethodName: cl.method, Params: &params})
}

// getTimeout returns the lowest of the default timeout or remaining duration
// to the context's deadline.
func getTimeout(ctx context.Context, cl Call) time.Duration {
	timeout := cl.timeout
	if timeout > maxRPCTimeout {
		timeout = maxRPCTimeout
	}
	if dl, ok := ctx.Deadline(); ok {
		newTimeout := dl.Sub(time.Now())
		if newTimeout < timeout {
			timeout = newTimeout
		}
	}
	return timeout
}

// unpackValue unpacks a value struct into the given pointers.
func unpackValue(val value, out interface{}) error {
	switch o := out.(type) {
	case *string:
		if val.Str == nil {
			return errors.Reason("value %s is not a string value", val).Err()
		}
		*o = *val.Str
	case *bool:
		if val.Boolean == nil {
			return errors.Reason("value %s is not a boolean value", val).Err()
		}
		v, err := xmlBooleanToBool(*val.Boolean)
		if err != nil {
			return err
		}
		*o = v
	case *int:
		if val.Int == nil {
			return errors.Reason("value %s is not an int value", val).Err()
		}
		i, err := xmlIntegerToInt(*val.Int)
		if err != nil {
			return err
		}
		*o = i
	case *float64:
		if val.Double == nil {
			return errors.Reason("value %s is not a double value", val).Err()
		}
		f, err := xmlDoubleToFloat64(*val.Double)
		if err != nil {
			return err
		}
		*o = f
	case *[]string:
		if val.Array == nil {
			return errors.Reason("value %s is not an array value", val).Err()
		}
		for _, e := range val.Array.Values {
			var i string
			if err := unpackValue(e, &i); err != nil {
				return err
			}
			*o = append(*o, i)
		}
	case *[]bool:
		if val.Array == nil {
			return errors.Reason("value %s is not an array value", val).Err()
		}
		for _, e := range val.Array.Values {
			var i bool
			if err := unpackValue(e, &i); err != nil {
				return err
			}
			*o = append(*o, i)
		}
	case *[]int:
		if val.Array == nil {
			return errors.Reason("value %s is not an array value", val).Err()
		}
		for _, e := range val.Array.Values {
			var i int
			if err := unpackValue(e, &i); err != nil {
				return err
			}
			*o = append(*o, i)
		}
	case *[]float64:
		if val.Array == nil {
			return errors.Reason("value %s is not an array value", val).Err()
		}
		for _, e := range val.Array.Values {
			var i float64
			if err := unpackValue(e, &i); err != nil {
				return err
			}
			*o = append(*o, i)
		}
	case *xmlrpc.Value:
		if val.Str != nil {
			o.ScalarOneof = &xmlrpc.Value_String_{
				String_: *val.Str,
			}
		} else if val.Boolean != nil {
			v, err := xmlBooleanToBool(*val.Boolean)
			if err != nil {
				return err
			}
			o.ScalarOneof = &xmlrpc.Value_Boolean{
				Boolean: v,
			}
		} else if val.Int != nil {
			i, err := xmlIntegerToInt(*val.Int)
			if err != nil {
				return err
			}
			o.ScalarOneof = &xmlrpc.Value_Int{
				Int: int32(i),
			}
		} else if val.Double != nil {
			f, err := xmlDoubleToFloat64(*val.Double)
			if err != nil {
				return err
			}
			o.ScalarOneof = &xmlrpc.Value_Double{
				Double: f,
			}
		} else if val.Array != nil {
			vl := make([]*xmlrpc.Value, len(val.Array.Values))
			o.ScalarOneof = &xmlrpc.Value_Array{
				Array: &xmlrpc.Array{
					Values: vl,
				},
			}
			for i, v := range val.Array.Values {
				vl[i] = &xmlrpc.Value{}
				if err := unpackValue(v, vl[i]); err != nil {
					return err
				}
			}
		} else {
			return errors.Reason("not implemented type of *xmlrpc.Value,  %#v", val).Err()
		}
	default:
		return errors.Reason("%q is not a supported type for unpackValue %#v", reflect.TypeOf(out), out).Err()
	}
	return nil
}

// unpack extracts a response's arguments into a list of given pointers.
func (r *methodResponse) unpack(out []interface{}) error {
	if r.Params == nil {
		if len(out) != 0 {
			return errors.Reason("response contains no args; want %d", len(out)).Err()
		}
		return nil
	}
	if len(*r.Params) != len(out) {
		return errors.Reason("response contains %d arg(s); want %d", len(*r.Params), len(out)).Err()
	}

	for i, p := range *r.Params {
		if err := unpackValue(p.Value, out[i]); err != nil {
			return errors.Annotate(err, "failed to unpack response param at index %d", i).Err()
		}
	}

	return nil
}

// checkFault returns a FaultError if the response contains a fault with a non-zero faultCode.
func (r *methodResponse) checkFault() error {
	if r.Fault == nil {
		return nil
	}
	if r.Fault.Value.Struct == nil {
		return errors.Reason("fault %s doesn't contain xml-rpc struct", r.Fault.Value).Err()
	}
	var rawFaultCode string
	var faultString string
	for _, m := range r.Fault.Value.Struct.Members {
		switch m.Name {
		case "faultCode":
			if m.Value.Int == nil {
				return errors.Reason("faultCode %s doesn't provide integer value", m.Value).Err()
			}
			rawFaultCode = *m.Value.Int
		case "faultString":
			if m.Value.Str == nil {
				return errors.Reason("faultString %s doesn't provide string value", m.Value).Err()
			}
			faultString = *m.Value.Str
		default:
			return errors.Reason("unexpected fault member name: %s", m.Name).Err()
		}
	}
	faultCode, err := xmlIntegerToInt(rawFaultCode)
	if err != nil {
		return errors.Annotate(err, "interpreting fault code").Err()
	}
	if faultCode == 0 {
		return errors.Reason("response contained a fault with unexpected code 0; want non-0: faultString=%s", faultString).Err()
	}
	return NewFaultError(faultCode, faultString)
}

// Run makes an XML-RPC call to the server.
func (r *XMLRpc) Run(ctx context.Context, cl Call, out ...interface{}) error {
	body, err := serializeMethodCall(cl)
	if err != nil {
		return err
	}

	// Get RPC timeout duration from context or use default.
	timeout := getTimeout(ctx, cl)
	serverURL := fmt.Sprintf("http://%s:%d", r.host, r.port)
	httpClient := &http.Client{Timeout: timeout}
	resp, err := httpClient.Post(serverURL, "text/xml", bytes.NewBuffer(body))
	if err != nil {
		return errors.Annotate(err, "timeout = %v", timeout).Err()
	}
	defer func() { resp.Body.Close() }()

	// Read body and unmarshal XML.
	bodyBytes, err := ioutil.ReadAll(resp.Body)
	res := methodResponse{}
	if err = xml.Unmarshal(bodyBytes, &res); err != nil {
		return err
	}
	if err = res.checkFault(); err != nil {
		return err
	}
	// If outs are specified, unpack response params.
	// Otherwise, return without unpacking.
	if len(out) > 0 {
		if err := res.unpack(out); err != nil {
			// testing.ContextLogf(ctx, "Failed to unpack XML-RPC response for request %v: %s", cl, string(bodyBytes))
			return err
		}
	}
	return nil
}
