# emacs for Chrome OS

This directory contains projects for using emacs as editor for Chrome OS.

## Gerrit integration.

See [Chromacs gerrit integration](gerrit/README.md) for how to integrate with
gerrit.

## `cros_sdk` tramp integration.

In your `.emacs` configuration file, load `cros-sdk-tramp.el`, and set up the
path to your CrOS checkout.

```lisp
(setq cros-sdk-tramp-src-path "~/src/path/to/cros")
(load-file "~/path/to/cros-sdk-tramp.el")
```

Then find file with path starting `/cros::` would use the right path, things
like `M-x shell` will start a `cros_sdk`. Because `cros_sdk` invokes sudo you
will be asked password.

Make sure you ask no when asked to store your corp password.

`M-x compile` for example with `cros_workon_make --test --board=rammus-arc-r
debugd` will start compilation inside the chroot in the compilation buffer and
the next-error would find the right source location.

`cros-sdk-tramp-rotate-among-files` utility is provided to switch between inside
chroot and outside.

To make `cros_sdk` smooth you may want to tweak your
[sudo configuration](https://chromium.googlesource.com/chromiumos/docs/+/HEAD/tips-and-tricks.md#How-to-make-sudo-a-little-more-permissive)
