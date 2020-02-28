/*
Copyright 2020 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.

Module containing script to initialize database table schemas.
*/

/*
This script should ONLY be ran when the CloudSQL database is being created.
This initializes the schema tables and columns that are stored in cloudsql.

To run this script use the following cmd:
`mysql -u linux_patches_robot -p --host 127.0.0.1 -p linuxdb < initialize_sql_tables.sql`
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
  sha VARCHAR(40),
  branch VARCHAR(5) NOT NULL,
  upstream_sha VARCHAR(40) NOT NULL,
  patch_id CHAR(40) NOT NULL,
  description TEXT NOT NULL,
  FOREIGN KEY (upstream_sha) REFERENCES linux_upstream_commits(sha),
  PRIMARY KEY (sha)
);
CREATE INDEX patch_id ON linux_stable (patch_id);

/*
Cannot put foreign key on upstream_sha since it may contain SHA's from
maintainer trees which haven't been merged into upstream yet.
*/
CREATE TABLE IF NOT EXISTS linux_chrome (
  sha VARCHAR(40),
  branch VARCHAR(5) NOT NULL,
  upstream_sha VARCHAR(40),
  patch_id CHAR(40) NOT NULL,
  description TEXT NOT NULL,
  PRIMARY KEY (sha)
);
CREATE INDEX upstream_sha ON linux_chrome (upstream_sha);
CREATE INDEX patch_id ON linux_chrome (patch_id);


/*
Possibility for date to see history of latest fetches.
*/
CREATE TABLE IF NOT EXISTS previous_fetch (
  linux ENUM('linux-stable', 'linux-chrome', 'linux-upstream'),
  branch VARCHAR(20),
  sha_tip VARCHAR(40) NOT NULL,
  PRIMARY KEY (linux, branch)
);


CREATE TABLE IF NOT EXISTS stable_fixes (
  kernel_sha VARCHAR(40), /*stable sha*/
  fixedby_upstream_sha VARCHAR(40),
  branch VARCHAR(5) NOT NULL,
  entry_time DATETIME NOT NULL,
  close_time DATETIME,
  fix_change_id CHAR(41),
  status ENUM('OPEN', 'MERGED', 'ABANDONED', 'CONFLICT') NOT NULL,
  reason VARCHAR(120),
  FOREIGN KEY (kernel_sha) REFERENCES linux_stable(sha),
  FOREIGN KEY (fixedby_upstream_sha) REFERENCES linux_upstream_commits(sha),
  PRIMARY KEY (kernel_sha, fixedby_upstream_sha)
);


CREATE TABLE IF NOT EXISTS chrome_fixes (
  kernel_sha VARCHAR(40), /*chrome sha*/
  fixedby_upstream_sha VARCHAR(40),
  branch VARCHAR(5) NOT NULL,
  entry_time DATETIME NOT NULL,
  close_time DATETIME,
  fix_change_id CHAR(41),
  status ENUM('OPEN', 'MERGED', 'ABANDONED', 'CONFLICT') NOT NULL,
  reason VARCHAR(120),
  FOREIGN KEY (kernel_sha) REFERENCES linux_chrome(sha),
  FOREIGN KEY (fixedby_upstream_sha) REFERENCES linux_upstream_commits(sha),
  PRIMARY KEY (kernel_sha, fixedby_upstream_sha)
);
