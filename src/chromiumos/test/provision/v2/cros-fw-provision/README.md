# cros-fw-provision

This directory contains cros-fw-provision: a service for preparing
devices-under-test with specific application processor ("AP") and embedded
controller ("EC") firmware ("fw") builds.  Preparing devices with specific
builds is called "provisioning".

## Launching

A prebuilt cros-fw-provision will be available in the chroot.  To launch it,
execute, `cros-fw-provision server` or `cros-fw-provision cli`.  `server` spins
up a service and waits for a gRPC request to come over the network before
provisioning starts.  `cli` immediately executes the request, which is required
to be passed in during launch.

## Dependencies

cros-fw-provision expects cros-cache, and either cros-dut or cros-servod, to be
running.

In the lab, the cache server should already be up.  Local runs of
cros-fw-provision will need the cache server started.

`cros-dut` is needed if provisioning directly.

`cros-servod` is needed if provisioning over
[servo]("https://chromium.googlesource.com/chromiumos/third_party/hdctools/+/HEAD/README.md").
