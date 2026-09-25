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


PARTS = [("J1", "CH_P", "Port 1  TX+"), ("J2", "CH_M", "Port 2  TX-"), ("J3", "CH_P", "Port 3  RX+"),
         ("J4", "CH_M", "Port 4  RX-"), ("J5", "THRU", "Thru A"), ("J6", "THRU", "Thru B")]
ROOT = u()
body = []
for k, (ref, netname, note) in enumerate(PARTS):
    X = 60.96 + 40.64 * (k % 3)
    Y = 63.5 + 50.8 * (k // 3)
    body.append(f'''	(symbol (lib_id "Connector:Conn_Coaxial") (at {X} {Y} 0) (unit 1) (body_style 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
		(uuid "{u()}")
		(property "Reference" "{ref}" (at {X} {Y-6.35} 0) (effects (font (size 1.27 1.27))))
		(property "Value" "SMA edge launch" (at {X} {Y+8.89} 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount" (at {X} {Y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Datasheet" "" (at {X} {Y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(pin "1" (uuid "{u()}"))
		(pin "2" (uuid "{u()}"))
		(instances (project "serdes_test_channel" (path "/{ROOT}" (reference "{ref}") (unit 1))))
	)''')
    body.append(f'	(wire (pts (xy {X-5.08} {Y}) (xy {X-12.7} {Y})) (stroke (width 0) (type default)) (uuid "{u()}"))')
    body.append(f'	(label "{netname}" (at {X-12.7} {Y} 180) (effects (font (size 1.27 1.27)) (justify right bottom)) (uuid "{u()}"))')
    body.append(f'	(wire (pts (xy {X} {Y+5.08}) (xy {X} {Y+12.7})) (stroke (width 0) (type default)) (uuid "{u()}"))')
    body.append(f'	(label "GND" (at {X} {Y+12.7} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{u()}"))')
    body.append(f'	(text "{note}" (at {X} {Y-11.43} 0) (effects (font (size 1.27 1.27))) (uuid "{u()}"))')
body.append(f'	(text "SerDes Link Stage B test channel: 12 in uncoupled pair (J1-J3, J2-J4) and 1 in thru (J5-J6)" (at 25.4 25.4 0) (effects (font (size 2 2)) (justify left)) (uuid "{u()}"))')
sch = f'''(kicad_sch
	(version 20250114)
	(generator "eeschema")
	(generator_version "10.0")
	(uuid "{ROOT}")
	(paper "A4")
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
