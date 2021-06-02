;; -*- lexical-binding: t -*-
;; Copyright 2020 The Chromium OS Authors. All Rights Reserved.
;; Use of this source code is governed by a BSD-style license that can be
;; found in the LICENSE file.

;; repo-transient.el --- Transient menus to use some repo commands within magit
;;

;; This file is not part of GNU Emacs.

(require 'term)
(require 'transient)
(require 'magit-process)

(define-infix-argument repo:current-project ()
  :description "Current Project"
  :class 'transient-switch
  :key "-c"
  :argument ".")

(define-infix-argument repo:all-projects ()
  :description "All Projects"
  :class 'transient-switch
  :key "-A"
  :argument "--all")

;; TODO(jrosenth): the below keybindings don't work ... might be
;; something with evil mode
(defun repo--term-insert-yes ()
  (interactive)
  (term-send-string (get-buffer-process (current-buffer))
                    "yes\n"))

(defun repo--term-insert-no ()
  (interactive)
  (term-send-string (get-buffer-process (current-buffer))
                    "no\n"))

(defvar repo-term-mode-map
  (let ((map (copy-keymap magit-mode-map)))
    (define-key map (kbd "y") #'repo--term-insert-yes)
    (define-key map (kbd "n") #'repo--term-insert-no)
    (set-keymap-parent map magit-mode-map)
    map))

(define-derived-mode repo-term-mode term-mode "Repo Output"
  "Derived terminal mode for repo output.")

(defun repo--run-interactively (&rest args)
  (let ((buf (apply #'make-term "repo-output" "repo" nil args)))
    (with-current-buffer buf
      (repo-term-mode))
    (magit-display-buffer buf)))

(defun repo-sync (args)
  "Run a repo sync command."
  (interactive (list (transient-args 'repo-sync-menu)))
  (apply #'repo--run-interactively "sync" args))

(defun repo-rebase (args)
  "Run a repo rebase command."
  (interactive (list (transient-args 'repo-rebase-menu)))
  (apply #'repo--run-interactively "rebase" args))

(define-transient-command repo-sync-menu ()
  "Transient menu for repo sync."
  ["Project"
   (repo:current-project)]
  ["Commands"
   ("y" "Sync" repo-sync)])

(define-transient-command repo-rebase-menu
  "Transient menu for repo rebase."
  ["Project"
   (repo:current-project)]
  ["Commands"
   ("r" "Rebase" repo-rebase)])

(defun repo-start (branch-name args)
  "Run a repo start command."
  (interactive (list "sBranch name: ")
               (transient-args 'repo-start-menu))
  (apply #'magit-call-process "repo" "start" args))

(defun repo-start-temp (args)
  "Run a repo start command with an auto-generated branch name."
  (interactive (transient-args 'repo-start-menu))
  (repo-start (format-time-string "temp-%Y-%m-%dT%H:%M:%S")
              args))

(define-transient-command repo-start-menu
  "Transient menu for repo start."
  ["Project"
   (repo:all-projects)]
  ["Commands"
   ("s" "Start new development branch" repo-start)
   ("t" "Start temporary development branch" repo-start-temp)])

(defun repo-upload (args)
  "Run a repo upload command."
  (cond
   ((and (not (member "--label=Verified+1" args))
         (not (member "--label=Verified-1" args)))
    (repo-upload `(,@args "--label=Verified+1")))
   ((and (not (member "--cbr" args))
         (not (seq-some (lambda (arg)
                          (string-prefix-p "--br=" arg))
                        args)))
    (repo-upload `(,@args "--cbr")))
   (t (apply #'repo--run-interactively "upload" args))))

(defun repo-upload-current (args)
  "Run a repo upload command in the current project."
  (interactive (list (transient-args 'repo-upload-menu)))
  (repo-upload (cons "." args)))

(defun repo-upload-all (args)
  "Run a repo upload command for all projects."
  (interactive (list (transient-args 'repo-upload-menu)))
  (repo-upload args))

(define-infix-argument repo:--re ()
  :description "Set reviewers"
  :class 'transient-option
  :key "-r"
  :argument "--re=")

(define-infix-argument repo:--cc ()
  :description "Set reviewers"
  :class 'transient-option
  :key "-c"
  :argument "--cc=")

(define-infix-argument repo:--br ()
  :description "Local branch to upload"
  :class 'transient-option
  :key "-b"
  :argument "--br="
  :reader 'magit-transient-read-revision)

(define-infix-argument repo:--dest ()
  :description "Remote destination branch"
  :class 'transient-option
  :key "-D"
  :argument "--dest=")

(define-infix-argument repo:--hashtag ()
  :description "Hashtags"
  :class 'transient-option
  :key "-h"
  :argument "--hashtag=")

(define-transient-command repo-upload-menu ()
  "Transient menu for repo upload."
  ["People"
   (repo:--re)
   (repo:--cc)
   ("-E" "Don't send emails" "--no-emails")]
  ["Upload Hooks"
   ("-n" "Skip upload hooks" "--no-verify")
   ("-i" "Ignore failures in upload hooks" "--ignore-hooks")]
  ["Labels"
   ("-a" "Label Auto-Submit+1" "--label=Auto-Submit+1")
   ("-d" "Label Commit-Queue+1 (dry run)" "--label=Commit-Queue+1")
   ("-Q" "Label Commit-Queue+2" "--label=Commit-Queue+2")
   ("-B" "Label Verified-1 (BAD)" "--label=Verified-1")
   ("-S" "Sticky CQ+2" "--hashtag=stickycq")]
  ["CL Options"
   ("-w" "Work in Progress" "--wip")
   ("-p" "Private" "--private")
   (repo:--hashtag)]
  ["Branches"
   (repo:--br)
   (repo:--dest)]
  ["Upload"
   ("u" "Upload current project" repo-upload-current)
   ("U" "Upload all projects" repo-upload-all)])

(define-transient-command repo-main-menu ()
  "Transient menu for repo commands."
  ["Subcommands"
   ("y" "sync" repo-sync-menu)
   ("r" "rebase" repo-rebase-menu)
   ("s" "start" repo-start-menu)
   ("u" "upload" repo-upload-menu)])

(provide 'repo-transient)
