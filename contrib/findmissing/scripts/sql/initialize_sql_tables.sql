/*
Copyright 2020 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.

Module containing script to initialize database table schemas.
*/


CREATE TABLE IF NOT EXISTS linux_upstream_commits (
  sha VARCHAR(40),
  description TEXT NOT NULL,
  patch_id CHAR(40) NOT NULL,
  PRIMARY KEY (sha)
);
CREATE INDEX patch_id ON linux_upstream_commits (patch_id);


CREATE TABLE IF NOT EXISTS linux_upstream_fixes (
  upstream_sha VARCHAR(40),
  fixedby_upstream_sha VARCHAR(40),
  FOREIGN KEY (upstream_sha) REFERENCES linux_upstream_commits(sha),
  FOREIGN KEY (fixedby_upstream_sha) REFERENCES linux_upstream_commits(sha),
  PRIMARY KEY (upstream_sha, fixedby_upstream_sha)
);
CREATE INDEX upstream_sha ON linux_upstream_fixes (upstream_sha);


CREATE TABLE IF NOT EXISTS linux_stable (
  stable_sha VARCHAR(40),
  branch VARCHAR(5) NOT NULL,
  upstream_sha VARCHAR(40) NOT NULL,
  patch_id CHAR(40) NOT NULL,
  description TEXT NOT NULL,
  FOREIGN KEY (upstream_sha) REFERENCES linux_upstream_commits(sha),
  PRIMARY KEY (stable_sha)
);


/*
Cannot put foreign key on upstream_sha since it may contain SHA's from
maintainer trees which haven't been merged into upstream yet.
*/
CREATE TABLE IF NOT EXISTS linux_chrome (
  chrome_sha VARCHAR(40),
  change_id CHAR(41),
  branch VARCHAR(5) NOT NULL,
  upstream_sha VARCHAR(40),
  patch_id CHAR(40) NOT NULL,
  description TEXT NOT NULL,
  PRIMARY KEY (chrome_sha)
);
CREATE INDEX upstream_sha ON linux_chrome (upstream_sha);
CREATE INDEX patch_id ON linux_chrome (patch_id);


/*
Possibility for date to see history of latest fetches.
*/
CREATE TABLE IF NOT EXISTS previous_fetch (
  linux ENUM('linux_stable', 'linux_chrome', 'linux_upstream') NOT NULL,
  branch VARCHAR(5) NOT NULL,
  sha_tip VARCHAR(40) NOT NULL
);


CREATE TABLE IF NOT EXISTS stable_fixes (
  stable_sha VARCHAR(40),
  fixedby_upstream_sha VARCHAR(40),
  branch VARCHAR(5) NOT NULL,
  entry_time DATETIME NOT NULL,
  close_time DATETIME,
  fix_change_id CHAR(41),
  status ENUM('OPEN', 'MERGED', 'ABANDONED', 'CONFLICT') NOT NULL,
  reason VARCHAR(120),
  FOREIGN KEY (stable_sha) REFERENCES linux_stable(stable_sha),
  FOREIGN KEY (fixedby_upstream_sha) REFERENCES linux_upstream_commits(sha),
  PRIMARY KEY (stable_sha, fixedby_upstream_sha)
);


CREATE TABLE IF NOT EXISTS chrome_fixes (
  chrome_sha VARCHAR(40),
  fixedby_upstream_sha VARCHAR(40),
  branch VARCHAR(5) NOT NULL,
  entry_time DATETIME NOT NULL,
  close_time DATETIME,
  fix_change_id CHAR(41),
  status ENUM('OPEN', 'MERGED', 'ABANDONED', 'CONFLICT') NOT NULL,
  reason VARCHAR(120),
  FOREIGN KEY (chrome_sha) REFERENCES linux_chrome(chrome_sha),
  FOREIGN KEY (fixedby_upstream_sha) REFERENCES linux_upstream_commits(sha),
  PRIMARY KEY (chrome_sha, fixedby_upstream_sha)
);
