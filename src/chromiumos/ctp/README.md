## CTP Client Library
This simplies the process of calling CTP programmatically

## Testing
`go test ./...`

## Usage
### Scheduling Tests via CTP

To schedule tests, create a CTPBuilder object and then call it's `ScheduleCTPBuild` method. This will return a Build object which you can use to track the progress of the test

```
tp := &test_platform.Request_TestPlan{
    Suite: []*test_platform.Request_Suite{&test_platform.Request_Suite{Name: "rlz"}},
}

ctp := &builder.CTPBuilder{
    Image:      "zork-release/R107-15117.103.0",
    Board:      "zork",
    Pool:       "xolabs-satlab",
    TestPlan:   tp,
}

b, err := ctp.ScheduleCTPBuild(c)
```

Note that the default `AuthOptions` will likely be unsuitable since you will need to match the scope and location of the auth a user logged in with. Therefore you will likely need to override it. 