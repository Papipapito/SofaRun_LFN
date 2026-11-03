"""parchear.py — aplica srlfn.asm (nombres largos en la lista) al SR.COM de SofaRun 8.1.

Uso:  python parchear.py SR.COM.original SR.COM.nuevo
El original (SofaRun 8.1, 34.929 bytes, sha1 2f13bb73...) NO va en el repositorio: hay que traer el propio.
Necesita pasmo (http://pasmo.speccy.org/): en el PATH o, en Windows, dentro de WSL."""
import hashlib
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = 0x100
SHA1 = "2f13bb7303d4cc4f9c0a54c084907e320777be22"
FIN_ORIGINAL = 0x8971               # lo que sigue al final de SR.COM: ahi empezaba el monton

# (direccion, bytes originales, bytes nuevos o simbolo) -> ganchos con CALL/JP a nuestro codigo
GANCHOS = [
    (0x0F86, b"\xC5\xFD\xE5", 0xCD, "mk"),                 # PUSH BC / PUSH IY      -> CALL mk
    (0x0E58, b"\x2A\x51\x74", 0xCD, "build"),              # LD HL,(7451h)          -> CALL build
    (0x0CD2, b"\xD5\x2A\x55\x74", 0xC3, "lfnfree"),        # PUSH DE / LD HL,(7455h) -> JP lfnfree + NOP
    (0x3E54, b"\x3A\xEC\x7D", 0xCD, "setlay"),            # LD A,(7DECh)           -> CALL setlay
]
# La rejilla ancha: UNA columna de 80 (nombre de 63) en vez de cuatro de 20. No se toca el fichero: setlay escribe
# estas constantes al empezar el modo de pantalla de 80 columnas (y las de siempre con 40).
# (direccion, de siempre, ancha)
REJILLA = [
    (0x0F85, 0x0C, 0x3F),   # LD C,12 -> 63: ancho del nombre
    (0x0F95, 0x06, 0x07),   # LD C,6 -> 7: espacios que se borran antes del tamano
    (0x0FA1, 0x0C, 0x3F),   # ADD A,12 -> 63: de donde
    (0x0FCD, 0x0D, 0x41),   # ADD A,13 -> 65: el "<DIR>"
    (0x0FFF, 0x12, 0x46),   # ADD A,12h -> 46h: el tamano acaba en x+70
    (0x1038, 0x14, 0x50),   # paso de columna 20 -> 80
    (0x107D, 0x14, 0x20),   # el paso entre separadores: no pasar de 127 (SofaRun compara con signo): 79 + 32 > 80
    (0x104B, 0x13, 0x4F),   # el separador, en la ultima columna (79)
    (0x129D, 0x14, 0x50),   # columnas = ancho / 80
]
# El monton: 5F84h lo inicia en FIN_ORIGINAL; ahora empieza detras de nuestro codigo
PALABRAS_MONTON = [(0x5F95, FIN_ORIGINAL), (0x5F9E, FIN_ORIGINAL), (0x5FA1, FIN_ORIGINAL), (0x5FBE, FIN_ORIGINAL + 2)]


def ensamblar(d):
    # lay.inc: las constantes de la rejilla (se comprueba que en el original son las de siempre)
    with open(os.path.join(AQUI, "lay.inc"), "w") as f:
        f.write("LAYN equ %d\nlay:\n" % len(REJILLA))
        for dir_, viejo, nuevo in REJILLA:
            assert d[dir_ - BASE] == viejo, "%04X: %02X" % (dir_, d[dir_ - BASE])
            f.write("                dw      %04Xh\n                db      %02Xh,%02Xh\n" % (dir_, viejo, nuevo))
    for f in ("srlfn.hex", "srlfn.sym"):
        if os.path.exists(os.path.join(AQUI, f)):
            os.remove(os.path.join(AQUI, f))
    orden = ["pasmo", "--hex", "srlfn.asm", "srlfn.hex", "srlfn.sym"]
    if not shutil.which("pasmo") and shutil.which("wsl"):
        orden = ["wsl"] + orden
    r = subprocess.run(orden, cwd=AQUI, capture_output=True, text=True)
    if r.returncode:
        sys.exit("pasmo: " + r.stdout + r.stderr)
    simbolos = {}
    for linea in open(os.path.join(AQUI, "srlfn.sym")):
        p = linea.split()
        if len(p) >= 3 and p[1].upper() == "EQU":
            simbolos[p[0].lower()] = int(p[2].rstrip("Hh"), 16)
    memoria = {}
    for linea in open(os.path.join(AQUI, "srlfn.hex")):
        linea = linea.strip()
        if not linea.startswith(":"):
            continue
        b = bytes.fromhex(linea[1:])
        n, dir_, tipo = b[0], b[1] << 8 | b[2], b[3]
        if tipo == 0:
            for i in range(n):
                memoria[dir_ + i] = b[4 + i]
    for f in ("srlfn.hex", "srlfn.sym", "lay.inc"):
        os.remove(os.path.join(AQUI, f))
    return memoria, simbolos


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    d = bytearray(open(sys.argv[1], "rb").read())
    if hashlib.sha1(d).hexdigest() != SHA1:
        sys.exit("%s no es el SR.COM de SofaRun 8.1 original (sha1 %s)" % (sys.argv[1], SHA1))
    assert BASE + len(d) == FIN_ORIGINAL
    memoria, s = ensamblar(d)
    fin = s["codeend"]
    nueva_base = FIN_ORIGINAL + ((fin - FIN_ORIGINAL + 3) // 4) * 4       # el monton conserva su alineacion (1 mod 4)
    # el codigo, detras del final del original
    for a in range(FIN_ORIGINAL, fin):
        d.append(memoria.get(a, 0))
    for dir_, antes, op, sim in GANCHOS:
        o = dir_ - BASE
        assert d[o:o + len(antes)] == antes, "%04X: %s" % (dir_, d[o:o + len(antes)].hex())
        nuevo = bytes((op, s[sim] & 0xFF, s[sim] >> 8))
        d[o:o + len(antes)] = nuevo + b"\x00" * (len(antes) - 3)
    for dir_, valor in PALABRAS_MONTON:
        o = dir_ - BASE
        assert d[o] | d[o + 1] << 8 == valor, "%04X: %02X%02X" % (dir_, d[o + 1], d[o])
        nuevo = nueva_base + (valor - FIN_ORIGINAL)
        d[o], d[o + 1] = nuevo & 255, nuevo >> 8
    print("codigo %04Xh-%04Xh (%d bytes); el monton empieza en %04Xh (antes %04Xh)"
          % (FIN_ORIGINAL, fin - 1, fin - FIN_ORIGINAL, nueva_base, FIN_ORIGINAL))
    open(sys.argv[2], "wb").write(d)
    print("%s: %d bytes, sha1 %s" % (sys.argv[2], len(d), hashlib.sha1(d).hexdigest()))


if __name__ == "__main__":
    main()
