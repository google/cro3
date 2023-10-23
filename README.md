# lium - Make ChromiumOS development extremely easy

`lium` is an extremely user-friendly tool for ChromiumOS developers.

It provides a simple way to do common development tasks and make the barrier for contributing to ChromiumOS and lium itself as low as possible.

It also makes discovering features and functionality as easy as and clear as possible, with command completions.

Moreover, it manages local development hardware including DUTs and Servos, and act as working examples of commands to interact with them.

We hope lium gives you some time for a nap and/or coffee, or other tasks by making your work more effective ;)

## Core principles

- Make the basic ChromiumOS development workflow extremely easy
  - Background: There have been a huge barriers to get started with the ChromiumOS development. It scares newcomers sometimes, and such environment is not sustainable, scalable or efficient. The top priority of lium is to mitigate this high barrier of entry.
  - Basic workflows include: checkout the source code, build images / deploying packages / run tests with / without modifications.
- Make it extremely easy to start using lium
  - Background: As stated in the above, our goal is lowering the barrier for people who are about to start contribution to ChromiumOS. To achive that, a tool that aids the goal should be extremely easy as well to start using it.
  - How: Follow best practices and common ways to do things. Prefer defaults always if there is no clear reason to change that.
- Be an executable reference of how to do things by providing best practices as a code
  - Background: Documentation can be rotten silently. Code rots as well, but it is easier to notice that it's broken. Also, people tend to prefer coding over writing documents.
  - How: Provide enough background information in the code as comments. Put links to the documentation. Put anything useful that may help future developers and users. Avoid natural languages that is confusing. Instead, translate the logics and steps described in documentation as a code.

## Build and install

[Install the Rust toolchain](https://rustup.rs/) and run:

```
make install
```

### Shell completions

You can install the shell completion by running this at any time:
```
# Bash
lium setup bash-completion

# Zsh
lium setup zsh-completion
```

Please don't forget to follow instructions that are printed after running the command above and reload your shell!

This will be done automatically after `make install` if your default shell is supported by lium.

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
make check
```
to verify your change with formatting checks and unit tests.

Once your commit is ready, please file a pull request on GitHub, as described in [CONTRIBUTING.md](./CONTRIBUTING.md).

To make sure the commits in the main tree to be bisectable, pull requests will be squashed and rebased on top of the main branch before being merged. Therefore, please make sure that the title and the description of a pull request can be treated as commit messages, before submitting it out for code review.

Happy hacking!

## Disclaimer
This is not an officially supported Google product.
