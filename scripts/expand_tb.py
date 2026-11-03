"""Strict hierarchical expander for the generated tb schematics.

xschem's own batch netlister needs an X server, so this minimal expander
covers exactly the constructs gen_tb_sch.py emits (vsource/gnd/code/
code_shown/opin/ipin + hierarchical X instances, all rot0/flip0; graphic
B rects and the launcher symbol are netlist-ignored) and FAILS LOUDLY on
anything else. Its real job is the correspondence check every hierarchical
flow depends on: symbol pin order == subcircuit port order == parent nets.

Records may span lines (native xschem: literal newlines inside {...}, e.g.
the .control code_shown block and the graph rect), so parsing accumulates
to brace balance instead of assuming one line per record.

Usage: python3 scripts/expand_tb.py <top.sch> <out.spice>
Then: ngspice -b <out.spice>; the vout/vfilt traces must reproduce the
proven flat-deck replay (see scripts/check_tb_replay.py).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XSDIR = ROOT / "design" / "analog" / "xschem"

# device pin offsets (local coords, rot0): name -> [(pin, dx, dy)]
DEV_PINS = {
    "devices/vsource.sym": [("p", 0, -30), ("m", 0, 30)],
    "devices/gnd.sym": [("p", 0, 0)],
    "devices/code.sym": [],
    "devices/code_shown.sym": [],
    "devices/ipin.sym": [("p", 0, 0)],
    "devices/opin.sym": [("p", 0, 0)],
    "devices/lab_pin.sym": [("p", 0, 0)],
}

_lines = []
_autonet = [0]


def emit(s):
    _lines.append(s)


def autonet():
    _autonet[0] += 1
    return f"n{_autonet[0]}"


class Union:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def join_all(uf, endpoints, segments):
    """Union endpoints by coincidence AND T-junction (Manhattan only)."""
    for (x1, y1, o1) in endpoints:
        for (x2, y2, o2) in endpoints:
            if x1 == x2 and y1 == y2:
                uf.union(repr(o1), repr(o2))
    for (x, y, o) in endpoints:
        for (ax, ay, bx, by, w) in segments:
            assert ax == bx or ay == by, f"diagonal wire ({ax},{ay})-({bx},{by})"
            on = (x == ax == bx and min(ay, by) <= y <= max(ay, by)) or \
                 (y == ay == by and min(ax, bx) <= x <= max(ax, bx))
            if on:
                uf.union(repr(o), repr(("wire", w)))


def records(path):
    """Logical records: accumulate physical lines until braces balance.

    xschem stores literal newlines inside {...} (multiline code blocks,
    graph rects, launcher tclcommands), so a record is lines-up-to-balance.
    """
    rec, depth = [], 0
    for raw in open(path):
        line = raw.rstrip("\n")
        rec.append(line)
        depth += line.count("{") - line.count("}")
        assert depth >= 0, f"unbalanced braces in {path}: {line}"
        if depth == 0 and rec != [""]:
            yield "\n".join(rec)
            rec = []
    assert not rec, f"dangling record in {path}"


def parse_sch(path):
    """Return (instances, wires): inst=(sym,x,y,attrs), wire=(x1,y1,x2,y2,lab)."""
    inst, wires = [], []
    for rec in records(path):
        m = re.match(r"C \{(.*?)\} (\S+) (\S+) (\d) (\d) \{(.*)\}$",
                     rec, re.DOTALL)
        if m:
            assert (m.group(4), m.group(5)) == ("0", "0"), f"rot/flip in {path}"
            inst.append((m.group(1), float(m.group(2)), float(m.group(3)),
                         m.group(6)))
            continue
        m = re.match(r"N (\S+) (\S+) (\S+) (\S+) \{(.*)\}$", rec, re.DOTALL)
        if m:
            lab = m.group(5).replace("\n", "")
            if lab.startswith("lab="):
                lab = lab[4:]
            wires.append((float(m.group(1)), float(m.group(2)),
                          float(m.group(3)), float(m.group(4)),
                          lab or None))
            continue
    return inst, wires


def sym_pins(sym_path):
    """Pin labs in .sym file order with local coords."""
    pins = []
    for line in open(sym_path):
        m = re.match(r"B \d+ (\S+) (\S+) (\S+) (\S+) \{name=([^ }]+)", line)
        if m:
            x1, y1, x2, y2 = (float(m.group(i)) for i in range(1, 5))
            pins.append((m.group(5), (x1 + x2) / 2, (y1 + y2) / 2))
    return pins


def attr(attrs, key):
    m = re.search(key + r'="(.*)"', attrs, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(key + r"=(\S+)", attrs)
    return m.group(1) if m else None


LEAF = {"r2r_dac8_pdk.sym"}  # DUT: model comes from dac_subckt.spice


def expand(top_sch):
    """Flatten hierarchy; return (subckt_defs, top_lines)."""
    inst, wires = parse_sch(top_sch)
    uf = Union()
    endpoints = []  # (x, y, owner) owner=(kind, payload)

    defBasics = None
    for sym, x, y, attrs in inst:
        if sym == "devices/launcher.sym":
            continue  # GUI-only load button; not part of the netlist
        if sym in DEV_PINS:
            for pin, dx, dy in DEV_PINS[sym]:
                endpoints.append((x + dx, y + dy, ("dev", sym, attrs, pin)))
                if sym == "devices/gnd.sym":
                    uf.union(repr(endpoints[-1][2]), "net:0")
        elif sym in LEAF:
            for lab, dx, dy in sym_pins(XSDIR / sym):
                endpoints.append((x + dx, y + dy, ("hier", sym, attrs, lab)))
        elif sym.endswith(".sym"):
            sub = (XSDIR / sym).with_suffix(".sch")
            assert sub.exists(), f"missing sub-schematic {sub}"
            for lab, dx, dy in sym_pins(XSDIR / sym):
                endpoints.append((x + dx, y + dy, ("hier", sym, attrs, lab)))
        else:
            raise AssertionError(f"unsupported symbol {sym}")

    for x1, y1, x2, y2, lab in wires:
        w = autonet()
        endpoints.append((x1, y1, ("wire", w)))
        endpoints.append((x2, y2, ("wire", w)))
        if lab:
            if lab.startswith("lab="):
                lab = lab[4:]
            uf.union(repr(("wire", w)), f"net:{lab}")

    for (x1, y1, o1) in endpoints:
        for (x2, y2, o2) in endpoints:
            if x1 == x2 and y1 == y2:
                uf.union(repr(o1), repr(o2))

    # one label per net: two different labs unioned = a short.
    # net:0 (ground) is exempt: rails labeled vgnd/gnd intentionally merge
    # into it (the batch deck ties XDAC vgnd straight to 0).
    seen = {}
    for k in uf.p:
        if k.startswith("net:") and k != "net:0":
            r = uf.find(k)
            assert r not in seen, f"SHORT: {seen[r]} meets {k[4:]}"
            seen[r] = k[4:]

    # resolve each owner to its net
    auto = set()

    def anon():
        n = autonet()
        auto.add(n)
        return n

    def resolve(r):
        names = [k[4:] for k in uf.p if uf.find(k) == r and k.startswith("net:")]
        # ground canonicalizes to 0: same-root nets must emit ONE name or
        # SPICE sees two disconnected nets (proved by the vgnd rail).
        if "0" in names:
            return "0"
        return names[0] if names else anon()

    owner_net = {}
    for x, y, o in endpoints:
        owner_net[repr(o)] = resolve(uf.find(repr(o)))

    # a top-level pin on an auto net is an OPEN schematic (proved by the
    # vref/vpwr/vgnd float: 30-off rows netlisted clean and simmed garbage)
    for x, y, o in endpoints:
        if o[0] in ("hier", "dev") and owner_net[repr(o)] in auto:
            raise AssertionError(f"OPEN: {o} floats on {owner_net[repr(o)]}")

    top_lines = []
    sub_defs = {}
    for sym, x, y, attrs in inst:
        if sym == "devices/launcher.sym":
            continue  # GUI-only: spice_ignore=true nets nothing (verified)
        if sym in ("devices/code.sym", "devices/code_shown.sym"):
            v = attr(attrs, "value")
            assert v is not None, f"{sym} without value"
            top_lines.append(f"** code {attr(attrs, 'name')}: {v}")
            top_lines.append(v)
        elif sym == "devices/vsource.sym":
            name = attr(attrs, "name")
            nets = [owner_net[repr(("dev", sym, attrs, p))]
                    for p, _, _ in DEV_PINS[sym]]
            top_lines.append(f"{name} {nets[0]} {nets[1]} {attr(attrs, 'value')}")
        elif sym == "devices/gnd.sym":
            pass  # goto=0 handled: net named 0 below
        elif sym in LEAF or sym.endswith(".sym"):
            name = attr(attrs, "name")
            pins = sym_pins(XSDIR / sym)
            model = sym[:-len(".sym")]
            if sym not in LEAF:
                sub = (XSDIR / sym).with_suffix(".sch")
                if sym not in sub_defs:
                    sub_defs[sym] = emit_subckt(sym, sub)
            nets = [owner_net[repr(("hier", sym, attrs, lab))]
                    for lab, _, _ in pins]
            top_lines.append(f"{name} {' '.join(nets)} {model}")
        else:
            raise AssertionError(f"unsupported {sym}")
    return sub_defs, top_lines


def emit_subckt(sym, sub_sch):
    """Netlist one sub-schematic as .subckt; ports in opin/ipin file order."""
    inst, wires = parse_sch(sub_sch)
    ports = []
    for s, x, y, attrs in inst:
        if s in ("devices/ipin.sym", "devices/opin.sym"):
            m = re.search(r"lab=([^ }]+)", attrs)
            ports.append(m.group(1))
    pins = sym_pins(XSDIR / sym)
    assert [lab for lab, _, _ in pins] == ports, \
        f"pin-order mismatch: sym {[l for l, _, _ in pins]} vs sch {ports}"
    print(f"correspondence OK: {sym} ({len(ports)} pins)")
    uf = Union()
    endpoints = []
    devs = []
    for s, x, y, attrs in inst:
        if s in DEV_PINS and s not in ("devices/ipin.sym", "devices/opin.sym",
                                       "devices/lab_pin.sym", "devices/code.sym"):
            for pin, dx, dy in DEV_PINS[s]:
                endpoints.append((x + dx, y + dy, ("dev", s, attrs, pin)))
                if s == "devices/gnd.sym":
                    uf.union(repr(endpoints[-1][2]), "net:0")
        elif s in ("devices/ipin.sym", "devices/opin.sym", "devices/lab_pin.sym"):
            m = re.search(r"lab=([^ }]+)", attrs)
            endpoints.append((x, y, ("port", m.group(1))))
        elif s == "devices/code.sym":
            pass
        else:
            raise AssertionError(f"unsupported {s} in {sub_sch}")
    for x1, y1, x2, y2, lab in wires:
        w = autonet()
        endpoints.append((x1, y1, ("wire", w)))
        endpoints.append((x2, y2, ("wire", w)))
        if lab:
            if lab.startswith("lab="):
                lab = lab[4:]
            uf.union(repr(("wire", w)), f"net:{lab}")
    for (x1, y1, o1) in endpoints:
        for (x2, y2, o2) in endpoints:
            if x1 == x2 and y1 == y2:
                uf.union(repr(o1), repr(o2))
    owner_net = {}
    for x, y, o in endpoints:
        r = uf.find(repr(o))
        names = [k[4:] for k in uf.p if uf.find(k) == r and k.startswith("net:")]
        owner_net[repr(o)] = "0" if "0" in names else \
            (names[0] if names else autonet())
    # ports must touch a wire: a forced lab name would mask an open
    for x, y, o in endpoints:
        if o[0] == "port":
            net = owner_net[repr(o)]
            assert net == o[1], \
                f"port {o[1]} floats (touches net {net})"
    model = sym[:-len(".sym")]
    out = [f".subckt {model} {' '.join(ports)}"]
    for s, x, y, attrs in inst:
        if s == "devices/vsource.sym":
            name = attr(attrs, "name")
            nets = [owner_net[repr(("dev", s, attrs, p))]
                    for p, _, _ in DEV_PINS[s]]
            # uniquify instance names per hierarchy level
            out.append(f"{name}_{model} {nets[0]} {nets[1]} {attr(attrs, 'value')}")
        elif s == "devices/gnd.sym":
            pass
    out.append(".ends")
    return out


if __name__ == "__main__":
    top = Path(sys.argv[1])
    assert top.suffix == ".sch"
    # DUT correspondence: DAC sym pin order == dac sch port order
    dpins = [lab for lab, _, _ in sym_pins(XSDIR / "r2r_dac8_pdk.sym")]
    dports = []
    for line in open(XSDIR / "r2r_dac8_pdk.sch"):
        m = re.match(r"C \{devices/[io]pin\.sym\} \S+ \S+ \d \d \{name=\S+ lab=([^}]*)\}",
                     line)
        if m:
            dports.append(m.group(1))
    assert dpins == dports, f"DAC pin-order mismatch: {dpins} vs {dports}"
    print(f"correspondence OK: r2r_dac8_pdk (13 pins)")
    sub_defs, top_lines = expand(top)
    L = ["* expanded visitor tb (strict expander, see scripts/expand_tb.py)",
         ".lib /home/alrida-ismail/.local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice tt",
         ".include results/dac_subckt.spice"]
    for sym, defi in sub_defs.items():
        # stepper subcircuit: rename ports b* (shared net names already match)
        L += defi
    # hoist directives last (code.sym order in file), but NEVER a second
    # .lib: reloading sky130.lib.spice redefines every PDK subckt and
    # ngspice's numparam binding breaks ("12 formal but 2 actual", proven).
    # The GUI flow still needs s_lib in the schematic; batch drops both the
    # raw .lib value line and its ** code comment here.
    L += [ln for ln in top_lines
          if not ln.startswith("** code") and not ln.startswith(".lib ")]
    L += [ln for ln in top_lines
          if ln.startswith("** code") and ".lib " not in ln]
    Path(sys.argv[2]).write_text("\n".join(L) + "\n")
    print(f"wrote {sys.argv[2]}")
