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

	// DroneServiceAccountCreds is needed to upload APKs to Android Provisioning GSBucket.
	DroneServiceAccountCreds = "/creds/service_accounts/skylab-drone.json"
	GSBucketName             = "android-provisioning-apks"
)
