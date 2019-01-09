# Nebraska

Nebraska is a mock Omaha server built to facilitate testing of new DLCs
(DownLoadable Content) as well as update and install mechanisms in Chrome OS. It
is designed to be a lightweight, simple, and dependency-free standalone server
that can run on a host machine or DUT. Its single purpose is to respond
to update and install requests with Omaha-like responses based on some provided
metadata. All other related functions (i.e. generating payloads, transferring
files to a DUT, and serving the payloads themselves) must be handled
elsewhere.

## System Requirements

The entire server is implemented in `nebraska.py` and Nebraska does not depend
on anything outside of the Python standard libraries, so this file on its own
should be sufficient to run the server on any device with Python 2.7.10 or
newer.

WARNING: External dependencies should never be added to Nebraska!

## Payload Metadata

Nebraska handles requests based on the contents of install and update payload
directories. These directories should be populated with JSON files describing
the payloads you wish to make available. On receiving a request, Nebraska
searches the install or update payload directory as appropriate and formulates
a response based on metadata describing a matching payload if it can find one.
Nebraska expects at least one of these directories to be specified on startup.

### Metadata Format

The information in these files should be output by `paygen` when generating
a payload, and should have the following key-value pairs. See `sample.json` for
an example.

```
appid: The appid of the app provided by the payload.
name: Payload file name.
target_version: App target version.
is_delta: True iff the payload is a delta update.
source_version: The source version if the payload is a delta update.
size: Total size of the payload.
metadata_signature: Metadata signature.
metadata_size: Metadata size.
sha256_hex: SHA256 of the payload.
```

## Payload URLs

Nebraska does not serve the payload itself. It only provides payload metadata
formatted in an Omaha-like response along with a URL where the payload can be
found. The base of this URL can be given at startup.

The URL can be the URL of some other server that serves payloads, or can be a
file URL that points to a directory on the DUT containing update and install
payloads. When responding to a request, Nebraska constructs the URL it uses in
its response by appending "update" or "install" onto the end of the given base
URL depending on whether the request is for an update or install. The complete
URL for a payload can be constructed by concatenating the URL given in by
Nebraska with the name of the payload, which is also given in the response from
Nebraska. Giving a file URL in place of server URL is possible due to the fact
that update engine relies on `libcurl` to handle the payload transfer, which is
able to handle local files in the same way it handles remote URLs.

## Known Issues

### Lazy Version Checking

We only check the first two version components when doing version comparisons.
This is partially due to the way the final version component is constructed in
development builds vs. production builds.

### Detecting Update/Install

In order to signal that a DLC should be installed rather than updated, update
engine includes a request for the platform app without a request for an update.
This allows Omaha to differentiate between an update operation where Chrome OS
and all DLCs will be updated to a strictly greater version, and an install
operation where one or more DLCs of the same version as the platform app will be
installed. We currently decide whether a request is for an update or install
based on whether exactly one other app (which we assume to be the platform app)
the request list does not have an associated update request.
