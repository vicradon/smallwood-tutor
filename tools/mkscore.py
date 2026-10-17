"""Build a two-staff piano .mxl from a compact text spec.

Spec format (see scores/src/*.txt):
  title: Slow Air
  time: 3/4
  tempo: Andante
  # one line per bar: RH | LH
  E5/3@3 D5/1@2 C5/2@1 | C3/2@5 E3/2@3 G3/2@1
  !p                      <- dynamic marking for the next bar (p, pp, f, mf...)
  [                       <- start repeat before next bar
  ]                       <- end repeat after previous bar
  ---                     <- system break before next bar

Token: PITCH[+PITCH...]/DURATION[@FINGER[+FINGER...]]
  DURATION is in eighths: 1 eighth, 2 quarter, 3 dotted quarter, 4 half, 6 dotted half
  r/DURATION is a rest. Fingers list in the same order as pitches.

Usage: python tools/mkscore.py scores/src/slow-air.txt scores/slow-air.mxl
"""
import re, sys, zipfile

TYPES = {1: ("eighth", 0), 2: ("quarter", 0), 3: ("quarter", 1), 4: ("half", 0), 6: ("half", 1), 8: ("whole", 0)}


def parse(path):
    meta, bars, pending = {}, [], {}
    for raw in open(path, encoding="utf-8"):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^(\w+):\s*(.+)$", line)
        if m and "|" not in line and "/" not in m.group(2):
            meta[m.group(1)] = m.group(2).strip(); continue
        if m and m.group(1) == "time":
            meta["time"] = m.group(2).strip(); continue
        if line.startswith("!"):
            pending["dyn"] = line[1:]; continue
        if line == "[":
            pending["fwd"] = True; continue
        if line == "]":
            bars[-1]["back"] = True; continue
        if line == "---":
            pending["brk"] = True; continue
        rh, lh = [s.split() for s in line.split("|")]
        bars.append({"rh": rh, "lh": lh, **pending}); pending = {}
    return meta, bars


def token(t):
    m = re.match(r"^([^/]+)/(\d+)(?:@(.+))?$", t)
    if not m:
        raise ValueError(f"bad token {t!r}")
    pitches = [] if m.group(1) == "r" else m.group(1).split("+")
    fingers = m.group(3).split("+") if m.group(3) else []
    return pitches, int(m.group(2)), fingers


def pitch_xml(p):
    m = re.match(r"^([A-G])(#|b)?(\d)$", p)
    alter = {"#": 1, "b": -1}.get(m.group(2), 0)
    a = f"<alter>{alter}</alter>" if alter else ""
    return f"<pitch><step>{m.group(1)}</step>{a}<octave>{m.group(3)}</octave></pitch>"


def notes_xml(tokens, staff, voice, beat_len):
    out, pos = [], 0
    parsed = [token(t) for t in tokens]
    beams = [""] * len(parsed)
    # beam runs of eighths that sit inside one beat
    i = 0
    while i < len(parsed):
        if parsed[i][1] == 1:
            j, start = i, pos_of(parsed, i)
            while j + 1 < len(parsed) and parsed[j + 1][1] == 1 and pos_of(parsed, j + 1) // beat_len == start // beat_len:
                j += 1
            if j > i:
                beams[i] = "begin"; beams[j] = "end"
                for k in range(i + 1, j): beams[k] = "continue"
            i = j + 1
        else:
            i += 1
    for k, (pitches, dur, fingers) in enumerate(parsed):
        typ, dots = TYPES[dur]
        dot = "<dot/>" * dots
        if not pitches:
            out.append(f"<note><rest/><duration>{dur}</duration><voice>{voice}</voice><type>{typ}</type>{dot}<staff>{staff}</staff></note>")
            continue
        for n, p in enumerate(pitches):
            chord = "<chord/>" if n else ""
            beam = f'<beam number="1">{beams[k]}</beam>' if beams[k] and n == 0 else ""
            fing = ""
            if n < len(fingers):
                place = "above" if staff == 1 else "below"
                fing = f'<notations><technical><fingering placement="{place}">{fingers[n]}</fingering></technical></notations>'
            out.append(f"<note>{chord}{pitch_xml(p)}<duration>{dur}</duration><voice>{voice}</voice><type>{typ}</type>{dot}<staff>{staff}</staff>{beam}{fing}</note>")
        pos += dur
    return "".join(out), sum(t[1] for t in parsed)


def pos_of(parsed, i):
    return sum(t[1] for t in parsed[:i])


def build(meta, bars):
    beats, beat_type = map(int, meta.get("time", "4/4").split("/"))
    bar_len = beats * 8 // beat_type  # in eighths
    beat_len = 8 // beat_type
    xs = []
    for i, b in enumerate(bars, 1):
        x = [f'<measure number="{i}">']
        if b.get("brk"):
            x.append('<print new-system="yes"/>')
        if i == 1:
            x.append(f'<attributes><divisions>2</divisions><key><fifths>{meta.get("key", "0")}</fifths></key><time><beats>{beats}</beats><beat-type>{beat_type}</beat-type></time><staves>2</staves><clef number="1"><sign>G</sign><line>2</line></clef><clef number="2"><sign>F</sign><line>4</line></clef></attributes>')
            if "tempo" in meta:
                x.append(f'<direction placement="above"><direction-type><words font-weight="bold">{meta["tempo"]}</words></direction-type><staff>1</staff></direction>')
        if b.get("fwd"):
            x.append('<barline location="left"><bar-style>heavy-light</bar-style><repeat direction="forward"/></barline>')
        if b.get("dyn"):
            x.append(f'<direction placement="below"><direction-type><dynamics><{b["dyn"]}/></dynamics></direction-type><staff>1</staff></direction>')
        rh, rlen = notes_xml(b["rh"], 1, 1, beat_len)
        lh, llen = notes_xml(b["lh"], 2, 5, beat_len)
        # durations are in eighths but divisions=2 per quarter, so they already match
        if rlen != bar_len or llen != bar_len:
            raise ValueError(f"bar {i}: RH={rlen} LH={llen}, expected {bar_len} eighths")
        x.append(rh)
        x.append(f"<backup><duration>{bar_len}</duration></backup>")
        x.append(lh)
        if b.get("back"):
            x.append('<barline location="right"><bar-style>light-heavy</bar-style><repeat direction="backward"/></barline>')
        x.append("</measure>")
        xs.append("".join(x))
    composer = meta.get("composer", "William Smallwood")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<score-partwise version="4.0"><work><work-title>{meta.get("title", "Untitled")}</work-title></work>'
        f'<identification><creator type="composer">{composer}</creator></identification>'
        '<part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>'
        f'<part id="P1">{"".join(xs)}</part></score-partwise>'
    )


def write_mxl(xml, path):
    container = ('<?xml version="1.0" encoding="UTF-8"?><container><rootfiles>'
                 '<rootfile full-path="score.musicxml" media-type="application/vnd.recordare.musicxml+xml"/>'
                 '</rootfiles></container>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/vnd.recordare.musicxml", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("score.musicxml", xml)


if __name__ == "__main__":
    meta, bars = parse(sys.argv[1])
    write_mxl(build(meta, bars), sys.argv[2])
    print(f"{meta.get('title')}: {len(bars)} bars -> {sys.argv[2]}")
