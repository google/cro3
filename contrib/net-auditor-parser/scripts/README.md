These scripts are for automating the syscall usage analysis flow.

main.sh -
    Intended to be run from the host. This is the core script to automate the
    full experiment. No additional user involvement is needed, apart from
    running this script.

run_monitoring.sh -
    Intended to be run from the client, invoked by the main.sh script.
    Simulates the normal user behavior, then collecting all auditd logs and
    running parse.py script to show the syscall histograms.

Run:
$ bash main.sh
