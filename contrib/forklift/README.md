# Forklift Utility

## Overview

The forklift utility aids in backporting large numbers of commits from
upstream to a local branch. To accomplish this, it uses a report file to keep
track of the commits which have been backported and which are outstanding.

The report file contains the list of commits to be cherry picked as well as the
current progress of the forklift. The utility uses it to keep track of progress
across invocations. The file is human-readable json, and can be read/altered if
necessary. It should not be necessary to inspect/modify the report fie, if you
find yourself doing this, please send patches :-).


## Operation
The order of operations for a forklift is as follows:

### Find the target pull request
Seach lore.kernel.org for the pull request you would like to forklift. In this
example we will use the [drm 5.11 pull request](https://lore.kernel.org/dri-devel/CAPM=9tyNrbap4FG6qstkC5YTznqVebD=ye+4+Z+t42yQnL325A@mail.gmail.com/).

From here, you will need the `Message-Id` as well as the mailing list/project to
gather it from. In our case, they are:
```
List/Project: dri-devel
Message-ID: CAPM=9tyNrbap4FG6qstkC5YTznqVebD=ye+4+Z+t42yQnL325A@mail.gmail.com
```

### Generate the report
Now that we have the pull request, we start a new branch in our target kernel
directory (using `repo sync` or `git`) and generate the report.

```
$ forklift.py generate-report \
    --report-path forklift.json \
    --list dri-devel \
    --msg-id 'CAPM=9tyNrbap4FG6qstkC5YTznqVebD=ye+4+Z+t42yQnL325A@mail.gmail.com' \
    --common-ancestor v5.9 \
    --bug 'b:12345678'
    --test 'Trust me.'
```

In this case we've also specified a common ancestor between the 2 trees. This
is a commit which is common to both trees. In our case we've chose the 5.9
release tag. While this is not necessary, it allows the forklift utility to
skip common history when looking for commits.

### Cherry-pick the commits
Now that the report has been generated, the utility knows which commits it
should try to backport. You can use the cherry-pick subcommand to start
pulling back patches.

```
$ forklift.py cherry-pick --report-path forklift.json
```

The tool will pause when it reaches a merge conflict. At this point you must
manually fix the conflict and choose a resolution to continue. The menu will
present three options to continue:
```
 c   - Conflict resolved, patch is HEAD. Continue
 s   - Patch was not needed. Skip it.
 q   - Quit
Please resolve the conflict and choose an option:
```

Choice 'c' will add a BACKPORT prefix to the subject of the HEAD commit as
well as the BUG and TEST entries at the bottom of the commit message. Choice
's' will mark the commit as complete in the report and move to the next
commit. Choice 'q' will exit immediately, leaving the conflicting commit
unfinished.

If you leave the conflicting commit unfinished, you can use the
`complete-cherry-pick` subcommand later to mark it complete.

### Resolving conflicts
Conflict resolution is the most time consuming part of forklifting. This
utility can help disect where the conflicts are coming from to expedite
the process.

One will typically want to resolve a conflict in the following order of
operation.

1. Review the entire conflict by using `Print conflict`.
2. Compare the output in HEAD (`Print head`) with the output in remote
(`Print remote`).
3. Once the difference has been identified, use `Blame head` and `Blame remote`
to identify the commit causing the conflict.
4. Resolve the conflict and record the resolution in the commit message.

See the `resolve-conflict` subcommand documentation below for detailed information
and output on the above choices.


## Subcommands
### generate-report

This subcommand creates the report file from a pull request on lore.kernel.org.

Usage:
```
usage: forklift generate-report [-h] [--git-path GIT_PATH] --report-path
                                REPORT_PATH --list LIST --msg-id MSG_ID
                                [--bug BUG] [--test TEST]
                                [--common-ancestor COMMON_ANCESTOR]

optional arguments:
  -h, --help            show this help message and exit
  --git-path GIT_PATH, -g GIT_PATH
                        Path to git repository (if not current dir).
  --report-path REPORT_PATH, -m REPORT_PATH
                        Path to store forklift report file.
  --list LIST           Mailing list from lore.kernel.org/lists.html.
  --msg-id MSG_ID       Message-Id for the pull request to process.
  --bug BUG             Value to use for BUG= in commit descriptions.
  --test TEST           Value to use for TEST= in commit descriptions.
  --common-ancestor COMMON_ANCESTOR
                        Optional common ancestor between the local and remote
                        trees. Improves execution time if provided.
```

To generate your report, provide the subcommand with the project on lore (find
this on the homepage) and the Message-Id value of the pull request message. Finally, choose a location for the report file and pass this in as report-path.

Once invoked, forklift will fetch the remote tag/branch and compare it with the
contents of the local branch. It will write the patches into the report file for
later use.


### cherry-pick
This subcommand cherry-picks the outstanding patches from the report to the
local branch.

Usage:
```
usage: forklift.py cherry-pick [-h] [--git-path GIT_PATH] --report-path
                               REPORT_PATH

optional arguments:
  -h, --help            show this help message and exit
  --git-path GIT_PATH   Path to git repository (if not current dir).
  --report-path REPORT_PATH
                        Path to store forklift report file.
```

To start cherry-picking, invoke the subcommand with an already generated
report. For each commit, the utility will try to determine if the patch exists
in the local branch and will invoke `git cherry-pick` if not.

If the cherry-pick results in an empty commit, this will skip the commit and
continue.

If there is a conflict which needs intervention, the subcommand will stop
cherry-picking and wait. There are typically 2 resolutions:

1. Manually resolve the commit and apply it.
2. If this patch is not needed, discard it.

### complete-cherry-pick
This marks a commit in the report file as backported.

Usage:
```
usage: forklift.py complete-cherry-pick [-h] --report-path REPORT_PATH
                                        [--git-path GIT_PATH]
                                        [--commit COMMIT]

optional arguments:
  -h, --help            show this help message and exit
  --report-path REPORT_PATH
                        Path to store forklift report file.
  --git-path GIT_PATH   Path to git repository (if not current dir).
  --commit COMMIT       Git hash to identify a commit.
```

This can be useful when cherry-picking a file outside of the cherry-pick
subcommand and wants the utility to skip a commit.

### resolve
Aids in resolving a conflict.

_Note:_ this is not tied to the report and can be used for any conflict.

Usage:
```
usage: forklift.py resolve [-h] [--git-path GIT_PATH]

optional arguments:
  -h, --help           show this help message and exit
  --git-path GIT_PATH  Path to git repository (if not current dir).
```

This subcommand has 3 different sub-menus with different options:

#### File Selection menu
```
$ forklift.py resolve

 1   - drivers/gpu/drm/mediatek/mtk_drm_drv.c
 2   - drivers/gpu/drm/rockchip/rockchip_drm_drv.c
 q   - Exit
Choose a file to resolve:
```

This menu allows you to choose which file you'd like to inspect. Enter the
number in the prompt.

#### Conflict Selection Menu
```
Attempting to resolve conflicts in drivers/gpu/drm/mediatek/mtk_drm_drv.c

 1   - Line 334
 bh  - Blame file HEAD
 br  - Blame file remote
 b   - Back
 q   - Quit
Choose a conflict to resolve:
```

Each conflict in the selected file will show up as a menu item. In the example
above, there is only one conflict at line 334.

Additionally, if more context is required, the other options in this menu
allow one to view the `git blame` output for the entire file. `Blame file
HEAD` can be used to view the blame output for the file on disk in the
local branch. `Blame file remote` shows the blame output for the remote file
_before_ the remote commit was applied. This allows one to determine if
there are missing commits causing the conflict.

#### Conflict Inspection Menu
```
 c   - Print conflict
 h   - Print head
 r   - Print remote
 rc  - Print remote commit
 bh  - Blame head
 br  - Blame remote
 b   - Back
 q   - Quit
Choose an action:
```
This menu allows one to inspect each conflict in isolation. The options
are as follows:

- `Print conflict` This outputs the entire conflict from the local file.
```
334   <<<<<<< HEAD
335   static struct drm_driver mtk_drm_driver = {
336     .driver_features = DRIVER_MODESET | DRIVER_GEM | DRIVER_ATOMIC |
337                        DRIVER_RENDER,
338   =======
339   static const struct drm_driver mtk_drm_driver = {
340     .driver_features = DRIVER_MODESET | DRIVER_GEM | DRIVER_ATOMIC,
341   >>>>>>> 70a59dd82959f.. drm/<drivers>: Constify struct drm_driver
```
- `Print head` This outputs the HEAD portion of the conflict from the local
file.
```
334   <<<<<<< HEAD
335   static struct drm_driver mtk_drm_driver = {
336     .driver_features = DRIVER_MODESET | DRIVER_GEM | DRIVER_ATOMIC |
337                        DRIVER_RENDER,
338   =======
```
- `Print remote` This outputs the remote portion of the conflict from the local file.
```
338   =======
339   static const struct drm_driver mtk_drm_driver = {
340     .driver_features = DRIVER_MODESET | DRIVER_GEM | DRIVER_ATOMIC,
341   >>>>>>> 70a59dd82959f.. drm/<drivers>: Constify struct drm_driver
```
- `Print remote commit` This outputs the conflicting commit in entirety.
```

commit 70a59dd82959f828220bf3f5f336e1b8fd931d15
Author: Daniel Vetter <daniel.vetter@ffwll.ch>
Date:   Wed Nov 4 11:04:24 2020 +0100

    drm/<drivers>: Constify struct drm_driver

    Only the following drivers aren't converted:
    - amdgpu, because of the driver_feature mangling due to virt support.
      Subsequent patch will address this.
    - nouveau, because DRIVER_ATOMIC uapi is still not the default on the
      platforms where it's supported (i.e. again driver_feature mangling)
...

diff --git a/drivers/gpu/drm/arm/display/komeda/komeda_kms.c b/drivers/gpu/drm/arm/display/komeda/komeda_kms.c
index 1f6682032ca49..6b99df6963842 100644
--- a/drivers/gpu/drm/arm/display/komeda/komeda_kms.c
+++ b/drivers/gpu/drm/arm/display/komeda/komeda_kms.c
@@ -58,7 +58,7 @@ static irqreturn_t komeda_kms_irq_handler(int irq, void *data)
        return status;
 }

-static struct drm_driver komeda_kms_driver = {
+static const struct drm_driver komeda_kms_driver = {
        .driver_features = DRIVER_GEM | DRIVER_MODESET | DRIVER_ATOMIC,
        .lastclose                      = drm_fb_helper_lastclose,
        DRM_GEM_CMA_DRIVER_OPS

...
```
- `Blame head` This prints the `git blame` output for the HEAD portion of the
conflict (with context).
```
4c6f3196e6ea11 (Alexandre Courbot      2019-07-29 14:33:34 +0900 331)    return drm_gem_prime_import_dev(dev, dma_buf, private->dma_dev);
4c6f3196e6ea11 (Alexandre Courbot      2019-07-29 14:33:34 +0900 332) }
4c6f3196e6ea11 (Alexandre Courbot      2019-07-29 14:33:34 +0900 333)
119f5173628aa7 (CK Hu                  2016-01-04 18:36:34 +0100 335) static struct drm_driver mtk_drm_driver = {
a2c4410ab39d64 (CK Hu                  2016-01-12 16:15:50 +0100 336)    .driver_features = DRIVER_MODESET | DRIVER_GEM | DRIVER_ATOMIC |
a2c4410ab39d64 (CK Hu                  2016-01-12 16:15:50 +0100 337)                       DRIVER_RENDER,
119f5173628aa7 (CK Hu                  2016-01-04 18:36:34 +0100 342)
119f5173628aa7 (CK Hu                  2016-01-04 18:36:34 +0100 343)    .dumb_create = mtk_drm_gem_dumb_create,
119f5173628aa7 (CK Hu                  2016-01-04 18:36:34 +0100 344)
```

- `Blame remote` This prints the change the remote commit is attempting to make
to the code and the `git blame` output for the remote portion of the conflict
_before_ the remote commit was applied.

```
>>>>> Possible result 0, score=0
-- diff
        return drm_gem_prime_import_dev(dev, dma_buf, private->dma_dev);
 }

-static struct drm_driver mtk_drm_driver = {
+static const struct drm_driver mtk_drm_driver = {
        .driver_features = DRIVER_MODESET | DRIVER_GEM | DRIVER_ATOMIC,

        .dumb_create = mtk_drm_gem_dumb_create,
-- blame
4c6f3196e6ea11 (Alexandre Courbot      2019-07-29 14:33:34 +0900 322) }
4c6f3196e6ea11 (Alexandre Courbot      2019-07-29 14:33:34 +0900 323)
119f5173628aa7 (CK Hu                  2016-01-04 18:36:34 +0100 324) static struct drm_driver mtk_drm_driver = {
0424fdaf883a68 (Daniel Vetter          2019-06-17 17:39:24 +0200 325)    .driver_features = DRIVER_MODESET | DRIVER_GEM | DRIVER_ATOMIC,
119f5173628aa7 (CK Hu                  2016-01-04 18:36:34 +0100 326)
119f5173628aa7 (CK Hu                  2016-01-04 18:36:34 +0100 327)    .dumb_create = mtk_drm_gem_dumb_create,
119f5173628aa7 (CK Hu                  2016-01-04 18:36:34 +0100 328)
```

By inspecting the above, we can see the conflict resulted from the different
values of `.driver_features` between upstream and downstream. When we inspect
those commits, we see that downstream patch `a2c4410ab39d6 ("CHROMIUM:
drm/mediatek: Add interface to allocate Mediatek GEM buffer.")` introduced the
`DRIVER_RENDER` flag which causes the conflict.

In some cases there are multiple results. This is because mapping a conflict in
a local file to remote blame is not 1:1. The utility will attempt to show the
most relevant results. If all else fails, one can list the entire blame output
in the file menu.
