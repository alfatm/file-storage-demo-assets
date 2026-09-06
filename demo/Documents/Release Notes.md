# Release Notes

## 2.0.0 — 2026-07-24

### Added
- Share links with PIN, expiry date and download limits
- Access report for every shared file
- Content search for PDF, DOCX and Markdown documents
- WebDAV backend for existing NAS shares

### Changed
- Thumbnails are now generated at 128, 256 and 512 pixels
- API tokens expire after ninety days by default
- Two-factor authentication is enforced for administrators

### Fixed
- Uploads over 5 GB failed to resume after a network interruption
- Folder rename lost the modification date of nested files
- Search results ignored the selected folder filter

## 1.9.2 — 2026-06-19

### Fixed
- Preview of RTF documents rendered raw control words
- Grid view flickered when thumbnails finished loading out of order

## 1.9.1 — 2026-06-05

### Fixed
- Session cookies were not rotated after a password change
