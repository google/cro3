# CopyBot

CopyBot is a tool that automates commit copying from a third-party
repository into Gerrit.  Currently, it's used by the Zephyr and
Coreboot projects.

[TOC]

## CopyBot vs. Copybara

Google already has very complex infrastructure to copy code from one
place to another called [Copybara].  So why does CopyBot exist?
Copybara works at the "tree level" and does not know how to
cherry-pick code between sources.  Rightfully, adding support for
cherry-picking comes with additional complexities, like figuring out
how to handle merge conflicts.

However, many of our teams need the ability to either maintain patches
on a temporary basis, or land commits in a different order to
integrate dependencies.  Thus, we need the ability to do cherry-picks,
even if it does mean extra complexity.

Should [Copybara] support this in the future in a manner which works
well for CopyBot's users, we should work to deprecate our usages of
CopyBot in favor of unified infrastructure.

[Copybara]: https://github.com/google/copybara

## CopyBot's design

CopyBot consists of two Python scripts: `copybot.py` and
`service_spawner.py`.

### copybot.py

`copybot.py` is what to run to copy code from one repository to
another.  Its general usage is:

```
./copybot.py [options...] <upstream_repo>:<upstream_branch> <downstream_repo>:<downstream_branch>
```

Run `./copybot.py --help` for a complete list of options supported.

`copybot.py` will then:

1. Search for the first commit in the downstream repo which has
   `GitOrigin-RevId` or `Original-Commit-Id` specified in the footers,
   or has the exact same hash as as an upstream commit.

2. Identify the commits that need cherry-picked from that commit up to
   the current branch head (keeping in mind file filtering pattens may
   cause certain commits to be skipped).

3. Cherry-pick those commits onto the downstream repo.

4. Push the changes to Gerrit.

### Service Spawner

The `service_spawner.py` spawns CI jobs on [SourceHut Builds] based on
configured jobs in a YAML file.

Run `./service_spawner.py --help` for a full list of options.

The config YAML file should contain entries:

`base-manifest`: This is the base build manifest for the job, which
should specify the dependencies required to invoke CopyBot.  The
manifest format is documented
[here](https://man.sr.ht/builds.sr.ht/manifest.md).

`services`: This specifies the list of services that should be
spawned.  The options available for each service is described below:

- `upstream` (required): The upstream URL to fetch from.

- `upstream-branch` (optional): The upstream branch.  If unspecified,
  assumed to be `main`.

- `downstream` (required): The downstream URL to fetch from and push to.

- `downstream-branch` (optional): The downstream branch.  If
  unspecified, assumed to be `main`.

- `topic` (required): This specifies the Gerrit topic to use for
  pushes.

- `labels`, `ccs`, `reviewers`, and `hashtags` are all optional lists
  which will be added to the Gerrit push options when uploading.

- `prepend-subject` (optional): A string to insert in front of the
  original commit message, for example `UPSTREAM: `.

- `merge-conflict-behavior` (optional): Either `SKIP` (the default),
  or `FAIL`.  `SKIP` will cause CopyBot to continue trying to
  cherry-pick further commits after a merge conflict, whereas `FAIL`
  will cause the script to exit immediately on the first merge
  conflict: no commits will be pushed.  Regardless of which option is
  chosen, CopyBot will still exit non-zero, allowing your downstreamer
  to manually deal with the conflict.

- `exclude-file-patterns` (optional): a list of regular expressions of
  paths to be excluded during downstreaming.  If all of the files in a
  commit match at least one of these patterns, the commit will be
  skipped during cherry-picking.  If some, but not all, of the files
  in the commit match, the commit will be reduced down to only the
  paths which don't match any regex.  CopyBot will add a
  `CopyBot-Skipped-File` footer to the commit message for each file
  skipped.

- `triggers` (optional): A list of triggers (as defined by the
  SourceHut manifest format) to complete after the build.  Generally,
  you should use this to set up an email trigger to notify the
  downstreamer of failures.

To get an idea of how the YAML translates to the command line passed
to `copybot.py`, run `./service_spawner.py --dry-run`, which will
print the generated manifest for each job.

[SourceHut Builds]: https://builds.sr.ht

## Using CopyBot

CopyBot is intended to be run daily as a cron job.  The Chromium OS
deployment of CopyBot runs nightly at ~4:30 AM Mountain Time.

Your job as a downstreamer is to:

- CR+2 and CQ+2 the commits uploaded by CopyBot.

- Watch for CQ failures.

- Manually handle commits with merge conflicts (if required).  You'll
  know this happens because you'll get an email from the CI failure:
  click the link for the output, and the list of commits with merge
  conflicts will be at the bottom of the page.

- Move commits with external dependency (e.g., a Cq-Depend, or an API
  change that requires rework of other code) out of the CL stack and
  handle merging these manually, as required.  See
  [Skipping Commits](#skipping-commits) below.

### Skipping Commits

On a rare occasion, it may be necessary to skip certain commits so
they can be merged later.

To do this, apply the Gerrit hashtag `copybot-skip` to either a commit
that you've uploaded manually, or one of CopyBot's commits.  From the
Gerrit UI, you may need to click the "More" button on the left panel
to see and add the hashtags.  The only requirement is that you include
the full upstream commit hash somewhere in the commit message.

On CopyBot's next run, it will respect your wishes, and no longer
upload any commits which came from this upstream revision.  If you
change your mind in the future, just remove the hashtag.

### Triggering CopyBot Manually

If you ever need to run CopyBot manually, you can either use
`./service_spawner.py --local --topic <your_gerrit_topic>` from the
command line, or you can ask jrosenth@ to do a manual spawn of the
SourceHut jobs.

## Contributing to CopyBot

First of all, thanks!  Your improvements are very much welcomed!

Python source code should be auto-formatted by `black` and `isort`.
Run `black .` and `isort .` to do the formatting.

To run tests, use `./run_tests.sh`.

### Future Improvements

A number of improvements could be made to Copybot in the future to
make it more friendly and help keep the bus number high.  Possible
ideas include:

- Migrating from SourceHut CI jobs to LUCI, or even re-writing the
  whole thing as a LUCI recipe.

- Adding a Web UI for monitoring and manual triggering.

- Better email notifications on merge conflicts.

- Automated copying and updates of FROMPULL PRs from GitHub when
  changes are pushed.
