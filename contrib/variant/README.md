# Programs to Create a New Variant of a Baseboard

Creating a new variant of a baseboard, e.g. making the Kohaku variant of the
Hatch baseboard, involves basically cloing the baseboard under a new name.
This involves tasks in multiple repositories. There is a shell script (and in
one case, some supporting python code) for each of these tasks.

Please note that all of these scripts and programs must be run inside the
chroot environment.

Before running any of these programs, please ensure that you have successfully
synced your tree (`repo sync`) and that your toolchain is up-to-date
(`update_chroot`). Each shell script will create a branch to track the new
variant, and it is vital that these branches are based off cros/master.

`new_variant.py` will run each of the shell scripts in turn, as well as
building the code (via `emerge`). new\_variant.py requires a --board and
--variant parameter, and allows an optional --bug parameter, e.g.
```
$ ./new_variant.py --board=hatch --variant=sushi --bug=b:12345
```
to create the "sushi" variant of the "hatch" baseboard, and associate all of
the commits with bug #12345 in Buganizer. If you omit the `--bug` parameter,
the commit messages will include `BUG=None`.

At a certain point in the program flow, `new_variant.py` will exit with a
message that you need to run `gen_fit_image.sh` outside of the chroot; open
a new terminal window, change to the appropriate directory, and run the script
indicated. When it has finished, you can return to the chroot environment and
run `./new_variant.py --continue` to resume the program.

These programs are a work in progress. For any questions, problems, or
suggestions, please contact `chromeos-scale-taskforce@google.com`.
