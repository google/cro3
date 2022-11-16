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
  sshwatcher  Ssh tunnel to host(s).
  wificell    Ssh tunnel to the dut, pcap, and router of a wificell.

Flags:
  -h, --help                          help for labtunnel
  -p, --local-port-start int          Initial local port to forward to tunnel (default 2200)
      --remote-port-chameleond int    Remote port for accessing the chameleond service on btpeers and chameleon devices (default 9992)
      --remote-port-ssh int           Remote port to forward ssh tunnels to (default 22)
  -o, --ssh-options strings           ssh options for all ssh commands (default [StrictHostKeyChecking=no,ExitOnForwardFailure=yes,ForkAfterAuthentication=no,LogLevel=ERROR,ControlMaster=auto,ControlPersist=3600,ControlPath=/tmp/ssh-labtunnel-%C,ServerAliveCountMax=10,ServerAliveInterval=1,VerifyHostKeyDNS=no,CheckHostIP=no,UserKnownHostsFile=/dev/null,Compression=yes])
      --ssh-retry-delay-seconds int   Time to wait before retrying failed ssh command calls (default 10)
  -a, --tauto                         For tunnel usage that differs between Tauto/Autotest and Tast, make then as expected for Tauto (effects btpeer and chameleon tunnels)
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
17:49:35.320507 starting ssh exec "TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
17:49:35.320890 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
17:49:35.333824 starting ssh exec "TUNNEL-ROUTER-1   [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]"
17:49:35.334141 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2201:localhost:22 chromeos1-dev-host1-router sleep 8h
17:49:35.346346 starting ssh exec "TUNNEL-PCAP-1     [localhost:2202 -> chromeos1-dev-host1-pcap -> localhost:22]"
17:49:35.346557 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2202:localhost:22 chromeos1-dev-host1-pcap sleep 8h
17:49:36.346795 Example Tast call (in chroot): tast run -var=router=localhost:2201 -var=pcap=localhost:2202 localhost:2200 <test>
17:49:36.346878 ssh state summary:
  TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
  TUNNEL-PCAP-1     [localhost:2202 -> chromeos1-dev-host1-pcap -> localhost:22]  RUNNING
  TUNNEL-ROUTER-1   [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]  RUNNING
^C17:49:40.064102 received SIGINT, cancelling operations
17:49:40.064238 ssh state summary:
  TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
  TUNNEL-PCAP-1     [localhost:2202 -> chromeos1-dev-host1-pcap -> localhost:22]  CLOSED
  TUNNEL-ROUTER-1   [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]  CLOSED
```
```text
$ labtunnel wificell chromeos1-dev-host1 --routers 1 --pcaps 1 --btpeers 1
17:51:47.304796 starting ssh exec "TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
17:51:47.305315 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
17:51:47.337514 starting ssh exec "TUNNEL-ROUTER-1   [localhost:2202 -> chromeos1-dev-host1-router -> localhost:22]"
17:51:47.337908 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2202:localhost:22 chromeos1-dev-host1-router sleep 8h
17:51:47.354007 starting ssh exec "TUNNEL-PCAP-1     [localhost:2203 -> chromeos1-dev-host1-pcap -> localhost:22]"
17:51:47.354339 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2203:localhost:22 chromeos1-dev-host1-pcap sleep 8h
17:51:47.399457 starting ssh exec "TUNNEL-BTPEER-1   [localhost:2206 -> chromeos1-dev-host1-btpeer1 -> localhost:9992]"
17:51:47.399730 SSH[4]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2206:localhost:9992 chromeos1-dev-host1-btpeer1 sleep 8h
17:51:48.399603 Example Tast call (in chroot): tast run -var=router=localhost:2202 -var=pcap=localhost:2203 localhost:2200 <test>
17:51:48.399671 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2206 -> chromeos1-dev-host1-btpeer1 -> localhost:9992]  RUNNING
  TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
  TUNNEL-PCAP-1     [localhost:2203 -> chromeos1-dev-host1-pcap -> localhost:22]  RUNNING
  TUNNEL-ROUTER-1   [localhost:2202 -> chromeos1-dev-host1-router -> localhost:22]  RUNNING
^C17:51:57.496110 received SIGINT, cancelling operations
17:51:57.496212 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2206 -> chromeos1-dev-host1-btpeer1 -> localhost:9992]  CLOSED
  TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
  TUNNEL-PCAP-1     [localhost:2203 -> chromeos1-dev-host1-pcap -> localhost:22]  CLOSED
  TUNNEL-ROUTER-1   [localhost:2202 -> chromeos1-dev-host1-router -> localhost:22]  CLOSED
```

### callbox
```text
$ labtunnel callbox chromeos1-donutlab-callbox1-host1 access@chromeos1-proxy chromeos1-donutlab-callbox1.cros
17:52:20.702901 starting ssh exec "TUNNEL-DUT        [localhost:2200 -> chromeos1-donutlab-callbox1-host1 -> localhost:22]"
17:52:20.703249 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-donutlab-callbox1-host1 sleep 8h
17:52:20.714076 starting ssh exec "TUNNEL-CALLBOX_MANAGER [localhost:2201 -> access@chromeos1-proxy -> localhost:5000]"
17:52:20.714422 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2201:localhost:5000 access@chromeos1-proxy sleep 8h
17:52:20.724327 starting ssh exec "TUNNEL-CALLBOX    [localhost:2202 -> access@chromeos1-proxy -> chromeos1-donutlab-callbox1.cros:5025]"
17:52:20.724583 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2202:chromeos1-donutlab-callbox1.cros:5025 access@chromeos1-proxy sleep 8h
17:52:21.724847 Example Tast call (in chroot): tast run -var=callbox=localhost:2202 -var=callboxManager=localhost:2201 localhost:2200 <test>
17:52:21.724946 ssh state summary:
  TUNNEL-CALLBOX    [localhost:2202 -> access@chromeos1-proxy -> chromeos1-donutlab-callbox1.cros:5025]  RUNNING
  TUNNEL-CALLBOX_MANAGER [localhost:2201 -> access@chromeos1-proxy -> localhost:5000]  RUNNING
  TUNNEL-DUT        [localhost:2200 -> chromeos1-donutlab-callbox1-host1 -> localhost:22]  RUNNING
17:52:23.054992 SSH[3]: ControlSocket /tmp/ssh-labtunnel-1d98ebacd0da22c935115711ccf10236c3803cce already exists, disabling multiplexing
^C17:53:33.196197 received SIGINT, cancelling operations
17:53:33.197416 ssh state summary:
  TUNNEL-CALLBOX    [localhost:2202 -> access@chromeos1-proxy -> chromeos1-donutlab-callbox1.cros:5025]  CLOSED
  TUNNEL-CALLBOX_MANAGER [localhost:2201 -> access@chromeos1-proxy -> localhost:5000]  CLOSED
  TUNNEL-DUT        [localhost:2200 -> chromeos1-donutlab-callbox1-host1 -> localhost:22]  CLOSED
```

### dut
```text
$ labtunnel dut chromeos1-dev-host1
17:54:01.421768 starting ssh exec "TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
17:54:01.422084 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
17:54:02.422317 Example Tast call (in chroot): tast run localhost:2200 <test>
17:54:02.422384 ssh state summary:
  TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
^C17:54:04.574735 received SIGINT, cancelling operations
17:54:04.574857 ssh state summary:
  TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
```

```text
$ labtunnel dut crossk-chromeos1-dev-host1
17:54:26.573920 starting ssh exec "TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
17:54:26.574249 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
17:54:27.574488 Example Tast call (in chroot): tast run localhost:2200 <test>
17:54:27.574523 ssh state summary:
  TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
^C17:54:30.196242 received SIGINT, cancelling operations
17:54:30.196304 ssh state summary:
  TUNNEL-DUT        [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
```

### dutvnc
```text
$ labtunnel dutvnc chromeos1-dev-host1
Creating SSH tunnel DUT_VNC: localhost:5900 -> chromeos1-dev-host1 -> localhost:5900...
Successfully created tunnels
 DUT_VNC: localhost:5900 -> chromeos1-dev-host1 -> localhost:5900
Starting kmsvnc on dut...
Running 'kmsvnc' on 'chromeos1-dev-host1' in local tmux session 'labtunnel_tmux_ssh_1646703196'...
Launching TigerVNC...

To shut down tunnels and sub-processes, exit this process (pid=221658) with SIGHUP, SIGINT, or SIGQUIT

TigerVNC Viewer 64-bit v1.11.0
Built on: 2021-04-17 08:22
Copyright (C) 1999-2020 TigerVNC Team and many others (see README.rst)
See https://www.tigervnc.org for information on TigerVNC.
^C
Closing labtunnel...
Closing tmux session 'labtunnel_tmux_ssh_1646703196'...
Killing child processes...
```

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
labtunnel btpeers crossk-chromeos15-row4-rack6-host4
17:06:29.808518 starting ssh exec "TUNNEL-DUT        [localhost:2200 -> chromeos15-row4-rack6-host4 -> localhost:22]"
17:06:29.808921 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos15-row4-rack6-host4 sleep 8h
17:06:29.844492 starting ssh exec "TUNNEL-BTPEER-1   [localhost:2203 -> chromeos15-row4-rack6-host4-btpeer1 -> localhost:9992]"
17:06:29.844650 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2203:localhost:9992 chromeos15-row4-rack6-host4-btpeer1 sleep 8h
17:06:30.845300 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2203 -> chromeos15-row4-rack6-host4-btpeer1 -> localhost:9992]  RUNNING
  TUNNEL-DUT        [localhost:2200 -> chromeos15-row4-rack6-host4 -> localhost:22]  RUNNING
^C17:06:32.710833 received SIGINT, cancelling operations
17:06:32.711649 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2203 -> chromeos15-row4-rack6-host4-btpeer1 -> localhost:9992]  CLOSED
  TUNNEL-DUT        [localhost:2200 -> chromeos15-row4-rack6-host4 -> localhost:22]  CLOSED
```

```text
$ labtunnel btpeers crossk-chromeos15-row4-rack6-host4 4
17:05:55.248614 starting ssh exec "TUNNEL-DUT        [localhost:2200 -> chromeos15-row4-rack6-host4 -> localhost:22]"
17:05:55.249045 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos15-row4-rack6-host4 sleep 8h
17:05:55.294289 starting ssh exec "TUNNEL-BTPEER-1   [localhost:2203 -> chromeos15-row4-rack6-host4-btpeer1 -> localhost:9992]"
17:05:55.294535 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2203:localhost:9992 chromeos15-row4-rack6-host4-btpeer1 sleep 8h
17:05:55.307050 starting ssh exec "TUNNEL-BTPEER-2   [localhost:2204 -> chromeos15-row4-rack6-host4-btpeer2 -> localhost:9992]"
17:05:55.307324 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2204:localhost:9992 chromeos15-row4-rack6-host4-btpeer2 sleep 8h
17:05:55.322976 starting ssh exec "TUNNEL-BTPEER-3   [localhost:2205 -> chromeos15-row4-rack6-host4-btpeer3 -> localhost:9992]"
17:05:55.323256 SSH[4]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2205:localhost:9992 chromeos15-row4-rack6-host4-btpeer3 sleep 8h
17:05:55.334133 starting ssh exec "TUNNEL-BTPEER-4   [localhost:2206 -> chromeos15-row4-rack6-host4-btpeer4 -> localhost:9992]"
17:05:55.334365 SSH[5]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2206:localhost:9992 chromeos15-row4-rack6-host4-btpeer4 sleep 8h
17:05:56.334564 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2203 -> chromeos15-row4-rack6-host4-btpeer1 -> localhost:9992]  RUNNING
  TUNNEL-BTPEER-2   [localhost:2204 -> chromeos15-row4-rack6-host4-btpeer2 -> localhost:9992]  RUNNING
  TUNNEL-BTPEER-3   [localhost:2205 -> chromeos15-row4-rack6-host4-btpeer3 -> localhost:9992]  RUNNING
  TUNNEL-BTPEER-4   [localhost:2206 -> chromeos15-row4-rack6-host4-btpeer4 -> localhost:9992]  RUNNING
  TUNNEL-DUT        [localhost:2200 -> chromeos15-row4-rack6-host4 -> localhost:22]  RUNNING
^C17:06:05.269405 received SIGINT, cancelling operations
17:06:05.269655 ssh state summary:
  TUNNEL-BTPEER-1   [localhost:2203 -> chromeos15-row4-rack6-host4-btpeer1 -> localhost:9992]  CLOSED
  TUNNEL-BTPEER-2   [localhost:2204 -> chromeos15-row4-rack6-host4-btpeer2 -> localhost:9992]  CLOSED
  TUNNEL-BTPEER-3   [localhost:2205 -> chromeos15-row4-rack6-host4-btpeer3 -> localhost:9992]  CLOSED
  TUNNEL-BTPEER-4   [localhost:2206 -> chromeos15-row4-rack6-host4-btpeer4 -> localhost:9992]  CLOSED
  TUNNEL-DUT        [localhost:2200 -> chromeos15-row4-rack6-host4 -> localhost:22]  CLOSED
```

### sshwatcher
```text
 labtunnel sshwatcher chromeos1-dev-host1
18:14:04.846826 starting ssh exec "TUNNEL-1          [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
18:14:04.847156 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
18:14:05.847231 ssh state summary:
  TUNNEL-1          [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
^C18:14:13.474880 received SIGINT, cancelling operations
18:14:13.475272 ssh state summary:
  TUNNEL-1          [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
```

```text
$ labtunnel sshwatcher chromeos1-dev-host1 chromeos1-dev-host1-router chromeos1-dev-host6
18:14:54.847513 starting ssh exec "TUNNEL-1          [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]"
18:14:54.848094 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos1-dev-host1 sleep 8h
18:14:54.859815 starting ssh exec "TUNNEL-2          [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]"
18:14:54.860329 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2201:localhost:22 chromeos1-dev-host1-router sleep 8h
18:14:54.870291 starting ssh exec "TUNNEL-3          [localhost:2202 -> chromeos1-dev-host6 -> localhost:22]"
18:14:54.870483 SSH[3]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2202:localhost:22 chromeos1-dev-host6 sleep 8h
18:14:55.870727 ssh state summary:
  TUNNEL-1          [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  RUNNING
  TUNNEL-2          [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]  RUNNING
  TUNNEL-3          [localhost:2202 -> chromeos1-dev-host6 -> localhost:22]  RUNNING
^C18:14:58.576961 received SIGINT, cancelling operations
18:14:58.577275 ssh state summary:
  TUNNEL-1          [localhost:2200 -> chromeos1-dev-host1 -> localhost:22]  CLOSED
  TUNNEL-2          [localhost:2201 -> chromeos1-dev-host1-router -> localhost:22]  CLOSED
  TUNNEL-3          [localhost:2202 -> chromeos1-dev-host6 -> localhost:22]  CLOSED
```


### chameleon
```text
labtunnel chameleon crossk-chromeos15-row1-metro11-host2
17:28:21.384892 starting ssh exec "TUNNEL-DUT        [localhost:2200 -> chromeos15-row1-metro11-host2 -> localhost:22]"
17:28:21.385214 SSH[1]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2200:localhost:22 chromeos15-row1-metro11-host2 sleep 8h
17:28:21.413752 starting ssh exec "TUNNEL-CHAMELEON  [localhost:2203 -> chromeos15-row1-metro11-host2-chameleon -> localhost:9992]"
17:28:21.413887 SSH[2]: RUN: /usr/bin/ssh -o StrictHostKeyChecking="no" -o ExitOnForwardFailure="yes" -o ForkAfterAuthentication="no" -o LogLevel="ERROR" -o ControlMaster="auto" -o ControlPersist="3600" -o ControlPath="/tmp/ssh-labtunnel-%C" -o ServerAliveCountMax="10" -o ServerAliveInterval="1" -o VerifyHostKeyDNS="no" -o CheckHostIP="no" -o UserKnownHostsFile="/dev/null" -o Compression="yes" -L 2203:localhost:9992 chromeos15-row1-metro11-host2-chameleon sleep 8h
17:28:22.414140 ssh state summary:
  TUNNEL-CHAMELEON  [localhost:2203 -> chromeos15-row1-metro11-host2-chameleon -> localhost:9992]  RUNNING
  TUNNEL-DUT        [localhost:2200 -> chromeos15-row1-metro11-host2 -> localhost:22]  RUNNING
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
sudo apt install tigervnc-viewer'
```
