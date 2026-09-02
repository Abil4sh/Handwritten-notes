<img width="1439" height="809" alt="Screenshot 2026-09-03 at 12 19 00 AM" src="https://github.com/user-attachments/assets/f583bdff-86b6-409b-b99e-7982c105578c" /># Handwritten Notes

Typed notes in, handwritten PDF out. Pick a layout, a hand, and paper — get a
page that reads as genuinely written rather than typeset.

![The editor, with live preview]


## Why it isn't just a handwriting font

Setting text in a handwriting font looks obviously fake: every `a` is identical,
every baseline is perfect, every line starts at exactly the same x. The renderer
here draws **glyph by glyph** and displaces each one:

- baseline drift, rotation, and size, each clamped at 2σ so no single character
  reads as a rendering fault
- one slope per line, applied cumulatively — real handwriting drifts across a
  line rather than vibrating around a perfect horizontal
- variation at the start of each line, because real left margins are not straight
- **cursive jitters per word, not per glyph**, since displacing connected
  letterforms individually snaps the joins

All of it is seeded deterministically from the note and line index, so the same
note renders byte-identically every time. That is what makes the render cache
correct: an identical request can safely return the stored PDF.

Output is vector, not raster — a 20-page note is a few hundred KB and stays
sharp at any zoom.

## Layout

- Greedy line breaking measured against real font metrics (`stringWidth`), not
  estimated — the six fonts vary by 21% in width at the same point size
- Widow and orphan control: a heading needs room for itself plus two lines of
  what follows, or it moves to the next page
- On ruled paper, leading snaps to the ruling pitch so every baseline lands on a
  line, and small gaps round away rather than drifting text off the rules
- Cornell layout places headings in a cue column *beside* their body text, which
  means the renderer cannot assume a single text column

## Configuration over code

Templates, papers, and handwriting styles are JSON files. The renderer contains
no template names — adding a layout is a new file, not a code change.

    grep -c "cornell" backend/app/render/page_renderer.py   # 0

## What works

- 4 layouts, 6 hands, 3 papers, adjustable size — 72 combinations
- Multi-colour highlighting that survives line wrapping
- Live preview as you type
- Accounts, saved notes, content-addressed render caching
- Live lecture capture with cue-phrase structuring ("first…", "be careful…",
  "now let's talk about…" become lists, callouts, and headings)

## What's next

- Uploaded audio files (needs Whisper; live capture uses the browser)
- Personal handwriting from uploaded samples — glyph extraction, then the same
  renderer protocol the font renderer already implements
- Direct editing on the page, which means either an overlay on the PDF or moving
  layout into the browser; the second costs the per-glyph jitter above
- Formulas beyond inline plain text

## Stack

FastAPI · ReportLab · Pydantic · Supabase (Postgres, Auth, Storage) · vanilla JS

The renderer is a pure function of (note, template, hand, paper) and knows
nothing about HTTP. `HandwritingRenderer` is a protocol with one implementation
today; the personal-handwriting renderer will implement the same two methods —
`measure` and `draw_run` — without the layout engine changing.

## Run it

    cd backend
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python scripts/fetch_fonts.py
    cp .env.example .env          # Supabase values; optional
    uvicorn app.main:app --reload

http://127.0.0.1:8000 — generating and downloading works without Supabase;
saving needs it.

## Syntax

    # Heading        ## Subheading       - bullet        1. numbered
    > quote          Term: meaning       Warning: ...    e.g. ...
    ---  divider     ==highlight==       ==g: ==b: ==p: ==o:  colours

## Fonts

Caveat, Patrick Hand, Kalam, Shadows Into Light, Dancing Script and Indie
Flower, from the official Google Fonts repository under the SIL Open Font
License. Licences ship in `backend/app/handwriting/fonts/licenses/`.
