"""etapa_a.py - prueba de rejilla: SofaRun con dos columnas de 40 (nombres de 31), sin nombres largos todavia."""
import sys
d = bytearray(open(sys.argv[1], "rb").read())
# (direccion, esperado, nuevo)
P = [
    (0x0F85, 0x0C, 0x1F),   # LD C,12 -> 31: ancho del nombre
    (0x0F95, 0x06, 0x07),   # LD C,6 -> 7: espacios que se borran antes del tamano
    (0x0FA1, 0x0C, 0x1F),   # ADD A,12 -> 31: donde empiezan
    (0x0FCD, 0x0D, 0x21),   # ADD A,13 -> 33: "<DIR>"
    (0x0FFF, 0x12, 0x26),   # ADD A,12h -> 26h: el tamano acaba en x+38
    (0x1038, 0x14, 0x28),   # paso de columna 20 -> 40
    (0x107D, 0x14, 0x28),
    (0x104B, 0x13, 0x27),   # primer separador en x+39
    (0x129D, 0x14, 0x28),   # columnas = ancho / 40
]
for a, viejo, nuevo in P:
    assert d[a - 0x100] == viejo, "%04X: %02X" % (a, d[a - 0x100])
    d[a - 0x100] = nuevo
open(sys.argv[2], "wb").write(d)
print("ok", len(d))
