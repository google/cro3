;; cros-sdk-tramp.el --- TRAMP integration for cros_sdk

;; Copyright 2022 The Chromium OS Authors. All rights reserved.
;; Use of this source code is governed by a BSD-style license that can be
;; found in the LICENSE file.

(require 'tramp)

(defgroup cros-sdk-tramp nil "TRAMP integration for cros_sdk."
  :prefix "cros-sdk-tramp-"
  :group 'applications)

(defcustom cros-sdk-tramp-src-path
  (locate-dominating-file load-file-name "src/platform/dev/contrib/OWNERS")
  "Location of chrome OS source tree. Needed for cros_sdk.

Default value is inferred from the location of this file."
  :type 'string
  :group 'cros-sdk-tramp)

(defconst cros-sdk-tramp-method "cros")

(defun cros-sdk-tramp-add-method ()
  "Add cros-sdk tramp method."
  ;; TODO(uekawa): This asks for username and password and hostname, but only
  ;; the password (for sudo) is used.
  (add-to-list 'tramp-methods
               `(,cros-sdk-tramp-method
                 (tramp-login-program
                  ,(concat "/bin/sh -c 'cd " cros-sdk-tramp-src-path " && cros_sdk'"))
                 (tramp-remote-shell "/bin/sh")
                 (tramp-remote-shell-args ("-i" "-c")))))

(eval-after-load 'tramp
  '(progn
     (cros-sdk-tramp-add-method)))

;; TODO(uekawa): there must be a better per-connection way to set this
(add-to-list 'tramp-remote-path 'tramp-own-remote-path)

(defun cros-sdk-tramp--match-cros (filename)
  (string-match "^/cros:.*:/mnt/host/source/\\(.*\\)$" filename))

(defun cros-sdk-tramp--cros-filename (filename)
  "Get the cros sdk filename."
  (if (cros-sdk-tramp--match-cros filename)
      filename
    (cros-sdk-tramp--rotate-filename filename)))

(defun cros-sdk-tramp--rotate-filename (current)
  "Returns the file name after rotating between cros-sdk and regular file."
  (let* ((cros-match (cros-sdk-tramp--match-cros current)))
    (if cros-match
        (let* ((relative-path (match-string 1 current))
               (abs-path
                (concat
                 (file-name-as-directory cros-sdk-tramp-src-path)
                 relative-path)))
          ;; was in cros_sdk
          abs-path)
      ;; Was in a regular directory
      (let* ((old-full-path (expand-file-name current))
             (old-root-path (expand-file-name cros-sdk-tramp-src-path))
             (old-relative-path-match-re (concat "^" (regexp-quote old-root-path) "\\(.*\\)$"))
             (old-relative-path-match
              (string-match old-relative-path-match-re
                            old-full-path))
             (old-relative-path (match-string 1 old-full-path))
             (new-full-path (concat "/cros::/mnt/host/source/" old-relative-path)))
        new-full-path))))

(defun cros-sdk-tramp-rotate-among-files ()
  "Rotate among same file inside or outside cros_sdk chroot.
They should be the same file."
  (interactive)
  (let* ((current (or (buffer-file-name) default-directory)))
    (find-file (cros-sdk-tramp--rotate-filename current))))


(provide 'cros-sdk-tramp)
