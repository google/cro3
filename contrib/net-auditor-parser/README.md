This script parses the output of the auditd daemon to print how much the
connect/send/sendmsg/sendmmsg syscalls are being used on a per-process basis.
Writing the statistics in the stdout stream in a decreasing order.

Run:
$ python3 parser.py data/sample.txt
