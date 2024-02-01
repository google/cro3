# cro3 - Make ChromiumOS development extremely easy

`cro3` is an extremely user-friendly tool for ChromiumOS developers.

It provides a simple way to do common development tasks and make the barrier for contributing to ChromiumOS and cro3 itself as low as possible.

It also makes discovering features and functionality as easy as and clear as possible, with command completions.

Moreover, it manages local development hardware including DUTs and Servos, and act as working examples of commands to interact with them.

We hope cro3 gives you some time for a nap and/or coffee, or other tasks by making your work more effective ;)

## Core principles

- Make the basic ChromiumOS development workflow extremely easy
  - Background: There have been a huge barriers to get started with the ChromiumOS development. It scares newcomers sometimes, and such environment is not sustainable, scalable or efficient. The top priority of cro3 is to mitigate this high barrier of entry.
  - Basic workflows include: checkout the source code, build images / deploying packages / run tests with / without modifications.
- Make it extremely easy to start using cro3
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
cro3 setup bash-completion

# Zsh
cro3 setup zsh-completion
```

Please don't forget to follow instructions that are printed after running the command above and reload your shell!

This will be done automatically after `make install` if your default shell is supported by cro3.

...are you using other shells? We appreciate your pull-requests!

## Command line reference

Please refer to [docs/cmdline.md](docs/cmdline.md) ( [HTML version](https://google.github.io/lium/cmdline.html) )

Tips: You can replace `cro3` with `cargo run -- ` to use your own modified version of cro3 instead.

Also, you can preview the command line reference by running:

```
gh extension install https://github.com/yusukebe/gh-markdown-preview
make preview
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
