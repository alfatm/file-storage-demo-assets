# Missing assets

What the filedom demo set (the redesign reference, the admin Overview, the phone layout) still needs on top of
`demo/`. Until these arrive the seeder falls back: initials avatars, empty Audio / Presentations chips, one video.

Drop the files anywhere under `demo/` (suggested folders below); the dataset maps names onto them.

## Needed

| # | What | How many | Format | Size / shape | Suggested place | Used for |
|---|---|---|---|---|---|---|
| 1 | Portrait photos for avatars | 10–12 | jpg / png / webp | square, 256–512 px, one face, neutral background | `demo/People/` | Owner column, sharing panels, top-bar account, admin user list |
| 2 | Audio | 2–3 | mp3, m4a, wav or flac (mixed is better) | 10–60 s | `demo/Audio/` | the "Audio" type chip, audio icons and preview |
| 3 | Presentations | 2–3 | pptx (+ odp or key if available) | a few slides with real-looking content | `demo/Documents/` | the "Presentations" type chip |
| 4 | Short videos | 2–3 | mov, webm, mkv (different from the existing mp4) | 5–30 s, ≤ 20 MB each | `demo/Videos/` | Brand_Video / Launch_Video rows, video thumbnails |
| 5 | Invoices | 3–4 | pdf | one page each, fictional company | `demo/Documents/Invoices/` | the Invoices folder and tag |

## Nice to have

| # | What | How many | Format | Notes |
|---|---|---|---|---|
| 6 | A large design file | 1 | fig / psd | tens of MB, so sizes look like the reference (48 MB mockup) |
| 7 | Other design formats | 1–2 | sketch, ai | more design icons |
| 8 | A product shot | 1 | jpg | studio-style object photo (reference: Product_Photoshoot.jpg) |
| 9 | Marketing PDFs | 2 | pdf | a brief and a one-pager with a hero image (reference: Marketing_Brief.pdf) |

## Already covered by `demo/`

Brand guidelines (`Design/Brand Guidelines.pdf`), logo (`Design/logo.svg`), UI mockup (`UI Design.fig`),
one video (`demo.mp4`), docx/xlsx/odt/rtf/md documents, photos, archives, code, CSV/JSON/YAML/SQLite/vCard/iCal.

Licences: keep the same rule as the rest of the set — free to use (Unsplash/Pexels/CC0 or self-made), fictional
people and companies; note the source of each new file in `demo/README.md`.
