"""Generate the Stage B test-channel board with KiCad's Python API (pcbnew).

Run with KiCad's bundled Python:

    "C:/Program Files/KiCad/10.0/bin/python.exe" pcb/make_test_channel_pcb.py

Writes pcb/serdes_test_channel.kicad_pcb. Everything below is in millimetres.

Board contents
  * Two 12 inch, 50 ohm microstrip lines on F.Cu, one for each half of the
    differential pair (TX+ to RX+ and TX- to RX-). They are 20 mm apart, so
    they behave as the two uncoupled lines assumed by the synthetic channel in
    data/touchstone/make_synthetic_channel.py. Port order TX+, TX-, RX+, RX-.
  * A 1 inch thru line with identical connectors and launches, for
    de-embedding the connector and launch from the 12 inch measurements.
  * Edge-launch SMA connectors (Amphenol 132289) on every port.
  * Solid ground on In1.Cu under the lines, ground pours on the other layers
    and a ground-via fence along every line.

The trace width is a starting value for a 4-layer JLCPCB-style stackup with
about 0.1 mm of prepreg between F.Cu and In1.Cu. Confirm it with the fab's
impedance calculator before ordering.
"""
from __future__ import annotations

import pathlib

import pcbnew
from pcbnew import FromMM as mm

OUT = pathlib.Path(__file__).with_name("serdes_test_channel.kicad_pcb")
FPLIB = r"C:\Program Files\KiCad\10.0\share\kicad\footprints\Connector_Coaxial.pretty"
FPNAME = "SMA_Amphenol_132289_EdgeMount"

LINE_LEN = 12 * 25.4          # pad-center to pad-center, mm
THRU_LEN = 1 * 25.4
PAD_HALF = 2.54               # SMA signal pad half length
W_TRACE = 0.16                # 50 ohm microstrip over ~0.1 mm prepreg (verify with fab)
W_PAD = 1.5
TAPER = 3.0
LINE_Y = (10.0, 30.0)
THRU_Y = 50.0
BOARD_L = LINE_LEN + 2 * PAD_HALF          # x of the right edge
TAB_L = THRU_LEN + 2 * PAD_HALF            # x of the right edge of the thru tab
BOARD_H = 40.0
TAB_H = 60.0

board = pcbnew.NewBoard(str(OUT))
board.SetCopperLayerCount(4)
board.GetDesignSettings().SetBoardThickness(mm(1.6))
board.GetDesignSettings().m_TrackMinWidth = mm(0.09)
board.GetDesignSettings().m_CopperEdgeClearance = 0  # edge-launch connectors sit on the edge, and the ground pours run to it

nets = {}


def net(name):
    if name not in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    return nets[name]


for n in ("GND", "CH_P", "CH_M", "THRU"):
    net(n)

L = pcbnew.F_Cu
V = lambda x, y: pcbnew.VECTOR2I(mm(x), mm(y))


def add_shape_poly(pts, layer, netname):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_POLY)
    s.SetLayer(layer)
    s.SetFilled(True)
    s.SetWidth(0)
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in pts:
        chain.Append(mm(x), mm(y))
    chain.SetClosed(True)
    ps = pcbnew.SHAPE_POLY_SET()
    ps.AddOutline(chain)
    s.SetPolyShape(ps)
    s.SetNet(net(netname))
    board.Add(s)
    return s


def outline(pts):
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        s.SetStart(V(*a)); s.SetEnd(V(*b))
        board.Add(s)


board_pts = [(0, 0), (BOARD_L, 0), (BOARD_L, BOARD_H), (TAB_L, BOARD_H), (TAB_L, TAB_H), (0, TAB_H)]
outline(board_pts)


def sma(ref, x, y, right_edge, netname):
    """Place an edge SMA. right_edge=True: board is to its left (body points +x)."""
    fp = pcbnew.FootprintLoad(FPLIB, FPNAME)
    fp.SetReference(ref)
    fp.SetValue("SMA edge launch")
    if right_edge:
        fp.SetPosition(V(x - PAD_HALF, y))
    else:
        fp.SetOrientationDegrees(180)
        fp.SetPosition(V(x + PAD_HALF, y))
    for p in fp.Pads():
        p.SetNet(net("GND") if p.GetNumber() == "2" else net(netname))
    board.Add(fp)
    return fp


def track(x1, y1, x2, y2, w, netname, layer=L):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(V(x1, y1)); t.SetEnd(V(x2, y2))
    t.SetWidth(mm(w)); t.SetLayer(layer)
    t.SetNet(net(netname))
    board.Add(t)


def via(x, y, netname="GND", drill=0.3, dia=0.6):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(x, y))
    v.SetDrill(mm(drill)); v.SetWidth(mm(dia))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetNet(net(netname))
    board.Add(v)


def line(y, x_left, x_right, net_left, net_right_unused, netname, refs):
    """x_left/x_right are the SMA pad centres (also the port reference planes)."""
    sma(refs[0], x_left - PAD_HALF, y, False, netname)
    sma(refs[1], x_right + PAD_HALF, y, True, netname)
    xa = x_left - PAD_HALF + PAD_HALF * 2 - 0.0   # inner end of the left pad
    xb = x_right + PAD_HALF - PAD_HALF * 2
    # tapers from the 1.5 mm pad to the trace at both ends
    add_shape_poly([(xa, y - W_PAD / 2), (xa + TAPER, y - W_TRACE / 2), (xa + TAPER, y + W_TRACE / 2), (xa, y + W_PAD / 2)], L, netname)
    add_shape_poly([(xb, y - W_PAD / 2), (xb - TAPER, y - W_TRACE / 2), (xb - TAPER, y + W_TRACE / 2), (xb, y + W_PAD / 2)], L, netname)
    track(xa + TAPER, y, xb - TAPER, y, W_TRACE, netname)
    # ground via fence
    x = xa + 4.0
    while x < xb - 4.0:
        for dy in (-1.2, 1.2):
            via(x, y + dy)
        x += 2.0
    return xa, xb


# Full-length differential halves. Port order: 1 TX+, 2 TX-, 3 RX+, 4 RX-.
line(LINE_Y[0], PAD_HALF, PAD_HALF + LINE_LEN, None, None, "CH_P", ("J1", "J3"))
line(LINE_Y[1], PAD_HALF, PAD_HALF + LINE_LEN, None, None, "CH_M", ("J2", "J4"))
line(THRU_Y, PAD_HALF, PAD_HALF + THRU_LEN, None, None, "THRU", ("J5", "J6"))

# Ground planes: In1 solid under the lines, F/B/In2 pours.
for layer in (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu, pcbnew.F_Cu):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net("GND"))
    z.SetLocalClearance(mm(0.5))
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in board_pts:
        ol.Append(mm(x), mm(y))
    board.Add(z)

# Clear In1 under every connector pad and taper so the wide pad does not
# load the launch (ground stays on In2 beneath it).
for z in board.Zones():
    if z.GetLayer() == pcbnew.In1_Cu:
        for y in (LINE_Y[0], LINE_Y[1], THRU_Y):
            for x0, x1 in ((0, 2 * PAD_HALF + TAPER + 1.0),
                           ((TAB_L if y == THRU_Y else BOARD_L) - (2 * PAD_HALF + TAPER + 1.0), TAB_L if y == THRU_Y else BOARD_L)):
                z.Outline().NewHole()
                for hx, hy in ((x0, y - 3), (x1, y - 3), (x1, y + 3), (x0, y + 3)):
                    z.Outline().Append(mm(hx), mm(hy), -1, z.Outline().OutlineCount() - 1)

# Labels on silkscreen
def text(s, x, y, size=1.5):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s); t.SetPosition(V(x, y)); t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    board.Add(t)


text("TX+  (P1)", 14, LINE_Y[0] - 5)
text("RX+  (P3)", BOARD_L - 14, LINE_Y[0] - 5)
text("TX-  (P2)", 14, LINE_Y[1] - 5)
text("RX-  (P4)", BOARD_L - 14, LINE_Y[1] - 5)
text("12 in, 50 ohm microstrip, uncoupled pair", BOARD_L / 2, LINE_Y[0] + 4)
text("12 in, 50 ohm microstrip, uncoupled pair", BOARD_L / 2, LINE_Y[1] + 4)
text("1 in thru (de-embedding)", 15.2, THRU_Y - 8)
text("SerDes Link Stage B test channel  rev A", BOARD_L / 2, BOARD_H - 1.5, 1.2)

filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())

pcbnew.SaveBoard(str(OUT), board)
print("wrote", OUT)
