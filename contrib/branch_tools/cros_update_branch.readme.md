cros_update_branch
==================
Author: martinroth@google.com

Introduction
------------
cros_update_branch is a tool to help cherry-pick commits from a series
of branches into another group of branches.  This is particularly useful
in Chrome OS for managing firmware and factory branches, though it
should be useful for any branches that you want to keep in sync.

## Use
To use the program, you will generally want to set up a config file.  It
can be used without a config file by specifying the board and branches
on the command line, but this limits it to working on a single
repository, and also loses many of the keyword highlighting
capabilities.  More on both of these will be covered later in the
document.

After running the script, it will look for the config file, and then
parse through it, setting up the variables.  It will then loop through
any listed repositories, syncing them by default, and then showing
differences between the two branches.  At that point, you may select the
commit IDs that you want to sync from the upstream repository to the
downstream repository.  Each of these commits is cherry-picked into a
temporary branch created by the script. If a cherry-pick fails, the
script gives you a number of options allowing you to attempt to merge
manually, or skip the commit if you so wish.

After all the desired patches have been cherry-picked from the upstream
to downstream branches, you are taken to a menu to decide what you want
to do next.  You can run a test build, push the changes to gerrit,
abandon the patches, or leave the temporary branch for later.

Note that when you do a build, the script does not currently check for
or run a cros-workon start for any repo - these need to be done
manually.

### Command Line Parameters
```
cros_update_branch version 0.09

Usage: cros_update_branch [options]

Options:
-b | --board      Set platform name.
-c | --conf       Set config file.
-d | --date       Earliest date to compare against - format:YYYY-MM-DD.
-D | --debug      Print debug information.  Use -DD to show all commands.
-F | --from       Set the branch to pull change from (for one project only).
-n | --nevercls   Never clear the screen or scrollback buffer.
-N | --nocolor    Don't use color codes.
-R | --repo       Specify the top of the repository directory.
-s | --skipsync   Assume that repos are already synced.
-S | --same       Show commits that are the same in both branches.
-T | --to         Set the branch to merge changes to (for one project only).
-V | --version    Print the version and exit.
```

#### General Parameters
##### -c | --conf

By default, the script looks for a config file in a number of places,
but if the config file isn’t found, or if you want to specify a
different config file name, the --conf parameter allows you to do that.

The config file search order is:
1. The current directory the script is run in.
2. Top of the current chroot directory.
3. Your home directory.
4. The same directory as the script.

##### -d | --date
The --date parameter allows you to set the oldest date that you want to
view commits from.  Generally this would be the last date that you ran
the script.  If this date is not given, the script looks for a date in
the config file.  If that date isn’t present either, you get ALL the
history.

##### -D | --debug
If you’re interested in seeing what the script is doing, --debug shows
you the general debug output, along with the output of the programs that
are being run.  To see all of the commands being run as well, add
another --debug to the command line.

##### -n | --nevercls
By default, each time a new project is shown, the screen and scrollback
buffer are cleared.  This prevents that and lets you see the entire
history.  This parameter is implied by the parameter --debug so that you
don’t lose the debug history.

##### -N | --nocolor
By default, some messages and all errors are shown in color.  This
parameter prevents that for use in logfiles and such.  Also prevents
Bold.

##### -R | --repo
Specify the root directory of the chroot. This is normally discovered by
the script if it’s run from under the chroot directory.

##### -s | --skipsync
If your repo has been recently synced, this saves some time by
preventing each repo from being synced again.

##### -S | --same
The normal display of patches to cherry-pick excludes patches that are
already in both branches.  This can be toggled at runtime, but this
parameter enables it by default.


#### Parameters used for single-repo runs

##### -b | --board
This allows you to specify a board/program name, such as Zork, Octopus,
or Guybrush

##### -F | --from
Specify the name of the upstream repo that you’re cherry-picking from.

##### -T | --to
Specify the name of the downstream repo that you’re cherry-picking to.


Menus
-----

### Cherry-pick menu
When you select a repo/project to sync, after switching to that
directory, updating the git tree and creating a temporary branch, you
will be shown the list of commits that are different between the two
branches, if there are any.  If there aren’t any changes, the script
will just go on to the next repo/project.

You will be presented with a basic prompt with the list of commands
allowing you to decide what to do next.

```
Commits for amd_blobs BOARD=guybrush BRANCH=remotes/cros/firmware-guybrush-14500.B
< d8a51cb [2022-02-15 08:16:32 -0700] (marshall.dawson@amd.com) - cezanne: Upgrade ABL to 0x22146070

Enter commit ids separated by spaces, (A)ll, (N)ext, (S)how unpicked,
(D)one, (L)ist picked, (R)efresh, (T)oggle Both, (H)elp or (Q)uit:
```

These options should be explained sufficiently by the in-script help
text below:
```
  Cherry-pick menu help:
   <commit ids> - Add commit to merge list. Multiple ids can be entered
                  at once, separated by spaces.
   (A)ll - Add all unmerged patches to the merge list.
   (D)one adding patches. Go to the commit menu.
   (H)elp - Display help text.
   (L)ist all patches currently in the merge list.
   (N)ext - Cherry-pick next unpicked commit.
   (Q)uit the script.
   (R)efresh - Re-display list of patches.
   (S)how unpicked commits.
   (T)oggle between showing and hiding patches in both branches.

  Color Key: Red Underlined - Unmerged, Contains platform name.
             Red - Unmerged, Contains a highlight keyword.
             Grey - Unmerged, Contains an ignore keyword.
             White - Unmerged, No keyword matches.
             Turquoise - commit in both to and from branches.
             Blue - Commit only on the 'To' branch.

  Git cherrymark Key: < Only in branch you are cherry-picking FROM (Upstream).
                      > Only in branch you are cherry-picking TO (Downstream).
                      = In both branches.
                   Note that commits that needed merging can show up
                   as both '<' and '>' instead of '='.

```

One thing to note is that the oldest patches are at the bottom, so if
you select the patches manually and add them at the prompt, to stay in
the order that they were in, you should start at the bottom of the list
and work your way up.

Additionally, after all available unpicked patches are selected and
cherry-picked into the temporary branch, only the bottom line of the
prompt will appear, as the top line of the prompt, is not useful at that
point.

Note that if you add a patch and change your mind about it, you can
select Done and go to the Commit menu where you can remove the patch
with the Update patches option which will take you into a ‘git rebase
-i’ session.  After removing the patch, you can select the Continue
adding patches option to come back to the Cherry-pick menu.

### Cherry-pick merge resolution menu
When cherry-picking a patch to the downstream branch, you’ll
occasionally come across a patch that doesn’t merge cleanly.  This
becomes more frequent the more out-of-date the downstream branch is
compared to the upstream.  In these cases, you’ll be presented with
another menu giving you options on how to resolve the issue.

```
Error: Could not cherry-pick d8a51cb automatically.
How do you want to resolve this?
 (A)bort cherry-picking.
 (C)ontinue with cherry-picking, skipping this patch.
 (F)ixed the cherry-pick in another terminal.
 (M)anual fix with git merge tool.
 (S)hell prompt to fix the issue.
 (V)iew the commit in gerrit.

Choose from an option above:
```

Aborting the cherry-picking procedure will stop immediately and go back
to the previous menu, whereas Continuing will just skip this one patch
and still attempt to pull in any other patches that you’re currently
cherry-picking.

To do a manual fix, you can either fix the issue by opening another
terminal window and doing your work there, or you can leave the script
to temporary prompt, fix the issue, and then exit to continue in the
script. The Manual fix option runs ‘git mergetool’ to open meld or the
like and allow you to look at and attempt to fix the changes.

The final option of View will open the commit in your web browser to
look at the patch.

### Commit Menu
After you’ve cherry-picked your patches and selected (D)one, the script
takes you to the commit menu.  This gives you the options for what to do
with your patches next.

```
Select what to do with the cherry-picked patches.
 (A)bandon changes.
 (B)uild now for testing: 'emerge-guybrush -j coreboot chromeos-bootimage '
 (C)ontinue adding patches.
 (D)elete current reviewer list: 'robbarnes@google.com rrangel@google.com'
 (E)nter additional reviewers for commits (separated by spaces).
 (P)ush for merge: 'l=Code-Review+2,l=Commit-Queue+2,l=Verified+1'
 (Q)uit the script
 (R)eplace commit hashtag: 'cherrypick-script'
 (S)ubmit for review: 'l=Verified+1,r=robbarnes@google.com,r=rrangel@google.com'
 (U)pdate patches (rebase -i).
 (V)alidate cherry-picked commits - leave branch for testing.
```

The typical options at this point are to either push the changes for
review with the Submit option, or for direct merge with the Push option.
For the Submit for review option, the default peer reviewers set in the
config file will be added to the review, but you have the option here to
clear the reviewers and set them in gerrit, or to add additional
reviewers at this point. You can of course also clear the list and add
completely different reviewers as well.

Additionally, the script defaults to a gerrit hashtag of
“cherrypick-script”, but this can be changed in this menu as well.

With the Update patches option, you can change the order of the patches,
delete patches, edit the commit messages, merge patches and the like.

The Continue adding patches option takes you back to the cherry-pick
menu.

There are three options for leaving the patches without pushing them.
Quitting the script does just what it says, while giving you the option
to delete or keep your temporary branch for later use. Abandoning your
changes will immediately delete the temporary branch with your
cherry-picked changes, and the Validate cherry-picked commits option
will continue on with the script, leaving the cherry-picked changes in
place.

The option of leaving the temporary branch with cherry-picked changes is
very useful, as you can run the script once and cherry-pick over any
changes that you think you might need, leaving the temporary branches in
place.  After finishing the script, you can do a full build, and if
successful, then run the script again to push the changes to the branch.

Building the changes is also available directly from the Commit Menu.
You will have the option of changing the build settings once you’ve
selected the build option.  Note again that the script does NOT check or
apply cros-workon settings for the projects, so if the project doesn’t
have that set for this repository, running the build will NOT actually
test the changes you just cherry-picked.

Config File
-----------

The real power of the script is shown by adding all of the repositories
that need to be synced for a branch into a config file.  This allows the
user to configure keywords, along with the list of necessary repos.

The values can be set anywhere in the config file, but it's probably
best to keep them organized into setting similar things in blocks instead
of by repo.

Comments are started with a #.  Blank lines are ignored.

### PLATFORM_NAME
```
# Set the platform name - needed for build testing
PLATFORM_NAME="zork"
```

### PROJ_PATH
The PROJ_PATH values configure both the location of the repository under
the root directory of the chroot that you're working in, along with the
repos being synced.  This variable needs an entry for every repo/project
that is needed for your final build.

```
# PROJ_PATH: Set paths for each project being checked
# Example: PROJ_PATH[coreboot]="src/third_party/coreboot"
# Note that these may be a subdirectory of a repo
# These get evaluated in alphabetical order
PROJ_PATH[coreboot]="src/third_party/coreboot"
PROJ_PATH[private_partner_overlay]="src/private-overlays/chromeos-partner-overlay/sys-boot"
PROJ_PATH[private_chipset_overlay]="src/private-overlays/chipset-picasso-private"
PROJ_PATH[chromeos_overlay]="src/third_party/chromiumos-overlay/sys-boot"
...
```

### PROJ_F_BRANCH
This value sets the upstream branch, which is the branch you're cherry-picking
from.  The 'default' value is used for any branches which are not specified
directly.  This field is where the internal/external repo information comes
from, so all internal repos need to be specified specifically.  This could be
changed in the future to look it up by the directory above.

```
# Set ALL CrOS "FROM" branches
PROJ_F_BRANCH[default]="remotes/cros/main"
PROJ_F_BRANCH[private_partner_overlay]="remotes/cros-internal/main"
PROJ_F_BRANCH[private_chipset_overlay]="remotes/cros-internal/main"
PROJ_F_BRANCH[coreboot]="remotes/cros/chromeos-2016.05"
...
```

### PROJ_T_BRANCH
And this value sets the downstream branch, or where you're cherry-picking your patches to.
Again, any repos that aren't listed here will use the 'default' value.  This again means that
all internal repos need to be specified.

```
# Set the branches to update.
# All not listed here use the 'default' version of the branch
### TODO: UPDATE get_to_branch() to find the remote repo cros/cros-internal
PROJ_T_BRANCH[default]="remotes/cros/firmware-zork-13434.B"
PROJ_T_BRANCH[edk2_payload]="remotes/cros/firmware-zork-13434.B-chromeos-2017.08"
PROJ_T_BRANCH[edk2_pco]="remotes/cros/firmware-zork-13434.B-pco"
PROJ_T_BRANCH[private_partner_overlay]="remotes/cros-internal/firmware-zork-13434.B"
PROJ_T_BRANCH[private_chipset_overlay]="remotes/cros-internal/firmware-zork-13434.B"
...
```

### PROJ_KEYWORDS
The keywords variable indicates words that should be highlighted. The
'global' value gets applied to all commits in all repos, whereas fields
with the names of the repos only get applied to that specific repo.
Names that are not repos are ignored by the script, but can be used to
build up other fields, such as using 'platforms' and 'chips' to build up
the 'global' value.

These values are used by grep
[(BRE syntax)](https://learnbyexample.github.io/gnu-bre-ere-cheatsheet/)
to do a case insensitive search.

```
# Keywords that indicate the commit may be of interest
PROJ_KEYWORDS[platforms]="\<zork\>\|\<trembyle\>\|\<dalboz\>\|/<ezkinil\>\|..."
PROJ_KEYWORDS[chips]="\<picasso\>\|\<pollock\>\|\<dali\>\|\<pco\>"
PROJ_KEYWORDS[global]="${PROJ_KEYWORDS[platforms]}\|${PROJ_KEYWORDS[platforms]}"
PROJ_KEYWORDS[coreboot]="\<soc/amd\>\|\<agesa\>\|amdfwtool\|mrc_cache\|vboot"
PROJ_KEYWORDS[chromeos_overlay]="coreboot-9999.ebuild"
...
```
### PROJ_DIM
These values turn the output grey, as they are typically associated with
projects other than the one we're currently interested in. The variable
is otherwise the same as PROJ_KEYWORDS.

```
# Keywords that indicate the commit is not interesting
# These are shown, but de-emphasized
PROJ_DIM[platforms]="\|volteer\|dedede\|octopus\|fizz\|puff"
PROJ_DIM[chips]="intel\|mediatek\|qualcomm"
PROJ_DIM[global]="${PROJ_DIM[platforms]}\|${PROJ_DIM[chips]}"
PROJ_DIM[coreboot]="emulation\|purism\|clevo\|qemu\|f2a85-m_pro"
...
```

### PROJ_IGNORE
These values are matched against a project to show that they're already
merged.  This can be needed for a number of reasons, such as squashed
patches getting merged instead of individual patches or patches getting
merged with differences.

There is no 'default' or 'global' value here, because each commit is
only going to go into a single project.
```
# commits already merged, but don't show up correctly
PROJ_IGNORE[coreboot]="3de870f224\|2da991400d\|2cce9c5c56\|3eddf72e8e\|..."
```

### PROJ_HIDE
This value is used to keep commits from being displayed at all.  Currently
there is only a global value to ignore automated commits.  If there is a
reason to change this, to project specific values, the script will need
to be updated.
```
# keywords to completely hide
PROJ_HIDE[global]="chrome-bot@chromium.org\|chromeos-ci-prod@chromeos-bot.iam.gserviceaccount.com chromeos-ci-release@chromeos-bot.iam.gserviceaccount.com"
```

### PROJ_BUILD
The PROJ_BUILD entries specify emerge values to pass to the build
```
# projects to emerge to test a particular repo
PROJ_BUILD[global]="coreboot chromeos-bootimage"
PROJ_BUILD[depthcharge]="depthcharge ${PROJ_BUILD[global]}"
PROJ_BUILD[bmpblk]="chromeos-bmpblk ${PROJ_BUILD[global]}"
PROJ_BUILD[chromeos_overlay]="depthcharge chromeos-bmpblk ${PROJ_BUILD[global]}"
```

### PROJ_REVIEWERS
This specifies the default reviewers for commits pushed for review.
These names are not added to commits pushed for merge.  Additional
repo/project names may be added here, and those values will be used
instead of the 'default' value.
```
PROJ_REVIEWERS[default]="rrangel@google.com"
```
### LAST_CHECKED_DATE
The final entry currently in the config file is the date that the repos
were last checked.  This is currently a global value that is applied
to all of the repos and currently must be updated manually.  This may be
specified on the command line, which overrides the value in the config file.

```
LAST_CHECKED_DATE="2021-1-15"
```


Future Changes
--------------

There are a number of places where the script could be changed to improve
it.

1. It's far too long and complex for a bash script, so should be
   rewritten in a different language.  I'd like to rewrite it in Go if I
   have the chance.
2. Automatically update the date.  This could go into a separate file so
   that the config file doesn't need to be changed.
3. There are some default values currently declared in the script that
   could be moved to the config file to make the script more general.
4. It would be nice to have a real TUI to select the commits instead of
   selecting them manually.
5. Put the colors into the config file so they can be customized.
6. There is a function which will write out a config file, but it's not
   yet hooked up to anything.
7. It'd be nice to be able to go backwards in the list of repos instead
   of just sequentially.
