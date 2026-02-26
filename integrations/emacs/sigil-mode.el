;;; sigil-mode.el --- Display and manage sigil code bookmarks -*- lexical-binding: t; -*-

;; Author: BjornRoberg
;; Version: 0.1.0
;; Package-Requires: ((emacs "27.1"))
;; Keywords: tools, convenience
;; URL: https://github.com/roobie/sigil

;;; Commentary:

;; Minor mode for displaying sigil bookmarks in the fringe gutter.
;; Reads .sigil/bookmarks.jsonl and context files from the repository root,
;; places fringe indicators on bookmarked lines, and provides keybindings
;; for creating, navigating, and managing bookmarks.
;;
;; Usage:
;;   (require 'sigil-mode)
;;   (global-sigil-mode 1)       ; auto-enable in all file buffers
;;
;; Or enable per-buffer:
;;   M-x sigil-mode
;;
;; Keybindings (default prefix C-c s):
;;   C-c s a   Add bookmark at point
;;   C-c s d   Delete bookmark at point
;;   C-c s l   List all bookmarks
;;   C-c s n   Jump to next bookmark in buffer
;;   C-c s p   Jump to previous bookmark in buffer
;;   C-c s v   Validate all bookmarks
;;   C-c s r   Refresh display

;;; Code:

(require 'json)
(require 'cl-lib)

;; --- Customization ---

(defgroup sigil nil
  "Sigil code bookmarks."
  :group 'tools
  :prefix "sigil-")

(defcustom sigil-command "sg"
  "Command to invoke the sigil CLI."
  :type 'string
  :group 'sigil)

(defcustom sigil-fringe-bitmap 'filled-rectangle
  "Fringe bitmap used to indicate bookmarks.
Some good options: `filled-rectangle', `large-circle', `right-arrow'."
  :type 'symbol
  :group 'sigil)

(defcustom sigil-fringe-face 'sigil-fringe-mark
  "Face used for fringe bookmark indicators."
  :type 'face
  :group 'sigil)

;; --- Faces ---

(defface sigil-fringe-mark
  '((((class color) (background dark))
     :foreground "#e5c07b")
    (((class color) (background light))
     :foreground "#986801")
    (t :foreground "yellow"))
  "Face for sigil fringe indicators."
  :group 'sigil)

(defface sigil-stale-mark
  '((((class color) (background dark))
     :foreground "#e06c75")
    (((class color) (background light))
     :foreground "#e45649")
    (t :foreground "red"))
  "Face for stale sigil fringe indicators."
  :group 'sigil)

;; --- Internal state ---

(defvar-local sigil--overlays nil
  "List of overlays for sigil bookmarks in this buffer.")

(defvar-local sigil--bookmarks nil
  "Parsed bookmarks relevant to this buffer.")

(defvar sigil--all-bookmarks nil
  "All parsed bookmarks from the current project.")

;; --- Project root detection ---

(defun sigil--find-root (&optional dir)
  "Find the project root containing .sigil/ or .git/ starting from DIR."
  (let ((start (or dir default-directory)))
    (or (locate-dominating-file start ".sigil")
        (locate-dominating-file start ".git"))))

;; --- JSONL parsing ---

(defun sigil--parse-jsonl (file)
  "Parse a JSONL file into a list of alists."
  (when (file-exists-p file)
    (let ((lines (split-string (with-temp-buffer
                                 (insert-file-contents file)
                                 (buffer-string))
                               "\n" t "[ \t]+")))
      (mapcar (lambda (line)
                (json-parse-string line :object-type 'alist))
              lines))))

(defun sigil--relative-path (file-path root)
  "Get FILE-PATH relative to ROOT."
  (file-relative-name (expand-file-name file-path) (expand-file-name root)))

;; --- Loading bookmarks ---

(defun sigil--load-bookmarks ()
  "Load all bookmarks from the project's .sigil/bookmarks.jsonl."
  (let ((root (sigil--find-root)))
    (when root
      (let ((jsonl-path (expand-file-name ".sigil/bookmarks.jsonl" root)))
        (setq sigil--all-bookmarks
              (or (sigil--parse-jsonl jsonl-path) '()))))))

(defun sigil--buffer-bookmarks ()
  "Return bookmarks matching the current buffer's file."
  (let ((root (sigil--find-root)))
    (when (and root buffer-file-name)
      (let ((rel-path (sigil--relative-path buffer-file-name root)))
        (cl-remove-if-not
         (lambda (bm)
           (string= (alist-get 'file bm) rel-path))
         sigil--all-bookmarks)))))

;; --- Overlay management ---

(defun sigil--clear-overlays ()
  "Remove all sigil overlays from the current buffer."
  (mapc #'delete-overlay sigil--overlays)
  (setq sigil--overlays nil))

(defun sigil--place-overlays ()
  "Place fringe overlays for all bookmarks in the current buffer."
  (sigil--clear-overlays)
  (let ((bookmarks (sigil--buffer-bookmarks)))
    (setq sigil--bookmarks bookmarks)
    (dolist (bm bookmarks)
      (let* ((line (alist-get 'line bm))
             (status (alist-get 'status bm))
             (desc (or (alist-get 'desc bm) ""))
             (tags (alist-get 'tags bm))
             (tag-str (if (and tags (> (length tags) 0))
                         (mapconcat #'identity (append tags nil) ", ")
                       ""))
             (face (if (member status '("stale" "missing_file"))
                       'sigil-stale-mark
                     sigil-fringe-face))
             (tooltip (format "[sigil] %s%s"
                              desc
                              (if (string-empty-p tag-str) ""
                                (format " [%s]" tag-str)))))
        (when (and (integerp line) (<= line (count-lines (point-min) (point-max))))
          (save-excursion
            (goto-char (point-min))
            (forward-line (1- line))
            (let ((ov (make-overlay (line-beginning-position) (line-end-position))))
              (overlay-put ov 'before-string
                           (propertize " " 'display
                                       `(left-fringe ,sigil-fringe-bitmap ,face)))
              (overlay-put ov 'help-echo tooltip)
              (overlay-put ov 'sigil-bookmark bm)
              (overlay-put ov 'priority 100)
              (push ov sigil--overlays))))))))

;; --- Refresh ---

(defun sigil-refresh ()
  "Reload bookmarks and refresh the fringe display."
  (interactive)
  (sigil--load-bookmarks)
  (sigil--place-overlays)
  (message "Sigil: refreshed %d bookmark(s) in buffer"
           (length sigil--bookmarks)))

;; --- Navigation ---

(defun sigil-next-bookmark ()
  "Jump to the next bookmarked line in the current buffer."
  (interactive)
  (let* ((cur-line (line-number-at-pos))
         (lines (sort (mapcar (lambda (bm) (alist-get 'line bm))
                              sigil--bookmarks)
                      #'<))
         (next (cl-find-if (lambda (l) (> l cur-line)) lines)))
    (if next
        (progn (goto-char (point-min))
               (forward-line (1- next))
               (sigil--echo-bookmark-at-point))
      (message "Sigil: no more bookmarks below"))))

(defun sigil-prev-bookmark ()
  "Jump to the previous bookmarked line in the current buffer."
  (interactive)
  (let* ((cur-line (line-number-at-pos))
         (lines (sort (mapcar (lambda (bm) (alist-get 'line bm))
                              sigil--bookmarks)
                      #'>))
         (prev (cl-find-if (lambda (l) (< l cur-line)) lines)))
    (if prev
        (progn (goto-char (point-min))
               (forward-line (1- prev))
               (sigil--echo-bookmark-at-point))
      (message "Sigil: no more bookmarks above"))))

(defun sigil--echo-bookmark-at-point ()
  "Display the bookmark description for the current line in the echo area."
  (let* ((line (line-number-at-pos))
         (bm (cl-find-if (lambda (b) (= (alist-get 'line b) line))
                          sigil--bookmarks)))
    (when bm
      (message "Sigil [%s]: %s"
               (let ((tags (alist-get 'tags bm)))
                 (if (and tags (> (length tags) 0))
                     (mapconcat #'identity (append tags nil) ",")
                   "-"))
               (or (alist-get 'desc bm) "")))))

;; --- Commands (shell out to sg) ---

(defun sigil--run (&rest args)
  "Run sigil CLI with ARGS, return stdout as string."
  (let ((root (sigil--find-root)))
    (when root
      (let ((default-directory root))
        (with-temp-buffer
          (apply #'call-process sigil-command nil t nil args)
          (buffer-string))))))

(defun sigil-add-bookmark ()
  "Add a sigil bookmark at the current line."
  (interactive)
  (unless buffer-file-name
    (user-error "Buffer is not visiting a file"))
  (let* ((root (sigil--find-root))
         (rel-path (sigil--relative-path buffer-file-name root))
         (line (line-number-at-pos))
         (location (format "%s:%d" rel-path line))
         (tags (read-string "Tags (comma-separated): "))
         (desc (read-string "Description: "))
         (args (list "add" location)))
    (unless (string-empty-p tags)
      (setq args (append args (list "-t" tags))))
    (unless (string-empty-p desc)
      (setq args (append args (list "-d" desc))))
    (let ((output (apply #'sigil--run args)))
      (message "%s" (string-trim output)))
    (sigil-refresh)))

(defun sigil-delete-bookmark ()
  "Delete the sigil bookmark at the current line."
  (interactive)
  (let* ((line (line-number-at-pos))
         (bm (cl-find-if (lambda (b) (= (alist-get 'line b) line))
                          sigil--bookmarks)))
    (if bm
        (when (y-or-n-p (format "Delete bookmark '%s'? " (alist-get 'desc bm)))
          (sigil--run "delete" (alist-get 'id bm))
          (sigil-refresh))
      (message "Sigil: no bookmark on this line"))))

(defun sigil-validate ()
  "Run sigil validate --fix and show results."
  (interactive)
  (let ((output (sigil--run "validate" "--fix")))
    (message "%s" (string-trim output))
    (sigil-refresh)))

;; --- Bookmark list buffer ---

(defun sigil-list-bookmarks ()
  "Open a buffer listing all sigil bookmarks in the project."
  (interactive)
  (sigil--load-bookmarks)
  (let ((buf (get-buffer-create "*Sigil*")))
    (with-current-buffer buf
      (sigil-list-mode)
      (sigil-list--refresh))
    (pop-to-buffer buf)))

(defvar sigil-list-mode-map
  (let ((map (make-sparse-keymap)))
    (define-key map (kbd "RET") #'sigil-list-goto)
    (define-key map (kbd "d")   #'sigil-list-delete)
    (define-key map (kbd "v")   #'sigil-list-validate)
    (define-key map (kbd "g")   #'sigil-list--refresh)
    (define-key map (kbd "q")   #'quit-window)
    map)
  "Keymap for `sigil-list-mode'.")

(define-derived-mode sigil-list-mode tabulated-list-mode "Sigil"
  "Major mode for browsing sigil bookmarks."
  (setq tabulated-list-format
        [("ID"     8  t)
         ("File"   30 t)
         ("Line"   5  t :right-align t)
         ("Tags"   20 t)
         ("Description" 40 t)
         ("Status" 8  t)])
  (setq tabulated-list-sort-key '("File" . nil))
  (tabulated-list-init-header))

(defun sigil-list--refresh ()
  "Refresh the bookmark list buffer."
  (interactive)
  (sigil--load-bookmarks)
  (let ((entries
         (mapcar
          (lambda (bm)
            (let ((id (alist-get 'id bm))
                  (tags (alist-get 'tags bm)))
              (list id
                    (vector
                     (substring id (max 0 (- (length id) 8)))
                     (alist-get 'file bm)
                     (number-to-string (alist-get 'line bm))
                     (if (and tags (> (length tags) 0))
                         (mapconcat #'identity (append tags nil) ",")
                       "")
                     (or (alist-get 'desc bm) "")
                     (or (alist-get 'status bm) "?")))))
          sigil--all-bookmarks)))
    (setq tabulated-list-entries entries)
    (tabulated-list-print t)))

(defun sigil-list-goto ()
  "Open the file at the bookmarked line."
  (interactive)
  (let* ((id (tabulated-list-get-id))
         (bm (cl-find-if (lambda (b) (string= (alist-get 'id b) id))
                          sigil--all-bookmarks)))
    (when bm
      (let* ((root (sigil--find-root))
             (file (expand-file-name (alist-get 'file bm) root))
             (line (alist-get 'line bm)))
        (find-file file)
        (goto-char (point-min))
        (forward-line (1- line))))))

(defun sigil-list-delete ()
  "Delete the bookmark at point in the list buffer."
  (interactive)
  (let* ((id (tabulated-list-get-id))
         (bm (cl-find-if (lambda (b) (string= (alist-get 'id b) id))
                          sigil--all-bookmarks)))
    (when (and bm (y-or-n-p (format "Delete '%s'? " (alist-get 'desc bm))))
      (sigil--run "delete" id)
      (sigil-list--refresh))))

(defun sigil-list-validate ()
  "Run validation from the list buffer."
  (interactive)
  (let ((output (sigil--run "validate" "--fix")))
    (message "%s" (string-trim output))
    (sigil-list--refresh)))

;; --- Minor mode ---

(defvar sigil-mode-map
  (let ((map (make-sparse-keymap)))
    (define-key map (kbd "C-c s a") #'sigil-add-bookmark)
    (define-key map (kbd "C-c s d") #'sigil-delete-bookmark)
    (define-key map (kbd "C-c s l") #'sigil-list-bookmarks)
    (define-key map (kbd "C-c s n") #'sigil-next-bookmark)
    (define-key map (kbd "C-c s p") #'sigil-prev-bookmark)
    (define-key map (kbd "C-c s v") #'sigil-validate)
    (define-key map (kbd "C-c s r") #'sigil-refresh)
    map)
  "Keymap for `sigil-mode'.")

;;;###autoload
(define-minor-mode sigil-mode
  "Minor mode for displaying sigil code bookmarks in the fringe."
  :lighter " Sigil"
  :keymap sigil-mode-map
  (if sigil-mode
      (progn
        (sigil--load-bookmarks)
        (sigil--place-overlays)
        (add-hook 'after-save-hook #'sigil-refresh nil t))
    (sigil--clear-overlays)
    (remove-hook 'after-save-hook #'sigil-refresh t)))

(defun sigil--maybe-enable ()
  "Enable `sigil-mode' if the buffer's file is inside a sigil project."
  (when (and buffer-file-name (sigil--find-root))
    (sigil-mode 1)))

;;;###autoload
(define-globalized-minor-mode global-sigil-mode sigil-mode sigil--maybe-enable
  :group 'sigil)

(provide 'sigil-mode)

;;; sigil-mode.el ends here
