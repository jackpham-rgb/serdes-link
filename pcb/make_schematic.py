"""Write serdes_test_channel.kicad_sch: six SMA ports and the nets that join them."""
import pathlib, re, uuid

SYM = pathlib.Path(r"C:\Program Files\KiCad\10.0\share\kicad\symbols\Connector.kicad_sym").read_text(encoding="utf-8")
i = SYM.index('(symbol "Conn_Coaxial"')
d, j = 0, i
while True:
    if SYM[j] == "(": d += 1
    elif SYM[j] == ")":
        d -= 1
        if d == 0: break
    j += 1
block = SYM[i:j + 1].replace('(symbol "Conn_Coaxial"', '(symbol "Connector:Conn_Coaxial"', 1)
block = "\n".join("\t\t" + l for l in block.splitlines())

pins = re.findall(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)', block)
print("pins", pins)
OUT = pathlib.Path(__file__).with_name("serdes_test_channel.kicad_sch")
u = lambda: str(uuid.uuid4())


ROWS = [  # (left ref, left note, right ref, right note, net, line description)
    ("J1", "TX+", "J3", "RX+", "CH_P", "12 in 50 ohm microstrip, F.Cu over solid ground (In1.Cu)"),
    ("J2", "TX-", "J4", "RX-", "CH_M", "12 in 50 ohm microstrip, F.Cu over solid ground (In1.Cu)"),
    ("J5", "Thru A", "J6", "Thru B", "THRU", "1 in 50 ohm microstrip, same launch as the 12 in lines"),
]
ROOT = u()
body = []
XL, XR = 22.86, 132.08


def connector(ref, note, X, Y, mirror):
    """Coax connector; mirrored ones face right (pin 1 at X+5.08)."""
    mir = " (mirror y)" if mirror else ""
    pin_x = X + 5.08 if mirror else X - 5.08
    body.append(f'''	(symbol (lib_id "Connector:Conn_Coaxial") (at {X} {Y} 0){mir} (unit 1) (body_style 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
		(uuid "{u()}")
		(property "Reference" "{ref}" (at {X} {Y-6.35} 0) (effects (font (size 1.27 1.27))))
		(property "Value" "SMA edge launch" (at {X} {Y+13.97} 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount" (at {X} {Y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Datasheet" "" (at {X} {Y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(pin "1" (uuid "{u()}"))
		(pin "2" (uuid "{u()}"))
		(instances (project "serdes_test_channel" (path "/{ROOT}" (reference "{ref}") (unit 1))))
	)''')
    body.append(f'	(wire (pts (xy {X} {Y+5.08}) (xy {X} {Y+10.16})) (stroke (width 0) (type default)) (uuid "{u()}"))')
    body.append(f'	(label "GND" (at {X} {Y+10.16} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{u()}"))')
    body.append(f'	(text "{note}" (at {X} {Y-9.53} 0) (effects (font (size 1.8 1.8) bold)) (uuid "{u()}"))')
    return pin_x


for k, (lref, lnote, rref, rnote, net, desc) in enumerate(ROWS):
    Y = 50.8 + 29.21 * k
    x1 = connector(lref, lnote, XL, Y, mirror=True)
    x2 = connector(rref, rnote, XR, Y, mirror=False)
    body.append(f'	(wire (pts (xy {x1} {Y}) (xy {x2} {Y})) (stroke (width 0) (type default)) (uuid "{u()}"))')
    body.append(f'	(label "{net}" (at {x1 + 7.62} {Y} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{u()}"))')
    body.append(f'	(text "{desc}" (at {(x1 + x2) / 2} {Y + 3.81} 0) (effects (font (size 1.4 1.4))) (uuid "{u()}"))')
body.append(f'	(text "SerDes Link test channel" (at 12.7 15.24 0) (effects (font (size 3 3) bold) (justify left)) (uuid "{u()}"))')
body.append(f'	(text "J1-J3 and J2-J4 are the two halves of the differential channel,\\nmeasured as a 4-port in the order TX+, TX-, RX+, RX-." (at 12.7 22.86 0) (effects (font (size 1.4 1.4)) (justify left)) (uuid "{u()}"))')
body.append(f'	(text "J5-J6 is the thru line, measured to remove the connector and launch\\nfrom the 12 in results. Every shield ties to the ground pour and stitching vias." (at 12.7 30.48 0) (effects (font (size 1.4 1.4)) (justify left)) (uuid "{u()}"))')
sch = f'''(kicad_sch
	(version 20250114)
	(generator "eeschema")
	(generator_version "10.0")
	(uuid "{ROOT}")
	(paper "User" 160 180)
	(title_block (title "SerDes Link test channel") (date "2026-11-11") (rev "A") (comment 1 "Two 12 in 50 ohm microstrip lines and a 1 in thru, edge-launch SMA") (comment 2 "Jack Pham"))
	(lib_symbols
{block}
	)
{chr(10).join(body)}
	(sheet_instances (path "/" (page "1")))
	(embedded_fonts no)
)
'''
OUT.write_text(sch, encoding="utf-8")
print("wrote", OUT)
