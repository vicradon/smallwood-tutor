# Smallwood Practice Tutor

Wait-mode piano tutor for exercises from *Smallwood's Pianoforte Tutor*, driven by a USB-MIDI keyboard (tested with a Casio CT-S100).

- `index.html`: the tutor. Pick an exercise or load any MusicXML/.mxl file; the cursor advances only when the right note or chord is played. Arrow keys move between bars.
- `check.html`: MIDI link check that shows live keys and raw messages.
- `scores/`: transcribed exercises as compressed MusicXML.

Needs Chrome or Edge on desktop, or Chrome on Android (Web MIDI). Static site, no build step.

## Adding an exercise

Write a spec in `scores/src/` (format documented at the top of `tools/mkscore.py`), then:

```
python3 tools/mkscore.py scores/src/NAME.txt scores/NAME.mxl
```

and add it to `LIBRARY` in `index.html`.
