# Meeting Notes

- **Date:** 2026-07-07
- **Attendees:** Anna Kowalski, Marco Rossi, Elena Petrova, Tom Schmidt
- **Topic:** Sharing launch readiness

## Agenda

1. Share links with PIN and expiry
2. Content search index size
3. Security review follow-ups
4. Cyprus office hiring

## Discussion

Share links are feature complete. Anna demoed revocation and the access report.
Marco raised that the content search index for image-heavy workspaces is larger
than expected because EXIF text is being indexed; he will strip it.

Elena summarised the security review: enforce two-factor authentication for
administrators before launch, and expire API tokens after ninety days by default.

Tom shared the hiring plan for the Limassol office: two senior engineers in
September, then four more in Q4.

## Decisions

- Launch share links on 24 July behind a per-workspace flag.
- Two-factor enforcement for administrators ships in the same release.

## Action items

- [ ] Marco: strip EXIF text from the index (2026-07-10)
- [ ] Elena: write the 2FA enforcement migration (2026-07-14)
- [ ] Anna: update the project roadmap page (2026-07-08)
- [ ] Tom: post the Cyprus job descriptions (2026-07-15)
