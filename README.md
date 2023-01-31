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
make
```

### Install bash completion file

You can also install the bash completion file by running:

```
lium setup bash-completion
source ~/.bash_completion
```

## Usage examples

You can replace `lium` with `cargo run -- ` to run your own modified version of lium.

Some may not work due to the updates. If you find them, let hikalium@ know!

```
lium arc guest_kernel_uprev --repo /work/chromiumos_stable/
lium build --repo /work/chromiumos_stable --board brya --packages sys-kernel/arcvm-kernel-ack-5_10
lium build --full --repo /work/chromiumos_stable --board brya
lium config set default_cros_checkout /work/chromiumos_stable/

lium config show
lium deploy --repo /work/chromiumos_stable --dut localhost:2282 --package sys-kernel/arcvm-kernel-ack-5_10 --autologin
lium dut discover --remote kled_SOMESERIALNUMBERS1234 --v6prefix 2001:DB8::
lium dut info 192.0.2.1
lium dut info --keys arch,hwid nightfury_SOMESERIALNUMBERS1234
lium dut list
lium dut shell droid_SOMESERIALNUMBERS1234
lium dut shell localhost:2282
lium dut shell '[2001:DB8::4a65:eeff:fe15:79c]:22' -- ./lium
lium flash --board octopus-kernelnext --version 15263.0.0 --dut kled_SOMESERIALNUMBERS1234 --repo /work/chromiumos_stable/
lium flash --repo /work/chromiumos_stable/ --board brya
lium servo control --repo /work/chromiumos_stable/ --serial SERVOV4P1-S-SOMESERIALNUMBERS1234 --mac-addr
lium servo list
lium servo list --json | jq .
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
