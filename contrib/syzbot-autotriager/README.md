# Autotriager

A set of utilities that assist in triaging syzkaller bugs reported for
Chrome OS kernels on IssueTracker.

## Library dependencies

* Beautiful Soup bs4([Link](https://pypi.org/project/beautifulsoup4/))
* Python requests([Link](http://docs.python-requests.org/en/master/))
* Python dataset([Link](https://dataset.readthedocs.io/en/latest/))

## Usage

* Generate local caches of issuetracker bugs, and information from
  https://syzkaller.appspot.com. Also generate a local cache of commit
  information from various linux kernels.

  Edit config.py and ensure that CROS_ROOT points to your local copy of
  chromiumos source, and that LINUX points to your local copy of linux
  kernel source code. Next, run:
```bash
$ ./dbgen.py --fetchall --hotlistid <issuetracker_hotlistid>
```

  Note that if you are in a hurry, it might be best to simply run the
  following commands, each in a seperate console instance:
```bash
$ ./dbgen.py --it --hotlistid <issuetracker_hotlistid>
$ ./dbgen.py --commits
$ ./dbgen.py --syzweb
```

* Start off autotriager as follows:
```bash
$ ./run4.py
```

* If you would like autotriager to match stacktraces(experimental) use:
```bash
$ ./run4.py --mst
```

# Patchfinder

A script that locates potentially security related commits that are present
in the upstream kernel, but not in the stable kernels.

## Library dependencies

* Python dataset([Link](https://dataset.readthedocs.io/en/latest/))
* Utility functions from Autotriager(see above)

## Usage

* Build your desired kernel(eg: coral) and fetch the object files created as part
  of the build process.
```bash
$ find . -name "*.o" >> OBJFILES
```

* Inside config.py update LINUX_STABLE with the correct path to your linux stable tree.

* Run patchfinder. Use the `--cachestable` flag only on your first run, or
  whenever you wish to refresh the cache.
```bash
$ ./patchfinder.py --kver 44 --objfiles <path/to/OBJFILES> --cachestable
```

Patchfinder will print out commits that:
* are present in the upstream kernel but not in stable
* affect source files corresponding to the object files listed in
  OBJFILES
* have a "Fixes:" tag corresponding to a commit that is already present in
  the stable kernel
