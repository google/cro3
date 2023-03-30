// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

const (
	DefaultServerPort   = 80
	DefaultLogDirectory = "/tmp/provision/"

	CIPDVersionCodeTagName = "version_code"

	ADBVendorKeys               = "/var/lib/android_keys"
	ADBUnixSocketMountDirectory = "/run/arc/adb"
	GMSCorePackageName          = "com.google.android.gms"
	GMSCoreCIPDPath             = "chromiumos/infra/skylab/third_party/gmscore/"

	// DroneServiceAccountCreds is needed to upload APKs to Android Provisioning GSBucket.
	DroneServiceAccountCreds = "/creds/service_accounts/skylab-drone.json"
	GSImageBucketName        = "android-provisioning-images"
	GSPackageBucketName      = "android-provisioning-apks"
)

type ProvisionState int64

const (
	Prepare ProvisionState = iota
	OSFetch
	OSInstall
	PackageFetch
	PackageInstall
	PostInstall
)

var OSVersionToBuildIDMap = map[string]map[string]string{
	"10": {
		"sunfish": "QD4A.200805.003", // android-10.0.0_r45
	},
	"11": {
		"sunfish": "RQ3A.211001.001", // android-11.0.0_r46
		"redfin":  "RQ3A.211001.001", // android-11.0.0_r46
		"barbet":  "RD2A.211001.002", // android-11.0.0_r48
	},
	"12": {
		"sunfish": "SQ3A.220705.003.A1", // android-12.1.0_r11
		"redfin":  "SQ3A.220705.003.A1", // android-12.1.0_r11
		"barbet":  "SQ3A.220705.003.A1", // android-12.1.0_r11
		"oriole":  "SQ3A.220705.003.A1", // android-12.1.0_r11
		"raven":   "SQ3A.220705.003.A1", // android-12.1.0_r11
	},
	"13": {
		"sunfish": "TQ1A.230205.002", // android-13.0.0_r30
		"redfin":  "TQ1A.230205.002", // android-13.0.0_r30
		"barbet":  "TQ1A.230205.002", // android-13.0.0_r30
		"oriole":  "TQ1A.230205.002", // android-13.0.0_r30
		"raven":   "TQ1A.230205.002", // android-13.0.0_r30
	},
}

var OSVersionToGMSCorePlatformMap = map[string]string{
	"10": "prodpi",
	"11": "prodrvc",
	"12": "prodsc",
	"13": "prodsc",
}
