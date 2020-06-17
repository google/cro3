;; -*- lexical-binding: t -*-

;; Copyright 2020 The Chromium OS Authors. All rights reserved.
;; Use of this source code is governed by a BSD-style license that can be
;; found in the LICENSE file.
(require 'request)

;; TODO this is test code to be removed in future CL.
(setq test-user "jrosenth")
(setq test-host "chromium-review.googlesource.com")
(setq test-repo-root (file-name-as-directory "~/chromiumos"))
(setq test-repo-manifest-path (expand-file-name ".repo/manifests/default.xml" test-repo-root))

(cl-defun gerrit--fetch-recent-changeid-project-pairs (host user &optional (count 3))
  "Fetches recent changes as changeid project dotted pairs.
host - Gerrit server address
user - the user who owns the recent changes
count (optional) - the number of recent changes, default is 3
Fetch recent changes that are not abandoned/merged, and
thus are actionable, returns a list of dotted pairs
of the form (change-id . project)."
  (let ((response
         (request
           (format "https://%s/changes/" host)
           ;; We don't use "status:reviewed" because that only counts reviews after latest patch,
           ;; but we may want reviews before the latest patch too.
           :params `(("q" . ,(format "owner:%s status:open" user))
                     ("n" . ,(format "%d" count)))
           :sync t
           :parser 'gerrit--request-response-json-parser
           :success (lambda (&key data error-thrown &allow-other-keys)
                       (when error-thrown
                         (message "%s" error-thrown))))))
    (loop for change across (request-response-data response)
          collect `(,(gethash "change_id" change) . ,(gethash "project" change)))))

(defun gerrit--request-response-json-parser ()
  "Response parsing callback for use with request.el
parses Gerrit response json payload by removing the
embedded XSS protection string before using a real json parser."
  (json-parse-string (replace-regexp-in-string "^[[:space:]]*)]}'" "" (buffer-string))))


(defun gerrit--get-unresolved-comments (host project change-id)
  "Gets recent unresolved comments for open Gerrit CLs.
Returns a map of the form path => sequence of comments,
where path is the filepath from the gerrit project root
and each comment represents a CommentInfo entity from Gerrit"
  (let* ((response
          (request
            (format "https://%s/changes/%s~master~%s/comments"
                    host
                    (url-hexify-string project)
                    change-id)
            :sync t
            :parser 'gerrit--request-response-json-parser
            :success (lambda (&key data error-thrown &allow-other-keys)
                       (when error-thrown
                         (message "%s" error-thrown)))))
         (out-map (request-response-data response)))
    ;; We only want the user to see unresolved comments.
    (loop for key in (hash-table-keys out-map) do
          ;; We explicitly check if not true because the value may be ':false'
          ;; which is technically evals to true as it is not nil.
          (delete-if (lambda (comment) (not (eql t (gethash "unresolved" comment))))
                     (gethash key out-map)))
    out-map))


(defun gerrit--fetch-map-changeid-project-pair-to-unresolved-comments (host user)
  "Returns a map of maps of the form:
(change-id . project) => filepath => Sequence(CommentInfo Map),
where filepath is from the nearest git root for a file."
  ;; The return value is intended as a local cache of comments for user's recent changes.
  (let ((out-map (make-hash-table :test 'equal)))
    (loop for pair in (gerrit--fetch-recent-changeid-project-pairs host user) do
          (setf (gethash pair out-map)
                (gerrit--get-unresolved-comments host (cdr pair) (car pair))))
    out-map))
