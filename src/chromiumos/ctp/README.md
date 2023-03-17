## CTP Client Library
This simplies the process of calling CTP programmatically

## Testing
`go test ./...`

## Usage
### Scheduling Tests via CTP

To schedule tests, create a CTPBuilder object and then call it's `ScheduleCTPBuild` method. This will return a Build object which you can use to track the progress of the test

```
// To run a test, use builder.TestPlanForTests
tp := builder.TestPlanForSuites([]string{"rlz"})

// Minimum required fields; see CTPBuilder object for full reference
ctp := &builder.CTPBuilder{
    Image:      "zork-release/R107-15117.103.0",
    Board:      "zork",
    Pool:       "xolabs-satlab",
    TestPlan:   tp,
}

// Create default client
err := ctp.AddDefaultBBClient(ctx)
if err != nil {
    return err
}


b, err := ctp.ScheduleCTPBuild(c)
```

Note that the default `AuthOptions` may be unsuitable since you will need to match the scope and location of the auth a user logged in with. It is configured to work with `luci-auth login` and if you use different scopes or secrets directories you will need to override the auth options

### Getting CTP Builds

To get the results of tests, use the `builder.GetBuild` function

```
b, err := builder.GetBuild(c, &builder.ClientArgs{}, <123>)
if err != nil {
    fmt.Printf("%s", err)
}
fmt.Printf("%v", b)
```

### Getting Test Results from CTP Builds
CTP builds store test result information in the output properties. The output properties have the following fields ([proto](https://source.corp.google.com/chromeos_public/infra/recipes/recipes/test_platform/cros_test_platform.proto))
- `response`- plaintext JSON field, marked as deprecated due to size
- `compressed_json_response`- [JSON dict converted to string, compressed with zlib, and then converted to base64](https://source.corp.google.com/chromeos_public/infra/recipes/recipes/test_platform/cros_test_platform.py;l=869?q=compressed_json_responses&sq=%20%20package:%5E(chromeos_public%7Cchromeos_internal%7Cchops_infra_internal)$)
- `compressed_responses`- [Proto object converted to string, compressed with zlib, and then converted to base64](https://source.corp.google.com/chromeos_public/infra/recipes/recipes/test_platform/cros_test_platform.py;l=872?q=compressed_json_responses&sq=%20%20package:%5E(chromeos_public%7Cchromeos_internal%7Cchops_infra_internal)$)

Code sample extracting the compressed_json_response info:
```
// Get `compressed_json_responses` field
s := b.Output.Properties.Fields["compressed_json_responses"].GetStringValue()
// Decode from base 64
data, err := base64.StdEncoding.DecodeString(s)
// Decompress
reader := bytes.NewReader(data)
r, err := zlib.NewReader(reader)
r.Close()
// r is now JSON encoded string of results
```

In theory, any of the three fields referenced above should have the required information, the difference is just in the encoding.
