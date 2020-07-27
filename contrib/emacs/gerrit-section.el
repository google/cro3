;; -*- lexical-binding: t -*-

;; copyright 2020 the chromium os authors. all rights reserved.
;; use of this source code is governed by a bsd-style license that can be
;; found in the license file.

(require 'magit)
(require 'magit-section)
(require 'repo-gerrit)

(defface gerrit-patch
  `((t :inherit magit-section-heading))
  "patch")


(defface gerrit-filepath
  `((t :inherit magit-branch-remote))
  "filepath")


(defconst gerrit-buffer-name "gerrit-comments"
  "The name of the buffer where the gerrit summary is placed.")


(defconst gerrit-section-mode-map magit-section-mode-map
  "Mode map for Gerrit Summary - copies standard magit map")


(defconst gerrit-section-type (gensym)
  "Magit Sections need a symbol for a section type.
We don't currently use this functionality.")


(define-derived-mode gerrit-section-mode magit-section-mode
  "Gerrit-Repo"
  "Mode for displaying Gerrit comments within Emacs."
  (when (fboundp 'evil-set-initial-state)
    ;; Evil Mode doesn't always play nice with the keymaps.
    (evil-set-initial-state 'gerrit-section-mode 'emacs)))



(defun gerrit-refresh ()
  "Refreshes Gerrit data from hosts."
  (interactive)
  (setf gerrit--refreshed t)
  (gerrit-init)
  (when (get-buffer gerrit-buffer-name)
    (save-excursion
      (switch-to-buffer gerrit-buffer-name)
      (setf inhibit-read-only t)
      (erase-buffer)
      (setf inhibit-read-only t)))
  (gerrit-comments t))


(defun gerrit-comments (&optional refresh)
  "Display buffer that shows comments for recent open changes.
This comment is idempotent."
  (interactive)
  (when (or (not (get-buffer gerrit-buffer-name))
            refresh)
    (save-excursion
      (set-buffer (get-buffer-create gerrit-buffer-name))
      (magit-insert-section (root)
        (magit-insert-heading "Gerrit Comments\n\n")
        (loop for change in
              (hash-table-keys gerrit--change-to-filepath-comments) do
              (unless (hash-table-empty-p
                       (gethash change gerrit--change-to-filepath-comments))
                (magit-insert-section (file)
                  (magit-insert-heading
                    (format "%s - %s"
                            (gethash "subject" change)
                            (gethash "change_id" change)))

                  (loop for filepath in
                        (hash-table-keys
                         (gethash
                          change
                          gerrit--change-to-filepath-comments))
                        do
                        (gerrit--insert-section-comments change
                                                         filepath))))))

      (when (hash-table-empty-p gerrit--change-to-filepath-comments)
        (insert "No open changes!"))

      (goto-char (point-min))
      (gerrit-section-mode)
      (setf word-wrap t)
      (setf truncate-lines nil)))

  (if refresh
      (switch-to-buffer gerrit-buffer-name)
    (pop-to-buffer gerrit-buffer-name)))


(define-button-type 'gerrit--filepath
  'face 'gerrit-filepath)

(defun gerrit--navigate-to-comment (project-branch-pair
                                    line
                                    filepath-from-project-root
                                    section-symbol)
  "Navigates the user to a comment."

  ;; Keep section open for user's to refer back to during edits.
  (when (oref section-symbol hidden)
    (magit-section-toggle section-symbol))

  (switch-to-buffer-other-window
   (find-file-noselect (gerrit--get-abs-path-to-file
                        filepath-from-project-root
                        project-branch-pair
                        test-repo-root)))

  (goto-char (point-min))
  (beginning-of-line line))


(defun gerrit--insert-comment-header (change
                                      filepath-from-project-root
                                      line
                                      section-symbol)
  "Inserts comments for the given change and system filepath."
  (let (header-text
        button-p
        (begin-pos (point)))
    (cond ((equal "/PATCHSET_LEVEL" filepath-from-project-root)
           (setf header-text
                 (propertize
                  "Patch Comment"
                  'face 'gerrit-filepath)))
          ((equal "/COMMIT_MSG" filepath-from-project-root)
           ;; TODO future CL for navigating
           ;; to commit message lines.
           (setf header-text
                 (propertize
                  (format "Commit Message:%s\n"
                          filepath-from-project-root
                          line)
                  'face 'gerrit-filepath)))
          ((equal "MERGE_LIST" filepath-from-project-root)
           (message "There are merge list comments which we don't support"))
          ;; Default here are filepath comments
          (t (progn
               (setf header-text
                     (propertize
                      (format "%s:%s\n"
                              filepath-from-project-root
                              line)
                      'face 'gerrit-filepath))
               (setf button-p t))))

    (magit-insert-heading header-text)
    (when button-p
      (make-button begin-pos
                   (point)
                   'type 'gerrit--filepath
                   'action
                   (lambda (button)
                     (gerrit--navigate-to-comment
                      change
                      line
                      filepath-from-project-root
                      section-symbol))))))


(defun gerrit--insert-section-comments (change
                                        filepath-from-project-root)
  ;; We want the smaller lines first.
  (sort (gethash filepath-from-project-root
                 (gethash change gerrit--change-to-filepath-comments))
        (lambda (a b)
          ;; If comment has no line, we don't care about ordering.
          (< (or (gethash "line" a) 0)
             (or (gethash "line" b) 0))))

  (loop for comment-info across
        (gethash filepath-from-project-root
                 (gethash change gerrit--change-to-filepath-comments))
        do
        ;; We don't care about our own comments.
        (unless (equal
                 test-user ;; FIXME when test code is removed
                 (gethash "email" (gethash "author" comment-info)))
          (let ((section-symbol (gensym))
                (line (gethash "line" comment-info))
                (begin-pos (point)))

            (magit-insert-section
              ;; We use section symbols to toggle when navigating.
              section-symbol
              (gerrit-section-type nil t)

              (gerrit--insert-comment-header
               change
               filepath-from-project-root
               line
               section-symbol)
              (gerrit--section-insert-comment comment-info))))))


(defun gerrit--section-insert-comment (comment-info)
  "Inserts the author, email, and body of a comment."
  (magit-insert-section-body
    (insert (format "Author: %s\nEmail: %s\nComment: %s\n"
                    (gethash "name" (gethash "author" comment-info))
                    (gethash "email" (gethash "author" comment-info))
                    (gethash "message" comment-info)))))
