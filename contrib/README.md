# Unsupported Chrome OS dev scripts

This directory is a place that developers can put scripts that are useful
to them and that might be useful to other developers.

A few notes about what's here:
* Nothing here may be used by build scripts.  It's expected to only contain
  scripts that are run manually.
* Nobody in the build team maintains these files.  If something is broken,
  you can try using the git history to find someone to help you, but even
  better you should upload a fix yourself.
* Chrome OS infrastructure makes no promises to keep scripts in here working.
  AKA: if you rely on some tool in "chromite", or on some Google server, or
  something else official.  ...and if that thing changes in a way that breaks
  you.  ...then it's up to you to change your script.  The change that broke
  you will not be reverted.

That being said: enjoy.
