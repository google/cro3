# End-to-End testing instruction:

## Requirements:
To run end-to-end testing locally, you will need <b>cipd access</b> on your machine and <b>drone service account</b> (or direct access to `android-provisioning/android-provisioning-apks` gs bucket).</br>
You will also need a valid ssh config to connect to the labstation (see ssh config section).

## Testing:
End to end testing is done over ssh tunneling to labstation (dutServer).

1. Establish the ssh tunnel:

 `ssh -f -N -L 2500:<dut_ip>:22 root@<host>`

2. In ‘common/constants.go’ change the `DroneServiceAccountCreds` to the local path to drone service account.

3. Fill out the `input_example.json` to meet your requirements.
- "dut" // DUT information. Required.
  - "id" // DUT id, needed for output file. Required.
  - "android" // DUT type. Required.
    - "associatedHostname" // Hostname of the device that the Android DUT is attached to. Optional.
    - "name" // DUT name. Optional.
    - "serialNumber" // string created by adb to uniquely identify the device. Required.
  - "cacheServer" // Cache server for downloading artifacts. Optional.
- "provisionState" // List of packages to install. Required.
  - "id": {"value": "provision_state_id"} // Provision state id (string). Required.
  - "cipdPackages" // List of CIPD packages to install. Required.
    - "name" // CIPD package name. Required.
    - "instanceId" // CIPD package ID. Required.
    - "serviceUrl" // CIPD service URL. Optional. chrome-infra-packages.appspot.com by default.
    - "androidPackage" // Type of the package (1 - GMS Core). Required.
    - "apkDetails" // Package details. Optional.
- "dutServer" // Address of the DUT server. Required.

4. `./android-provision cli -input input_example.json -output output.json`

## Notes:
- Make sure the dutServer field is set to `127.0.0.1` and the port used in the ssh tunnel corresponds to the port in your input file. Passing `127.0.0.1` as the address will automatically start the application in testing mode and use the ssh connection to reach the host.
- Because this implementation focuses on testing `android-provision` service, we are not doing any caching. Instead, apk files are downloaded locally and copied remotely to labstation everytime the service is run. Depending on the size of the apk, this step alone could take 7-10 minutes.

## ssh config:
- connect to [labstation](https://yaqs.corp.google.com/eng/q/4714681670647676928).
- connect to localhost:
```
Host 127.0.0.1 localhost
  CanonicalizeHostname yes
  PreferredAuthentications publickey
  StrictHostKeyChecking no
  User root
  IdentityFile %d/.ssh/testing_rsa
```
