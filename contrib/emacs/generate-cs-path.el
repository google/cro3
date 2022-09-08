;; generate-cs-path.el -- Generate codesearch URLs.

;; Copyright 2022 The ChromiumOS Authors
;; Use of this source code is governed by a BSD-style license that can be
;; found in the LICENSE file.

(defcustom cros-generate-cs-bin
  (concat
   (file-name-as-directory
    (locate-dominating-file load-file-name "src/platform/dev/contrib/OWNERS"))
   "chromite/contrib/generate_cs_path")
  "Path to executable to call to generate codesearch URLs"
  :group 'tools
  :type '(file :must-match t))

(defun cros-generate-cs-path()
  "Show the URL of the codesearch in message buffer and also add
to clipboard."
  (interactive)
  (let* ((filename (buffer-file-name (current-buffer)))
         (output
          (shell-command-to-string
           (format "%s %s -l %d --show" cros-generate-cs-bin filename
                   (line-number-at-pos)))))
    (message output)
    (kill-new output)))
