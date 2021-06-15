# Nebraska

[TOC]

## Introduction

Nebraska is a mock Omaha server built to facilitate testing of Auto Updates as
well as DLC (DownLoadable Content) update and install mechanisms in Chrome
OS. It is designed to be a lightweight, simple, and dependency-free standalone
server that can run on a host machine or DUT. Its single purpose is to respond
to update and install requests with Omaha-like responses based on some provided
metadata. All other related functions (i.e. generating payloads, transferring
files to a DUT, and serving the payloads themselves) must be handled elsewhere.

## System Requirements

The entire server is implemented in `nebraska.py` and it does not depend on
anything outside of the Python standard libraries (WARNING: and it would be
better to be kept that way), so this file on its own should be sufficient to run
the server on any device with Python 3.6 or newer.

WARNING: External dependencies should never be added to Nebraska!

## Payload Metadata

Nebraska handles requests based on the contents of install and update payload
directories. These directories should be populated with JSON files describing
the payloads you wish to make available. On receiving a request, Nebraska
searches the install or update payload directory as appropriate and formulates
a response based on metadata describing a matching payload if it can find one.
Nebraska expects at least one of these directories to be specified on startup.

### Metadata Format

The information in these files should be output by [paygen] when generating a
payload, and should have the following key-value pairs:

*   `appid` - The appid of the app provided by the payload.
*   `target_version` - App target version.
*   `is_delta` - True iff the payload is a delta update.
*   `source_version` - The source version if the payload is a delta update.
*   `size` - Total size of the payload.
*   `metadata_signature` - Metadata signature.
*   `metadata_size` - Metadata size.
*   `sha256_hex` - SHA256 of the payload.
*   `version` - The version of this file format.

An example `sample.json`:
```json
{
  "appid": "{F67500C1-C6D8-5287-E4EC-F9BBB4AEE5C5}",
  "target_version": "10895.78.0",
  "is_delta": true,
  "source_version": "10000.0.0",
  "size": 1069749941,
  "metadata_signature": "Dr4RFXYgcfvFHV/0VRQs+SCQmz15Sk04LLEDswtvng8BqNbBXA7VvPUhpCgX5T/t7cwPxTUHJVtxIREuBZpyIQxJQFZATspaClelpKBwadQzj7dpfShLpcbdlfM8qbLjIbXfC2Vymw03Mwf38lm0Fm75SANSTW9S4arPDf3sy9YGuqesnEJXyT3ZSGyK+Xto79zlURUXCgmia6t7MaJE3ZbCdeF4EiEMPDsipqj9ggmKwiCdUl2+RxTznX/015XFiBhogLrx9RCPHTR8nLz0H9RcRhIvMd+8g4kHUZTDvjCvG5EZHpIKk8FK8z0zY/LWVr738evwuNNwyKIazkQBTA==",
  "metadata_size": 50377,
  "sha256_hex": "886fd274745b4fa8d1f253cff11242fac07a29522b1bb9e028ab1480353d3160",
  "version": 2
}
```

## Payload URLs

Nebraska does not serve the payload itself. It only provides payload metadata
formatted in an Omaha-like response along with a URL where the payload can be
found. The base of this URL can be given at startup.

The URL can be the URL of some other server that serves payloads, or can be a
file URL that points to a directory on the DUT containing update and install
payloads. The complete URL for a payload is constructed by concatenating the
URL given in by Nebraska with the name of the payload, which is also given in
the response from Nebraska. Giving a file URL in place of server URL is possible
due to the fact that update engine relies on `libcurl` to handle the payload
transfer, which is able to handle local files in the same way it handles remote
URLs.

## Configure Nebraska at Runtime

Almost all our Auto Update tests require the nebraska be configured with
specific parameters/behaviors either at runtime or during start up. There are a
few ways to do this but most of them are going to be deprecated except one. So,
when adding a new behavior flag to nebraska, make sure the correct mechanism is
used. The current best supported method is through the `update_config` API. You
can send an HTTP `POST` request which has a JSON body. Look at [`Config`] class
for the list of available flags that can be used to change the Nebraska's
behavior. For example `config.json`:

```json
{
  "critical_update": true,
  "no_update": false,
  "eol_date": 1234
}
```

To update the config do:
```bash
$ curl -X POST -d @config.json http://localhost:{port}/update_config
```

If using the nebraska.py directly as a library, you can call the `UpdateConfig`
function directly at anytime to configure its behavior.

Other methods of configuring the Nebraska's behavior is using either
program/startup flags like (not preferred):

```bash
$ nebraska.py --foo-flag
```

Or you can pass the configs as query string (not preferred either and being
deprecated):

```bash
$ curl http://localhost:{port}/update/?critical_update=True&no_update=False
```

## Running Nebraska on test images

`nebraska.py` is enabled as a system service that is started before UpdateEngine
is up. However, it only starts on test images and only if the config file (a
JSON file) for nebraska is created in `/usr/local/nebraska/config.json`. This
file is the same JSON data that is passed in an HTTP POST request discussed in
[this](#configure-nebraska-at-runtime) section.

It can also be manually started with `$ start nebraska` or stopped with `$ stop
nebraska` commands.

## Testing with Nebraska

In order to run local tests with nebraska (either on DUT or workstation), one
can first run nebraska first:

```bash
# <payloads dir> and <metadata dir> can be the same.
$ nebraska.py --update-metadata=/tmp/<metadata dir> --log-file=stdout --update-payloads-address file:///tmp/<payloads dir>
```
Then, configure nebraska with behaviors you want:

```bash
$ curl -X POST -d '{"critical_update": true}' http://localhost:$(cat /run/nebraska/port)/update_config
```

At this point the nebraska.py instance is ready for interaction. You can start
an update check with UpdateEngine such as:

```bash
$ update_engine_client --omaha_url="http://localhost:$(cat /run/nebraska/port)/update" --update
```

And look at the UpdateEngine logs at `/var/log/update_engine.log`.

## Known Issues

### Detecting Update/Install

In order to signal that a DLC should be installed rather than updated, update
engine includes a request for the platform app without a request for an update.
This allows Omaha to differentiate between an update operation where Chrome OS
and all DLCs will be updated to a strictly greater version, and an install
operation where one or more DLCs of the same version as the platform app will be
installed. We currently decide whether a request is for an update or install
based on whether exactly one other app (which we assume to be the platform app)
the request list does not have an associated update request.

[paygen]: https://chromium.googlesource.com/chromiumos/chromite/+/HEAD/lib/paygen/
[`Config`]: nebraska.py#842
