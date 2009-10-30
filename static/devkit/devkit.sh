#!/bin/bash

set -e

DEVKIT_URL=$(grep ^CHROMEOS_DEVSERVER /etc/lsb-release | cut -d = -f 2-) 

if [ "x" = "x$DEVKIT_URL" ]
then
  echo "No devkit server specified in /etc/lsb-release"
  exit 1
fi

sudo mount -o remount,rw /

sudo rm -f /etc/init/software-update.conf

sudo echo "deb http://archive.ubuntu.com/ubuntu karmic main restricted multiverse universe" >> /tmp/devsrc 

sudo cp /tmp/devsrc /etc/apt/sources.list
sudo mkdir -p /var/cache/apt/archives/partial
sudo mkdir -p /var/log/apt
sudo apt-get update

sudo apt-get install -y vim
sudo apt-get install -y sshfs
sudo apt-get install -y gdb

sudo wget $DEVKIT_URL/vimrc.txt
sudo cp ./vimrc.txt ~/.vimrc
sudo chmod a+r ~/.vimrc
