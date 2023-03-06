# lium - yet another wrapper for CrOS developers

## Goal

We have too many ways to do common tasks. Also, our builds are fragile due to the multi-repo structure and
build system quirks, which consumes so much time of developers to try out trivial fix commands.
"lium" provides a simple interface for common tasks for CrOS developers,
with plenty of automatic error recovery mechanisms to avoid keep sticking your eyes on the display(s),
give you some time for a nap and/or coffee, or other tasks ;)

## Build and install

[Install the Rust toolchain](https://rustup.rs/) and run:

```
make install
```

### Install bash completion file

You can also install the bash completion file by running:

```
lium setup bash-completion && source ~/.bash_completion
```

This will be done automatically after `make install` if your default shell is bash.

## Usage examples

Note: You can replace `lium` with `cargo run -- ` to run your own modified version of lium.

Some may not work due to the updates. If you find them, let hikalium@ know or upload a CL to fix them!

### DUT
```
# SSH into a DUT using testing_rsa
lium dut shell --dut ${DUT}

# Execute a shell command on a DUT
lium dut shell --dut ${DUT} -- uname -a

# Add a DUT to the list
lium dut list --add ${IP}

# Show the list of DUTs registered
lium dut list

# Check connection and remove DUTs that have reused IP addresses
lium dut list --update

# Show DUT info
lium dut info --dut ${DUT}

# Show specific DUT info (e.g. ipv6_addr)
lium dut info --dut ${DUT} ipv6_addr

# Scan DUTs on a remote network
lium dut discover --remote ${REMOTE} | tee /tmp/dut_discovered.json
```

### Servo

```
# Update the list of Servo devices connected
lium servo list --update

# Show the cached list of Servo devices
lium servo list
```

### Flash

```
lium flash --repo ${CROS_DIR} --dut ${DUT}
lium flash --repo ${CROS_DIR} --board ${BOARD}
```

### Misc

```
lium arc guest_kernel_uprev --repo /work/chromiumos_stable/
lium build --repo /work/chromiumos_stable --board brya --packages sys-kernel/arcvm-kernel-ack-5_10
lium build --full --repo /work/chromiumos_stable --board brya
lium config set default_cros_checkout /work/chromiumos_stable/
lium config show
lium deploy --repo /work/chromiumos_stable --dut localhost:2282 --package sys-kernel/arcvm-kernel-ack-5_10 --autologin
lium dut discover --remote kled_SOMESERIALNUMBERS1234 --v6prefix 2001:DB8::
sudo `which lium` servo reset
lium sync --repo /work/chromiumos_stable/ --version 14899.0.0
lium sync --repo /work/chromiumos_stable/ --version R110-15263.0.0
# following command needs a mirror repo which has cloned with --mirror option
lium sync --repo /work/chromiumos_versions/R110-15248.0.0/ --version R110-15248.0.0 --reference /work/chromiumos_mirror/
lium sync --repo /work/chromiumos_versions/R110-15248.0.0/ --version R110-15248.0.0 # you can omit --reference if the config is set
```

## How to contribute
After making your change, please run:
```
make commit
```
to make a commit after running various checks.

Once your commit is ready, upload a CL with:
```
repo upload --cbr --wip .
```

and please add hikalium@ and/or mhiramat@ as reviewers.

Happy hacking!
