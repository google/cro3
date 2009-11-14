# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import web
from datetime import datetime
import time 

class BuildObject:
  """
    Common base class that defines key paths in the source tree.
  """
  def __init__(self, root_dir, static_dir):
    self.app_id = "87efface-864d-49a5-9bb3-4b050a7c227a"
    self.root_dir = root_dir
    self.scripts_dir = "%s/scripts" % self.root_dir
    self.static_dir = static_dir
    self.x86_pkg_dir = "%s/build/x86/local_packages" % self.root_dir

  def AssertSystemCallSuccess(self, err, cmd="unknown"):
    """
      TODO(rtc): This code should probably live somewhere else.
    """
    if err != 0:
      raise Exception("%s failed to execute" % cmd)
    

class BuildUtil(BuildObject):

  def GetPackageName(self, pkg_path):
    cmd = "cat %s/debian/control | grep Package: | cut -d \" \" -f 2-" % pkg_path
    return os.popen(cmd).read().strip() 

  def GetLastBuildTime(self, pkg_name):
    # TODO(rtc): convert this to local time. 
    cmd = "stat -c %s %s/%s*" % ("%Y", self.x86_pkg_dir, pkg_name)
    utc_time = os.popen(cmd).read().strip()
    return datetime.fromtimestamp(int(utc_time))

  def GetPackageBuildPath(self, pkg_name):
    cmd = "stat -c %s %s/%s*" % ("%n", self.x86_pkg_dir, pkg_name)
    return os.popen(cmd).read().strip()

  def GetPackageBuildFile(self, build_path):
    return build_path.replace(self.x86_pkg_dir + "/", "")

  def BuildPackage(self, pkg="all"):
    """
      Builds the given package and copies the output to the static dir so that
      it can be downloaded. 
      
      If pkg=all is specified then the kernel and all platform packages
      will be built. A new system image will also be created.

      If pkg=packages is specified then all platform packages
      will be built and a new system image will be created.
    """
    if pkg == "all":
      err = os.system("%s/build_all.sh" % self.scripts_dir)
      self.AssertSystemCallSuccess(err)
      return None

    if pkg == "packages":
      err = os.system("%s/build_platform_packages.sh" % self.scripts_dir)
      self.AssertSystemCallSuccess(err)
      err = os.system("%s/build_image.sh" % self.scripts_dir)
      self.AssertSystemCallSuccess(err)
      return None

    pkg_properties = self.GetPackages().get(pkg, None)
    if pkg_properties == None:
      raise Exception("Unknown package name %s" % pkg)

    cmd = "%s/make_pkg.sh" % pkg_properties.get("source_path")
    err = os.system(cmd)
    self.AssertSystemCallSuccess(err, cmd)

    # Reset pkg_properties after building so that output_path and
    # output_file_name are set up properly.
    pkg_properties = self.GetPackages().get(pkg, None)

    cmd = "cp %s %s" % (pkg_properties.get("output_path"), self.static_dir)
    err = os.system(cmd)
    self.AssertSystemCallSuccess(err, cmd)

    return pkg_properties.get("output_file_name")


  def GetPackages(self):
    """
      Lists all of the packages that can be built with a make_pkg.sh script.

      Returns a dictionary with the following keys
        name: the name of the package. 
        build_time: the time the package was last built (in UTC).
        source_path: the path to the package in the source tree. 
        output_path: the path to the deb created by make_pkg.sh.
        output_file_name: the name of the deb created by make_pkg.sh
    """
    pkgs = {} 
    cli = os.popen("find %s -name make_pkg.sh" % self.root_dir).read().split('\n')
    for pkg in cli:
      if pkg == "":
        continue
      pkg_path = pkg.replace("/make_pkg.sh", "", 1)
      pkg_name = self.GetPackageName(pkg_path)
      if pkg_name == "":
        web.debug("unable to find a package info for %s" % pkg_path)
        continue

      build_path = self.GetPackageBuildPath(pkg_name)

      build_time = None
      build_file = None
      if build_path != "":
        build_time = self.GetLastBuildTime(pkg_name)
        build_file = self.GetPackageBuildFile(build_path)

      pkgs[pkg_name] = {
        "name": pkg_name,
        "build_time": build_time,
        "source_path": pkg_path,
        "output_path": build_path,
        "output_file_name": build_file
      }
    return pkgs
