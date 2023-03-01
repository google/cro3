# Setup
To setup the callbox, copy all files from this directory to anywhere in the callbox(e.g. /tmp/).

Run the setup script corresponding to the configuration you want for the callbox.

Example:
>cd /tmp; bash setup4G.sh


# Some basic commands to troubleshoot issues on the callbox:
Open the callbox software monitors
>screen -x lte

Switch between enb/mme monitors
>Ctrl+a 0, Ctrl+a 1

Exist screen
>Ctrl+a d

Restart all services
>service lte restart
