# lium - Abstraction Layer of ChromiumOS development

`lium` is an abstruction layer of ChromiumOS development environment and workflows.

It provides a simple interface for common tasks for ChromiumOS developers,
with plenty of automatic error recovery mechanisms to avoid keep sticking your eyes on the display(s),
give you some time for a nap and/or coffee, or other tasks ;)

Also, it manages local development hardware including DUTs and Servos, and act as working examples of commands to interact with them.

## Build and install

[Install the Rust toolchain](https://rustup.rs/) and run:

```
make install
```

### Bash completion

You can install the bash completion file by running this at any time:

```
lium setup bash-completion && source ~/.bash_completion
```

This will be done automatically after `make install` if your default shell is bash.

...are you using other shells? We appreciate your pull-requests!

## Usage examples

Note: You can replace `lium` with `cargo run -- ` to run your own modified version of lium.

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

### Servo / Cr50

```
# Show list of Servo / Cr50 devices
lium servo list

# Do the same thing in JSON format
lium servo list --json
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

Once your commit is ready, please file a pull request on GitHub, as described in [CONTRIBUTING.md](./CONTRIBUTING.md).

Try to keep commits small and
[stacked](https://engineering.uptechstudio.com/blog/how-we-should-be-using-git/).
A series of small changes that each work in isolation and are easy to review
are better than one large one.  To help do this, we have created some hooks
using [git-ps](https://book.git-ps.sh/introduction), but you can easily use
something like [ghstack](https://github.com/ezyang/ghstack) or even meta's
[sapling](https://sapling-scm.com) to help you cut these into chains of Pull
Requests.

Happy hacking!

## Disclaimer
This is not an officially supported Google product.
