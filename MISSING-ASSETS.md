# Missing assets

All items from the original list are now in `demo/`, generated or fetched by `scripts/build_demo_files.py`
(`build_extras()`). Sources are listed in `demo/README.md`.

| # | What | Files |
|---|---|---|
| 1 | Portrait photos for avatars | `People/*.jpg / .png / .webp`: 12 people, 512×512, named after fictional team members (`anna-kowalski.jpg`, …) |
| 2 | Audio | `Audio/Podcast Intro.mp3`, `Brand Jingle.m4a`, `Ambient Loop.flac`, `UI Sounds.wav` (11–44 s, tagged, cover art) |
| 3 | Presentations | `Documents/Q3 Product Review.pptx`, `Documents/Sales Kickoff 2026.pptx`, `Documents/Company All-Hands.odp` |
| 4 | Short videos | `Videos/Brand Video.mov` (H.264/AAC), `Launch Video.webm` (VP9/Opus), `Office Tour.mkv` (H.264/Opus); 12–20 s, ~2.5 MB each |
| 5 | Invoices | `Documents/Invoices/Invoice INV-2026-0151.pdf`, `INV-2026-0158`, `NWL-20417`, `OS-2026-088` |
| 6 | Large design file | `Design/Website Mockup.psd`: 3840×2400, 5 named layers, ~51 MB |
| 7 | Other design formats | `Design/Mobile App.sketch`, `Design/Logo Concepts.ai` |
| 8 | Product shot | `Design/Product Photoshoot.jpg` |
| 9 | Marketing PDFs | `Documents/Marketing Brief.pdf` (2 pages, hero photo), `Documents/Product One-Pager.pdf` |

Still open: a Keynote `.key` deck (no way to generate a faithful one; optional in the original list).

Note: the committed `demo/` has hand edits the script does not reproduce (e.g. `Code/`, `Design/animation.gif`), so
build into a scratch directory (`python3 scripts/build_demo_files.py /tmp/out`) and copy over only what you need.
