# emacs for Chrome OS

[TOC]

This directory contains projects for using emacs as editor for Chrome OS.

## Tips for setting up emacs for Chrome OS

### BUILD.gn and .gni files

There is a copy of gn mode in chrome browser source tree for editing gn files.

https://chromium.googlesource.com/chromium/src/+/refs/heads/main/tools/emacs/gn.el

```lisp
(load-file "path/to/chromium/src/tools/emacs/gn.el")
```

### ebuild files

Try using the ebuild mode.

```shell
$ git clone https://anongit.gentoo.org/git/proj/ebuild-mode.git
```

```lisp
(add-to-list 'load-path "~/path/to/ebuild-mode/")
(load-library "~/src/ebuild-mode/ebuild-mode.el")
```

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

## CS integration

This will generate codesearch link.

```
(load-file "~/path/to/chromiumos/src/platform/dev/contrib/emacs/generate-cs-path.el")
```

`M-x cros-generate-cs-path` will generate the codesearch link and add it to the clipboard.
