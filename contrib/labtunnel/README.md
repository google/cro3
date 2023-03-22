# `labtunnel`
The `labtunnel` utility provides a CLI for commonly preformed tunneling
related commands necessary for accessing and testing with lab devices. Are you
tired of having to make ssh tunnels to DUTs so that you can run `tast`? Do you
want to remote desktop into a DUT but do not want to manage all that is
necessary to do that yourself every time? Use `labtunnel` today to do all that
and more with a simple single command!

## Installation
Use the `./install.sh` bash script to build and install labtunnel so
that it may be run as a regular command, `labtunnel`. The built copy will reside
at `./bin/labtunnel`.

Note: The installation script is meant to be run on your main system, not in a
chroot.

Note: Syncing an updated version of this source repository will not
automatically rebuild an updated version of `labtunnel`. To update your local
build of `labtunnel`, simply re-run `./install.sh` (or `./build.sh`) to rebuild
it.

### install_labtunnel.sh help
```text
$ bash ./install.sh help
Usage: install.sh [options]

Options:
 --dir|-d <path>    Path to directory where labtunnel is to be installed, which
                    should be in your $PATH (default = '~/lib/depot_tools').
```

## Usage
Run `labtunnel --help` to print its usage and `labtunnel <command> --help` to
print command-specific usage.

Note: The `labtunnel` command is meant to be run on the workstation that you want to
give access to lab devices to, and not inside a chroot.

```text
$ labtunnel -h

Create and maintain ssh tunnels for common lab environments easily.

To stop a running labtunnel command, send the SIGINT signal to the process. If
running labtunnel in a terminal environment, you can do this with CTRL+C.

All hosts that are accessed or tunneled through with any labtunnel command must
be configured so that they can be accessed without a username or password
prompt. This can be done securely by configuring your system's ssh settings to
use private keys for the given host. Temporary/test ssh configurations can also
be done directly with labtunnel with the "-o" flag to pass ssh config options
to the ssh command calls.

All tunnels are destroyed upon stopping labtunnel, and are restarted if
interrupted by a remote device reboot.

When a local port is forwarded to remote port, the next available port starting
at 2200 is used. The start port can be adjusted with --local-port-start. Used
ports will be freed upon stopping labtunnel.

Usage:
  labtunnel [command]

Available Commands:
  btpeers     Ssh tunnel to dut and its bluetooth peers.
  callbox     Ssh tunnel to dut, callbox manager, and callbox.
  chameleon   Ssh tunnel to dut and its chameleon device.
  completion  Generate the autocompletion script for the specified shell
  dut         Ssh tunnel to dut.
  dutvnc      Starts and connects to a VNC server on dut for remote GUI access.
  help        Help about any command
  hosts       Tunnel to different types of hosts without any automatic hostname resolution.
  sshwatcher  Ssh tunnel to host(s).
  wificell    Ssh tunnel to the dut, pcap, and router of a wificell.

Flags:
  -h, --help                          help for labtunnel
  -p, --local-port-start int          Initial local port to forward to tunnel (default 2200)
      --remote-port-chameleond int    Remote port for accessing the chameleond service on btpeers and chameleon devices (default 9992)
      --remote-port-ssh int           Remote port to forward ssh tunnels to (default 22)
  -o, --ssh-options strings           ssh options for all ssh commands (default [StrictHostKeyChecking=no,ExitOnForwardFailure=yes,ForkAfterAuthentication=no,LogLevel=ERROR,ControlMaster=auto,ControlPersist=3600,ControlPath=/tmp/ssh-labtunnel-%C,ServerAliveCountMax=10,ServerAliveInterval=1,VerifyHostKeyDNS=no,CheckHostIP=no,UserKnownHostsFile=/dev/null,Compression=yes])
      --ssh-retry-delay-seconds int   Time to wait before retrying failed ssh command calls (default 10)
  -v, --version                       version for labtunnel

Use "labtunnel [command] --help" for more information about a command.
```


## Examples
The following examples show the normal usage for different supported commands.
Once the tunneling is complete the expected behavior is that you keep the process
running until you no longer need the tunnels. Each example process is stopped by
sending SIGINT with ^C (ctr+c/cmd+c) to the terminal.

### wificell
```text
$ labtunnel wificell chromeos1-dev-host1
15:15:18.566467 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
15:15:18.567279 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
15:15:18.581083 starting ssh exec "TUNNEL-ROUTER-1   [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]"
15:15:18.581478 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2201:localhost:22 chromeos1-dev-host1-router sleep 8h
15:15:18.591454 starting ssh exec "TUNNEL-PCAP-1     [localhost:2202 -> chromeos1-dev-host1-pcap -> localhost:22]"
15:15:18.591701 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2202:localhost:22 chromeos1-dev-host1-pcap sleep 8h
15:15:19.591557 Example Tast call (in chroot): tast run -var=router=localhost:2201 -var=pcap=localhost:2202 localhost:2200 <test>
15:15:19.591638 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
  TUNNEL-PCAP-1     [localhost:2202 -> chromeos1-dev-host1-pcap -> localhost:22]  RUNNING
  TUNNEL-ROUTER-1   [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]  RUNNING
^C15:15:20.622671 received SIGINT, cancelling operations
15:15:20.622859 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
  TUNNEL-PCAP-1     [localhost:2202 -> chromeos1-dev-host1-pcap -> localhost:22]  CLOSED
  TUNNEL-ROUTER-1   [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]  CLOSED
```
```text
$ labtunnel wificell chromeos1-dev-host1 --routers 1 --pcaps 1 --btpeers 1
12:47:27.513469 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
12:47:27.514066 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 24h
12:47:27.534781 starting ssh exec "TUNNEL-ROUTER-1   [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]"
12:47:27.535628 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2201:localhost:22 chromeos1-dev-host1-router sleep 24h
12:47:27.552675 starting ssh exec "TUNNEL-PCAP-1     [localhost:2202 -> chromeos1-dev-host1-pcap -> localhost:22]"
12:47:27.553006 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2202:localhost:22 chromeos1-dev-host1-pcap sleep 24h
12:47:27.571573 starting ssh exec "TUNNEL-BTPEER-1   [localhost:2203 -> chromeos1-dev-host1-btpeer1 -> localhost:22]"
12:47:27.571810 SSH[4]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2203:localhost:22 chromeos1-dev-host1-btpeer1 sleep 24h
12:47:28.572109 Example Tast call (in chroot): tast run -var=router=localhost:2201 -var=pcap=localhost:2202 localhost:2200 <test>
12:47:28.572202 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2203 -> chromeos1-dev-host1-btpeer1 -> localhost:22]  RUNNING
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
  TUNNEL-PCAP-1     [localhost:2202 -> chromeos1-dev-host1-pcap -> localhost:22]  RUNNING
  TUNNEL-ROUTER-1   [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]  RUNNING
^C12:47:31.033286 received SIGINT, cancelling operations
12:47:31.033895 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2203 -> chromeos1-dev-host1-btpeer1 -> localhost:22]  CLOSED
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
  TUNNEL-PCAP-1     [localhost:2202 -> chromeos1-dev-host1-pcap -> localhost:22]  CLOSED
  TUNNEL-ROUTER-1   [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]  CLOSED
```

### callbox
```text
$ labtunnel callbox chromeos1-donutlab-callbox1-host1 access@chromeos1-proxy chromeos1-donutlab-callbox1.cros
15:16:21.143751 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos1-donutlab-callbox1-host1 -> localhost:22]"
15:16:21.144199 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-donutlab-callbox1-host1 sleep 8h
15:16:21.173143 starting ssh exec "TUNNEL-CALLBOX_MANAGER [localhost:2202 -> access@chromeos1-proxy -> localhost:5000]"
15:16:21.173445 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2202:localhost:5000 access@chromeos1-proxy sleep 8h
15:16:21.184626 starting ssh exec "TUNNEL-CALLBOX    [localhost:2203 -> access@chromeos1-proxy -> chromeos1-donutlab-callbox1.cros:5025]"
15:16:21.184815 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2203:chromeos1-donutlab-callbox1.cros:5025 access@chromeos1-proxy sleep 8h
15:16:22.185059 Example Tast call (in chroot): tast run -var=callbox=localhost:2203 -var=callboxManager=localhost:2202 localhost:2200 <test>
15:16:22.185154 ssh state summary:
  TUNNEL-CALLBOX    [localhost:2203 -> access@chromeos1-proxy -> chromeos1-donutlab-callbox1.cros:5025]  RUNNING
  TUNNEL-CALLBOX_MANAGER [localhost:2202 -> access@chromeos1-proxy -> localhost:5000]  RUNNING
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-donutlab-callbox1-host1 -> localhost:22]  RUNNING
15:16:23.284402 SSH[2]: ControlSocket /tmp/ssh-labtunnel-1d98ebacd0da22c935115711ccf10236c3803cce already exists, disabling multiplexing
^C15:16:36.886683 received SIGINT, cancelling operations
15:16:36.887779 ssh state summary:
  TUNNEL-CALLBOX    [localhost:2203 -> access@chromeos1-proxy -> chromeos1-donutlab-callbox1.cros:5025]  CLOSED
  TUNNEL-CALLBOX_MANAGER [localhost:2202 -> access@chromeos1-proxy -> localhost:5000]  CLOSED
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-donutlab-callbox1-host1 -> localhost:22]  CLOSED
```

### dut
```text
$ labtunnel dut chromeos1-dev-host1
15:17:03.856417 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
15:17:03.856744 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
15:17:04.856995 Example Tast call (in chroot): tast run localhost:2200 <test>
15:17:04.857032 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
^C15:17:07.228685 received SIGINT, cancelling operations
15:17:07.228788 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
```
```text
$ labtunnel dut crossk-chromeos1-dev-host1
15:17:30.455496 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
15:17:30.455825 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
15:17:31.456072 Example Tast call (in chroot): tast run localhost:2200 <test>
15:17:31.456107 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
^C15:17:34.409089 received SIGINT, cancelling operations
15:17:34.409182 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
```
Use leased DUT with only multiple DUTs leased
```text
$ labtunnel dut leased
Found 2 leased DUTs please select the DUT you would like to tunnel to:
0: chromeos8-row12-rack2-host51
1: chromeos15-row6-rack10-host7

Select from 0-1: 0
16:15:12.656539 Using user selected leased DUT: chromeos8-row12-rack2-host51
16:15:12.801205 starting ssh exec "TUNNEL-DUT-1      [localhost:2212 -> chromeos8-row12-rack2-host51 -> localhost:22]"
16:15:12.801327 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2212:localhost:22 chromeos8-row12-rack2-host51 sleep 8h
16:15:13.801444 Example Tast call (in chroot): tast run localhost:2212 <test>
16:15:13.801466 ssh state summary:
  TUNNEL-DUT-1      [localhost:2212 -> chromeos8-row12-rack2-host51 -> localhost:22]  RUNNING
```
Use leased DUT with only one DUT leased
```text
$ labtunnel dut leased
08:04:45.529115 Defaulting to only leased DUT: chromeos3-row1-rack1-host5
08:04:45.538693 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos3-row1-rack1-host5 -> localhost:22]"
08:04:45.538823 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos3-row1-rack1-host5 sleep 8h
08:04:46.538933 Example Tast call (in chroot): tast run localhost:2200 <test>
08:04:46.538953 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos3-row1-rack1-host5 -> localhost:22]  RUNNING
```

### dutvnc
```text
$ labtunnel dutvnc chromeos1-dev-host1
17:54:54.660120 starting ssh exec "DUT-VNC"
17:54:54.660631 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" chromeos1-dev-host1 kmsvnc
17:54:54.675322 starting ssh exec "TUNNEL-DUT-VNC    [localhost:2200 -> chromeos1-dev-host1 -> localhost:5900]"
17:54:54.675382 DUT VNC available at localhost:2200
17:54:54.675654 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:5900 chromeos1-dev-host1 sleep 8h
17:54:56.642424 SSH[1]: 2022-06-23T00:54:56.636527Z INFO kmsvnc: [kmsvnc.cc(201)] Starting with CRTC size of: 1920 1080
2022-06-23T00:54:56.636635Z INFO kmsvnc: [kmsvnc.cc(203)] with VNC view-port size of: 1920 1080
17:54:56.646092 SSH[1]: libEGL warning: MESA-LOADER: failed to open vgem: /usr/lib64/dri/vgem_dri.so: cannot open shared object file: No such file or directory (search paths /usr/lib64/dri, suffix _dri)

17:54:56.674651 SSH[1]: 22/06/2022 17:54:56 ListenOnTCPPort: Address already in use
17:54:56.744572 SSH[2]: ControlSocket /tmp/ssh-labtunnel-ac5abaa672652cdbddbcb8823c425469830288f0 already exists, disabling multiplexing
17:54:59.677720 ssh state summary:
  DUT-VNC  RUNNING
  TUNNEL-DUT-VNC    [localhost:2200 -> chromeos1-dev-host1 -> localhost:5900]  RUNNING
17:54:59.692010 TIGERVNC:
TigerVNC Viewer 64-bit v1.12.0
Built on: 2022-03-25 17:06
Copyright (C) 1999-2021 TigerVNC Team and many others (see README.rst)
See https://www.tigervnc.org for information on TigerVNC.
^C17:55:06.819177 received SIGINT, cancelling operations
17:55:06.819300 Error running command "xtigervncviewer": context canceled
17:55:06.819878 ssh state summary:
  DUT-VNC  CLOSED
  TUNNEL-DUT-VNC    [localhost:2200 -> chromeos1-dev-host1 -> localhost:5900]  CLOSED
```

### btpeers
```text
$ labtunnel btpeers crossk-chromeos15-row8-rack1-host4
12:48:05.579940 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row8-rack1-host4 -> localhost:22]"
12:48:05.580644 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos15-row8-rack1-host4 sleep 24h
12:48:05.593527 starting ssh exec "TUNNEL-BTPEER-1   [localhost:2201 -> chromeos15-row8-rack1-host4-btpeer1 -> localhost:22]"
12:48:05.593832 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2201:localhost:22 chromeos15-row8-rack1-host4-btpeer1 sleep 24h
12:48:06.594169 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2201 -> chromeos15-row8-rack1-host4-btpeer1 -> localhost:22]  RUNNING
  TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row8-rack1-host4 -> localhost:22]  RUNNING
^C12:48:09.420183 received SIGINT, cancelling operations
12:48:09.420283 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2201 -> chromeos15-row8-rack1-host4-btpeer1 -> localhost:22]  CLOSED
  TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row8-rack1-host4 -> localhost:22]  CLOSED
```
```text
$ labtunnel btpeers crossk-chromeos15-row8-rack1-host4 4
12:48:29.965128 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row8-rack1-host4 -> localhost:22]"
12:48:29.965707 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos15-row8-rack1-host4 sleep 24h
12:48:29.981905 starting ssh exec "TUNNEL-BTPEER-1   [localhost:2201 -> chromeos15-row8-rack1-host4-btpeer1 -> localhost:22]"
12:48:29.982262 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2201:localhost:22 chromeos15-row8-rack1-host4-btpeer1 sleep 24h
12:48:29.995841 starting ssh exec "TUNNEL-BTPEER-2   [localhost:2202 -> chromeos15-row8-rack1-host4-btpeer2 -> localhost:22]"
12:48:29.997159 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2202:localhost:22 chromeos15-row8-rack1-host4-btpeer2 sleep 24h
12:48:30.010030 starting ssh exec "TUNNEL-BTPEER-3   [localhost:2203 -> chromeos15-row8-rack1-host4-btpeer3 -> localhost:22]"
12:48:30.010413 SSH[4]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2203:localhost:22 chromeos15-row8-rack1-host4-btpeer3 sleep 24h
12:48:30.033923 starting ssh exec "TUNNEL-BTPEER-4   [localhost:2204 -> chromeos15-row8-rack1-host4-btpeer4 -> localhost:22]"
12:48:30.034196 SSH[5]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2204:localhost:22 chromeos15-row8-rack1-host4-btpeer4 sleep 24h
12:48:31.034502 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2201 -> chromeos15-row8-rack1-host4-btpeer1 -> localhost:22]  RUNNING
  TUNNEL-BTPEER-2   [localhost:2202 -> chromeos15-row8-rack1-host4-btpeer2 -> localhost:22]  RUNNING
  TUNNEL-BTPEER-3   [localhost:2203 -> chromeos15-row8-rack1-host4-btpeer3 -> localhost:22]  RUNNING
  TUNNEL-BTPEER-4   [localhost:2204 -> chromeos15-row8-rack1-host4-btpeer4 -> localhost:22]  RUNNING
  TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row8-rack1-host4 -> localhost:22]  RUNNING
^C12:48:31.444833 received SIGINT, cancelling operations
12:48:31.445079 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2201 -> chromeos15-row8-rack1-host4-btpeer1 -> localhost:22]  CLOSED
  TUNNEL-BTPEER-2   [localhost:2202 -> chromeos15-row8-rack1-host4-btpeer2 -> localhost:22]  CLOSED
  TUNNEL-BTPEER-3   [localhost:2203 -> chromeos15-row8-rack1-host4-btpeer3 -> localhost:22]  CLOSED
  TUNNEL-BTPEER-4   [localhost:2204 -> chromeos15-row8-rack1-host4-btpeer4 -> localhost:22]  CLOSED
  TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row8-rack1-host4 -> localhost:22]  CLOSED
```

### sshwatcher
```text
$ labtunnel sshwatcher chromeos1-dev-host1
15:22:02.247115 starting ssh exec "TUNNEL-SSH-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
15:22:02.247625 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
15:22:03.247903 ssh state summary:
  TUNNEL-SSH-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
^C15:22:06.216311 received SIGINT, cancelling operations
15:22:06.216443 ssh state summary:
  TUNNEL-SSH-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
```
```text
$ labtunnel sshwatcher chromeos1-dev-host1 chromeos1-dev-host1-router chromeos1-dev-host2
15:22:59.090184 starting ssh exec "TUNNEL-SSH-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
15:22:59.090569 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
15:22:59.165128 starting ssh exec "TUNNEL-SSH-2      [localhost:2206 -> chromeos1-dev-host1-router -> localhost:22]"
15:22:59.165390 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2206:localhost:22 chromeos1-dev-host1-router sleep 8h
15:22:59.179911 starting ssh exec "TUNNEL-SSH-3      [localhost:2207 -> chromeos1-dev-host2 -> localhost:22]"
15:22:59.180145 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2207:localhost:22 chromeos1-dev-host2 sleep 8h
15:23:00.180456 ssh state summary:
  TUNNEL-SSH-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
  TUNNEL-SSH-2      [localhost:2206 -> chromeos1-dev-host1-router -> localhost:22]  RUNNING
  TUNNEL-SSH-3      [localhost:2207 -> chromeos1-dev-host2 -> localhost:22]  RUNNING
^C15:23:03.144232 received SIGINT, cancelling operations
15:23:03.144381 ssh state summary:
  TUNNEL-SSH-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
  TUNNEL-SSH-2      [localhost:2206 -> chromeos1-dev-host1-router -> localhost:22]  CLOSED
  TUNNEL-SSH-3      [localhost:2207 -> chromeos1-dev-host2 -> localhost:22]  CLOSED
```


### chameleon
```text
$ labtunnel chameleon crossk-chromeos15-row1-metro11-host2
15:23:51.692896 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row1-metro11-host2 -> localhost:22]"
15:23:51.693293 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos15-row1-metro11-host2 sleep 8h
15:23:51.796860 starting ssh exec "TUNNEL-CHAMELEON-1 [localhost:2207 -> chromeos15-row1-metro11-host2-chameleon -> localhost:9992]"
15:23:51.797051 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2207:localhost:9992 chromeos15-row1-metro11-host2-chameleon sleep 8h
15:23:52.797299 ssh state summary:
  TUNNEL-CHAMELEON-1 [localhost:2207 -> chromeos15-row1-metro11-host2-chameleon -> localhost:9992]  RUNNING
  TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row1-metro11-host2 -> localhost:22]  RUNNING
^C15:23:54.778548 received SIGINT, cancelling operations
15:23:54.778670 ssh state summary:
  TUNNEL-CHAMELEON-1 [localhost:2207 -> chromeos15-row1-metro11-host2-chameleon -> localhost:9992]  CLOSED
  TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row1-metro11-host2 -> localhost:22]  CLOSED
```

### hosts
The `hosts` subcommand is great for connecting to an arbitrary amount of hosts
of varying types that may not follow normal lab naming conventions. Hostnames
are used as passed without modifications, and can be IPs.

```text
$ labtunnel hosts --help

Tunnel to different types of hosts without any automatic hostname resolution.

To specify a host, use one of the flags with a given hostname and a tunnel will
be created to that host as expected for that type of host. Multiple hosts
can be tunneled to at the same time, even for the same type, by providing
multiple flags (see example calls below).

Hostnames provided will be the exact hostnames passed to the ssh command call,
and can be IP addresses. Tunnels will only be created for the hosts specified.

Example calls:
$ labtunnel hosts --dut <dut_host>
$ labtunnel hosts --dut <dut1_host> --dut <dut2_host>
$ labtunnel hosts --dut <dut_host> --router <router_host> --pcap <pcap_host>
$ labtunnel hosts --dut <dut_host> --btpeer <btpeer1_host> --btpeer <btpeer2_host>
$ labtunnel hosts --dut <dut_host> --chameleon <chameleon_host>
$ labtunnel hosts --ssh <host>
$ labtunnel hosts --chameleond <host>

Usage:
  labtunnel hosts [flags]

Flags:
      --btpeer stringArray       Btpeer hosts to tunnel to
      --chameleon stringArray    Chameleon hosts to tunnel to
      --chameleond stringArray   Hosts to tunnel to their chameleond port
      --dut stringArray          Dut hosts to tunnel to
  -h, --help                     help for hosts
      --pcap stringArray         Pcap hosts to tunnel to
      --router stringArray       Router hosts to tunnel to
      --ssh stringArray          Hosts to tunnel to their ssh port

Global Flags:
  -p, --local-port-start int          Initial local port to forward to tunnel (default 2200)
      --remote-port-chameleond int    Remote port for accessing the chameleond service on btpeers and chameleon devices (default 9992)
      --remote-port-ssh int           Remote port to forward ssh tunnels to (default 22)
  -o, --ssh-options strings           ssh options for all ssh commands (default [StrictHostKeyChecking=no,ExitOnForwardFailure=yes,ForkAfterAuthentication=no,LogLevel=ERROR,ControlMaster=auto,ControlPersist=3600,ControlPath=/tmp/ssh-labtunnel-%C,ServerAliveCountMax=10,ServerAliveInterval=1,VerifyHostKeyDNS=no,CheckHostIP=no,UserKnownHostsFile=/dev/null,Compression=yes])
      --ssh-retry-delay-seconds int   Time to wait before retrying failed ssh command calls (default 10)
```
```text
$ labtunnel hosts --dut chromeos1-dev-host1
15:30:42.095985 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
15:30:42.096315 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
15:30:43.096570 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
^C15:30:44.508654 received SIGINT, cancelling operations
15:30:44.508773 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
```
```text
$ labtunnel hosts --dut chromeos1-dev-host1 --dut chromeos1-dev-host2
15:32:03.749978 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
15:32:03.750479 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
15:32:03.864530 starting ssh exec "TUNNEL-DUT-2      [localhost:2208 -> chromeos1-dev-host2 -> localhost:22]"
15:32:03.864747 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2208:localhost:22 chromeos1-dev-host2 sleep 8h
15:32:04.864955 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
  TUNNEL-DUT-2      [localhost:2208 -> chromeos1-dev-host2 -> localhost:22]  RUNNING
^C15:32:06.758604 received SIGINT, cancelling operations
15:32:06.758710 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
  TUNNEL-DUT-2      [localhost:2208 -> chromeos1-dev-host2 -> localhost:22]  CLOSED
```
```text
$ labtunnel hosts --dut chromeos1-dev-host1 --router chromeos1-dev-host1-router --pcap chromeos1-dev-host1-pcap
15:33:44.297583 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
15:33:44.297983 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
15:33:44.417969 starting ssh exec "TUNNEL-ROUTER-1   [localhost:2208 -> chromeos1-dev-host1-router -> localhost:22]"
15:33:44.418288 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2208:localhost:22 chromeos1-dev-host1-router sleep 8h
15:33:44.432527 starting ssh exec "TUNNEL-PCAP-1     [localhost:2209 -> chromeos1-dev-host1-pcap -> localhost:22]"
15:33:44.432739 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2209:localhost:22 chromeos1-dev-host1-pcap sleep 8h
15:33:45.432941 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
  TUNNEL-PCAP-1     [localhost:2209 -> chromeos1-dev-host1-pcap -> localhost:22]  RUNNING
  TUNNEL-ROUTER-1   [localhost:2208 -> chromeos1-dev-host1-router -> localhost:22]  RUNNING
^C15:33:47.570480 received SIGINT, cancelling operations
15:33:47.570573 ssh state summary:
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
  TUNNEL-PCAP-1     [localhost:2209 -> chromeos1-dev-host1-pcap -> localhost:22]  CLOSED
  TUNNEL-ROUTER-1   [localhost:2208 -> chromeos1-dev-host1-router -> localhost:22]  CLOSED
```
```text
$ labtunnel hosts --dut chromeos1-dev-host1 --btpeer chromeos1-dev-host1-btpeer1 --btpeer chromeos1-dev-host1-btpeer2
12:49:36.901401 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
12:49:36.901812 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 24h
12:49:36.923469 starting ssh exec "TUNNEL-BTPEER-1   [localhost:2201 -> chromeos1-dev-host1-btpeer1 -> localhost:22]"
12:49:36.923755 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2201:localhost:22 chromeos1-dev-host1-btpeer1 sleep 24h
12:49:36.942751 starting ssh exec "TUNNEL-BTPEER-2   [localhost:2202 -> chromeos1-dev-host1-btpeer2 -> localhost:22]"
12:49:36.943100 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2202:localhost:22 chromeos1-dev-host1-btpeer2 sleep 24h
12:49:37.943446 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2201 -> chromeos1-dev-host1-btpeer1 -> localhost:22]  RUNNING
  TUNNEL-BTPEER-2   [localhost:2202 -> chromeos1-dev-host1-btpeer2 -> localhost:22]  RUNNING
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
^C12:49:39.783457 received SIGINT, cancelling operations
12:49:39.783595 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2201 -> chromeos1-dev-host1-btpeer1 -> localhost:22]  CLOSED
  TUNNEL-BTPEER-2   [localhost:2202 -> chromeos1-dev-host1-btpeer2 -> localhost:22]  CLOSED
  TUNNEL-DUT-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
```
```text
$ labtunnel hosts --dut chromeos15-row1-metro11-host2 --chameleon chromeos15-row1-metro11-host2-chameleon
15:36:18.819905 starting ssh exec "TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row1-metro11-host2 -> localhost:22]"
15:36:18.820375 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos15-row1-metro11-host2 sleep 8h
15:36:18.951500 starting ssh exec "TUNNEL-CHAMELEON-1 [localhost:2209 -> chromeos15-row1-metro11-host2-chameleon -> localhost:9992]"
15:36:18.951737 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2209:localhost:9992 chromeos15-row1-metro11-host2-chameleon sleep 8h
15:36:19.952043 ssh state summary:
  TUNNEL-CHAMELEON-1 [localhost:2209 -> chromeos15-row1-metro11-host2-chameleon -> localhost:9992]  RUNNING
  TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row1-metro11-host2 -> localhost:22]  RUNNING
^C15:36:22.685999 received SIGINT, cancelling operations
15:36:22.686138 ssh state summary:
  TUNNEL-CHAMELEON-1 [localhost:2209 -> chromeos15-row1-metro11-host2-chameleon -> localhost:9992]  CLOSED
  TUNNEL-DUT-1      [localhost:2200 -> chromeos15-row1-metro11-host2 -> localhost:22]  CLOSED
```
```text
$ labtunnel hosts --ssh chromeos1-dev-host1
15:37:54.707585 starting ssh exec "TUNNEL-SSH-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
15:37:54.708024 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
15:37:55.708350 ssh state summary:
  TUNNEL-SSH-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
^C15:37:59.299104 received SIGINT, cancelling operations
15:37:59.299182 ssh state summary:
  TUNNEL-SSH-1      [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
```
```text
$ labtunnel hosts --chameleond chromeos1-dev-host1-btpeer1
15:38:59.152570 starting ssh exec "TUNNEL-CHAMELEOND-1 [localhost:2200 -> chromeos1-dev-host1-btpeer1 -> localhost:9992]"
15:38:59.152945 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:9992 chromeos1-dev-host1-btpeer1 sleep 8h
15:39:00.153233 ssh state summary:
  TUNNEL-CHAMELEOND-1 [localhost:2200 -> chromeos1-dev-host1-btpeer1 -> localhost:9992]  RUNNING
^C15:39:02.276492 received SIGINT, cancelling operations
15:39:02.276983 ssh state summary:
  TUNNEL-CHAMELEOND-1 [localhost:2200 -> chromeos1-dev-host1-btpeer1 -> localhost:9992]  CLOSED
```

## Debugging
`labtunnel` is designed to clean itself up if something goes wrong in most cases,
though there may be a few things can still go wrong.

### Ports not freed up after labtunnel closes
If `labtunnel` was killed forcefully it may not have had time to kill all the
ssh subprocess which are listening on ports. Finding the lingering `ssh`
processes (`ps -ef | grep ssh`) and killing them manually should clear this up.

Note: Even if this happens it will not prevent subsequent calls to `labtunnel`
from listening on new ports, as it will just skip to the next available port.

### TigerVNC not installed
The `dutvnc` tunnel operation uses the `xtigervncviewer` command provided by
TigerVNC to open a local VNC client to the VNC server on the DUT. You can either
install this or add the `--do-not-open-vnc` flag and use your own client to
connect to the hostname labtunnel prints out for use.

If you chose to install TigerVNC and are on gLinux, you can install it like so:
```text
sudo apt install tigervnc-viewer
```
