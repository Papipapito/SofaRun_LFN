"""parchear.py — aplica srlfn.asm (nombres largos en la lista) al SR.COM de SofaRun 8.1.

Uso:  python parchear.py SR.COM.original SR.COM.nuevo
El original (SofaRun 8.1: 34.929 bytes, sha1 2f13bb73..., o la version de 2025-11, 35.115 bytes, sha1 2d95ca7d...) NO va en
el repositorio: hay que traer el propio. La version se elige sola por el sha1.
Necesita pasmo (http://pasmo.speccy.org/): en el PATH o, en Windows, dentro de WSL."""
import hashlib
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = 0x100
# Las versiones de SR.COM: el codigo de la lista y del dibujo es el mismo y esta en las mismas direcciones; cambian las
# variables, las rutinas de memoria y el final del fichero (un desplazamiento de unos 186 bytes mas alla de 3300h).
# fin = la direccion que sigue al final del fichero (ahi empezaba el monton); setlay = el LD A,(ancho) que sigue a la
# eleccion de 80/40 columnas; monton = las 4 palabras de la rutina que inicia el monton (fin, fin, fin, fin+2)
VARIANTES = {
    "2f13bb7303d4cc4f9c0a54c084907e320777be22": dict(
        nombre="8.1", fin=0x8971, malloc=0x5BD6, free=0x5CB4, maxfree=0x5FC3, array=0x7455, count=0x7D1B,
        sorted=0x7451, pathv=0x7D1D, widthv=0x7DEC, setlay=0x3E54, monton=(0x5F95, 0x5F9E, 0x5FA1, 0x5FBE)),
    "2d95ca7d366f7ac87b299102e1b148692d934706": dict(
        nombre="8.1 (2025-11)", fin=0x8A2B, malloc=0x5C90, free=0x5D6E, maxfree=0x607D, array=0x750F, count=0x7DD5,
        sorted=0x750B, pathv=0x7DD7, widthv=0x7EA6, setlay=0x3E5D, monton=(0x604F, 0x6058, 0x605B, 0x6078)),
}


def ganchos(v):
    """(direccion, bytes originales, opcode nuevo, simbolo) de esa version."""
    w = lambda x: bytes((x & 255, x >> 8))
    return [
        (0x0F86, b"\xC5\xFD\xE5", 0xCD, "mk"),                                # PUSH BC / PUSH IY      -> CALL mk
        (0x0E58, b"\x2A" + w(v["sorted"]), 0xCD, "build"),                     # LD HL,(SORTED)         -> CALL build
        (0x0CD2, b"\xD5\x2A" + w(v["array"]), 0xC3, "lfnfree"),                # PUSH DE / LD HL,(ARRAY) -> JP lfnfree + NOP
        (v["setlay"], b"\x3A" + w(v["widthv"]), 0xCD, "setlay"),               # LD A,(ancho)           -> CALL setlay
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
def ensamblar(d, v):
    with open(os.path.join(AQUI, "variante.inc"), "w") as f:
        f.write("FIN equ %04Xh\nMALLOC equ %04Xh\nFREE equ %04Xh\nMAXFREE equ %04Xh\nARRAY equ %04Xh\nCOUNT equ %04Xh\n"
                "SORTED equ %04Xh\nPATHV equ %04Xh\nWIDTHV equ %04Xh\n"
                % (v["fin"], v["malloc"], v["free"], v["maxfree"], v["array"], v["count"], v["sorted"], v["pathv"], v["widthv"]))
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
    for f in ("srlfn.hex", "srlfn.sym", "lay.inc", "variante.inc"):
        os.remove(os.path.join(AQUI, f))
    return memoria, simbolos


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    d = bytearray(open(sys.argv[1], "rb").read())
    sha = hashlib.sha1(d).hexdigest()
    if sha not in VARIANTES:
        sys.exit("%s no es un SR.COM que conozca (sha1 %s). Valen: %s" % (
            sys.argv[1], sha, "; ".join("%s %s" % (v["nombre"], s) for s, v in VARIANTES.items())))
    v = VARIANTES[sha]
    fin_orig = v["fin"]
    print("base: SofaRun %s" % v["nombre"])
    assert BASE + len(d) == fin_orig
    memoria, s = ensamblar(d, v)
    fin = s["codeend"]
    nueva_base = fin_orig + ((fin - fin_orig + 3) // 4) * 4       # el monton conserva su alineacion (1 mod 4)
    # el codigo, detras del final del original
    for a in range(fin_orig, fin):
        d.append(memoria.get(a, 0))
    for dir_, antes, op, sim in ganchos(v):
        o = dir_ - BASE
        assert d[o:o + len(antes)] == antes, "%04X: %s" % (dir_, d[o:o + len(antes)].hex())
        nuevo = bytes((op, s[sim] & 0xFF, s[sim] >> 8))
        d[o:o + len(antes)] = nuevo + b"\x00" * (len(antes) - 3)
    for dir_, valor in zip(v["monton"], (fin_orig, fin_orig, fin_orig, fin_orig + 2)):
        o = dir_ - BASE
        assert d[o] | d[o + 1] << 8 == valor, "%04X: %02X%02X" % (dir_, d[o + 1], d[o])
        nuevo = nueva_base + (valor - fin_orig)
        d[o], d[o + 1] = nuevo & 255, nuevo >> 8
    print("codigo %04Xh-%04Xh (%d bytes); el monton empieza en %04Xh (antes %04Xh)"
          % (fin_orig, fin - 1, fin - fin_orig, nueva_base, fin_orig))
    open(sys.argv[2], "wb").write(d)
    print("%s: %d bytes, sha1 %s" % (sys.argv[2], len(d), hashlib.sha1(d).hexdigest()))


if __name__ == "__main__":
    main()
