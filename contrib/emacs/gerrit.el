;; -*- lexical-binding: t -*-

;; Copyright 2020 The Chromium OS Authors. All rights reserved.
;; Use of this source code is governed by a BSD-style license that can be
;; found in the LICENSE file.
(require 'request)
(require 'xml)

;; TODO this is test code to be removed in future CL.
;; The following will become user configuration options.
(setq test-user "aaronmassey@chromium.org")
(setq test-host "chromium-review.googlesource.com")
(setq test-repo-root (file-name-as-directory "~/chromiumos"))
(setq test-repo-manifest-path (expand-file-name ".repo/manifests/default.xml" test-repo-root))
;; TODO Make our parser self-discoverable by project instead of a parameter.
(setq test-manifest-parser (expand-file-name "src/platform/dev/contrib/emacs/manifest_parser"
                                             test-repo-root))
(defun gerrit-init ()
  (gerrit--init-global-comment-map test-host test-user)
  (gerrit--init-global-repo-project-path-map test-manifest-parser test-repo-manifest-path))


(defvar gerrit--change-to-filepath-comments nil
  "Map containing with change => filepath => comments.
filepath is from git project root, for the given change.")


(defvar gerrit--project-branch-pair-to-projectpath nil
  "Map showing relative path from repo root to project.
Is of the form (project . dest-branch) => path-from-repo-root.")


(cl-defun gerrit--fetch-recent-changes (host user &optional (count 3))
  "Fetches recent changes as ChangeInfo entities.
host - Gerrit server address
user - the user who owns the recent changes
count (optional) - the number of recent changes, default is 3
Fetch recent changes that are not abandoned/merged, and
thus are actionable, returns an array of hashtables that
represent Gerrit ChangeInfo entities."
  (request-response-data
   (request
     (format "https://%s/changes/" host)
     ;; We don't use "status:reviewed" because that only counts reviews after latest patch,
     ;; but we may want reviews before the latest patch too.
     :params `(("q" . ,(format "owner:%s status:open" user))
               ("n" . ,(format "%d" count)))
     :sync t
     :parser 'gerrit--request-response-json-parser)))


(defun gerrit--request-response-json-parser ()
  "Response parsing callback for use with request.el
parses Gerrit response json payload by removing the
embedded XSS protection string before using a real json parser."
  (json-parse-string (replace-regexp-in-string "^[[:space:]]*)]}'" "" (buffer-string))))


(defun gerrit--fetch-comments (host change)
  "Gets recent comments for open Gerrit CLs.
Returns a map of the form path => sequence of comments,
where path is the filepath from the gerrit project root
and each comment represents a CommentInfo entity from Gerrit"
  (request-response-data
   (request
     (format "https://%s/changes/%s~master~%s/comments"
             host
             (url-hexify-string (gethash "project" change))
             (gethash "change_id" change))
     :sync t
     :parser 'gerrit--request-response-json-parser)))


(defun gerrit--fetch-change-to-file-to-comments (host user)
  "Returns a map of maps of the form:
change => filepath => array(CommentInfo Map),
where filepath is from the nearest git root for a file.
Only fetches recent changes for open CLs."
  (let ((out-map (make-hash-table :test 'equal)))
    (loop for change across (gerrit--fetch-recent-changes host user) do
          (setf (gethash change out-map)
                (gerrit--fetch-comments host change)))
    out-map))


(defun gerrit--init-global-comment-map (host user)
  "Inits `gerrit--change-to-filepath-comments`."
  (setf gerrit--change-to-filepath-comments
        (gerrit--fetch-change-to-file-to-comments
         host user)))


(cl-defun gerrit--project-branch-pair-to-path-map (path-to-manifest-parser-exec abs-path-to-manifest)
  "Return map (project . dest-branch) => path-from-repo-root.
Parses the manifest given manifest file using the given parser executable.
Assumes that stdout of parser is a Lisp alist of the form:
((project . dest-branch) . path-from-repo-root)."
  (let (parsed-alist
        (output (make-hash-table :test 'equal))
        (tmp-buffer-name "*gerrit-temp--buffer*"))

    (when (get-buffer tmp-buffer-name)
      (kill-buffer tmp-buffer-name))

    (unless (= 0 (call-process path-to-manifest-parser-exec
                               nil
                               tmp-buffer-name
                               nil
                               abs-path-to-manifest))
      (message "Error parsing manifest file investigate %s" tmp-buffer-name)
      (cl-return-from gerrit--project-branch-pair-to-path-map nil))

    (save-excursion
      (set-buffer tmp-buffer-name)
      (goto-char (point-min))
      (setf parsed-alist (read (current-buffer)))
      (kill-buffer tmp-buffer-name))

    (loop for item in parsed-alist do
          (setf (gethash (car item) output) (cdr item)))

    output))


(defun gerrit--init-global-repo-project-path-map (path-to-manifest-parser-exec
                                                  abs-path-to-manifest)
  "Initializes `gerrit--project-branch-pair-to-projectpath`."
  ;; Here we use Python expat sax parser as it's considerably faster.
  (setf gerrit--project-branch-pair-to-projectpath (gerrit--project-branch-pair-to-path-map
                                                    path-to-manifest-parser-exec
                                                    abs-path-to-manifest)))


(defun gerrit--get-abs-path-to-file (filepath-from-project-git-root
                                     project-branch-pair
                                     abs-path-to-repo-root)
  "Returns full system path of the first argument.
`gerrit--project-branch-pair-to-projectpath` must be initialized."
  (expand-file-name
   filepath-from-project-git-root
   (directory-file-name
    (expand-file-name
     (gethash (cons (gethash "project" project-branch-pair)
                    (gethash "branch" project-branch-pair))
              gerrit--project-branch-pair-to-projectpath)
     abs-path-to-repo-root))))


(provide 'repo-gerrit)
