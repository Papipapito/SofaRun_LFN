#!/usr/bin/env python3
"""probar_mm.py - banco de pruebas REPRODUCIBLE de Multi Mente (MM.COM) en openMSX.

Comprueba, sin intervencion humana, lo que MM enseña para una carpeta con nombres largos (VFAT):
la LISTA (8.3 en el MM original, 12 caracteres + '>' en el parcheado) y el panel de File info.

    python probar_mm.py --mm-dir <carpeta con MM.COM, MM.EXE, MM.CFG, MMRET.DAT, MMMCR.DAT...> \\
                        --salida <carpeta> [--mm-com <otro MM.COM>] [--maquina Philips_NMS_8245] [--nextor 2.1.1|2.1.4]

Que hace (todo dentro de --salida; nada se escribe fuera, ni en el perfil de openMSX):
  1. Imagen de SD de 256 MB (MBR + FAT16 + Nextor 2.1.x) con MSXsdmaker.py ('imagen --sistema nextor214
     --programas mm'); se sustituye \\MM por el contenido de --mm-dir y se crea \\ROMS con unos 25 ficheros de
     prueba de nombre largo (mtools en WSL: mcopy crea las entradas LFN reales). Fechas y tamaños fijos.
  2. Maquina de openMSX = la indicada con el mapper al tamaño de --mapper-kb (por defecto 4096 KB) y un
     Sunrise IDE con el kernel Nextor elegido y la imagen. Se pasan a openMSX con OPENMSX_USER_DATA (una
     carpeta dentro de --salida), asi no se toca el perfil del usuario ni sus ajustes.
  3. Una sola instancia de openMSX con probar_mm.tcl: espera el prompt de DOS, 'CD \\ROMS', 'MM', espera a
     que MM pinte, captura la LISTA, baja el cursor a varios ficheros y captura el panel File info de cada
     uno; sale. Nota: 'MM <unidad:><carpeta>' del manual es la carpeta de los FICHEROS de MM, no la que se
     lista; MM lista la carpeta actual de DOS (por eso el CD previo).
  4. Deja en --salida: PNG de las capturas, probar_mm.log (lo hecho + registro del guion Tcl), la imagen,
     el listado de la imagen con nombres largos y cortos (imagen_ROMS.txt) y manifiesto.json.

Escenarios (--escenario):
  lista (defecto)  lo de arriba: lista y File info de 12 elementos.
  interaccion      imagen ampliada (+ .TXT largo, HOLA.COM, carpeta COPIA y 8 ficheros dentro de la carpeta larga) y
                   ordenar por nombre asc/desc, marcar, entrar/salir de la carpeta, volver 4 veces de [X]ecom (VER,
                   HOLA.COM, DIR, HOLA.COM; CHECK de que la lista vuelve a ser identica), borrar, copiar y salir.
  cs               'CS MM' desde \\MM, MM despues y comparacion de \\MM\\MM.COM antes/despues (leido de la imagen).
  libre            las --acciones que se den (DSL de probar_mm.tcl).
  --contar-ejecucion '3D60-3DDD 5CD0-5CFF' pone un punto de ruptura en cada direccion de esos rangos y cuenta, en los
  escenarios con acciones, cuantas veces se ejecuta una instruccion alli (codigo de MM.COM / otro programa en el TPA /
  otro slot). --mm-com usa otro MM.COM en lugar del de --mm-dir.

Rutas locales (no van en el repo; se pueden cambiar por argumento): ver las constantes de abajo.
Codigo de salida: 0 si todos los CHECK del guion han salido OK; 1 si alguno FALLA; 2 si el banco no ha podido
ejecutarse.
"""
import argparse
import calendar
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))

# ---- rutas locales (constantes documentadas; sobreescribibles por argumento) ----------------------------------
OPENMSX_EXE = r"C:\Program Files\openMSX\openmsx.exe"
SDMAKER = r"D:\proyectosAI\msx\SD_Maker\MSXsdmaker.py"
# Kernels Nextor para el Sunrise IDE. El 2.1.1 viene con openMSX (share\extensions); el 2.1.4 es el del repo
# de PicoVerse (Konamiman, Sunrise IDE, solo maestro).
NEXTOR_ROMS = {
    "2.1.1": None,  # se busca en <openMSX>\share\extensions\Nextor-2.1.1.SunriseIDE.ROM
    "2.1.4": r"D:\proyectosAI\msx\msx-picoverse-public\2350\software\explorer.pio\nextor\kernel"
             r"\Nextor-2.1.4.SunriseIDE.MasterOnly.ROM",
}
WSL_DISTRO = "Ubuntu-24.04"
WSL_MTOOLS = "$HOME/g3tools/mt/usr/bin"   # mtools sin root; si no existe se usa el del PATH de WSL

# ---- contenido de prueba -----------------------------------------------------------------------------------
# Fecha fija (UTC) para los ficheros de prueba: que File info (Time:) salga igual en cada ejecucion.
FECHA = calendar.timegm((2024, 3, 15, 10, 20, 30))
N_DIR = "Mis Juegos Favoritos"            # una carpeta con nombre largo


def _ficheros():
    """(nombre, tamaño). Orden = orden en el directorio de la imagen (mcopy los crea uno a uno)."""
    n60 = "Knightmare 3 - Shalom - The Legendary Warrior (1987)(Konami).rom"
    n60 = n60[:56] + ".rom"                                   # 60 caracteres justos
    L = [
        "Metal Gear 2 - Solid Snake (1990)(Konami).rom",       # 45
        "Metal Gear 2 - Solid Snake (1990)(Konami)[a1].rom",   # 49, misma raiz de 12
        "Aleste 1 - Eleven Fighters (1988)(Compile).rom",      # 46
        "Aleste 1 - Eleven Fighters (1988)(Compile)[a1].rom",  # 50, misma raiz de 12
        "Aleste 1 - Eleven Fighters (1988)(Compile)(JP).rom",  # 50, misma raiz de 12
        "Aleste 2 (1989)(Compile).rom",                        # 28
        "Pac.rom",                                             # 7
        "Zanac-EX.rom",                                        # 12
        "King Kong.rom",                                       # 13
        "Space Manbow (1989)(Konami).rom",                     # 31
        "Parodius - Fantasy Adventure.rom",                    # 32
        n60,                                                   # 60
        "M\u00fasica espa\u00f1ola \u00f1 (1990).rom",          # con acentos
        "Nemesis 3 - The Eve of Destruction (1988)(Konami).rom",
        "Gradius 2 - Nemesis 2 (1987)(Konami).rom",
        "Vampire Killer - Akumajo Dracula.rom",
        "Penguin Adventure (1986)(Konami).rom",
        "The Treasure of Usas (1987)(Konami).rom",
        "F-1 Spirit - The Way to Formula-1 (1987)(Konami).rom",
        "Quarth (1989)(Konami).rom",
        "Golvellius - Valley of Doom (1987)(Compile)(JP).rom",
        "README.TXT",                                          # solo 8.3
        "notes.txt",                                           # 8.3 en minusculas
    ]
    assert len(L[6]) == 7 and len(L[7]) == 12 and len(L[8]) == 13 and len(L[9]) == 31
    assert len(L[10]) == 32 and len(L[11]) == 60
    return [(n, 8192 * (i + 1) + 17 * i) for i, n in enumerate(L)]


FICHEROS = _ficheros()
# BENCH_EXTRA=N: N ficheros mas (nombre largo de unos 50 caracteres) para probar carpetas grandes
FICHEROS = FICHEROS + [("Juego de prueba numero %04d - con un subtitulo bastante largo (1990)(Test).rom" % i, 1024 + i)
                       for i in range(int(os.environ.get("BENCH_EXTRA", "0")))]

# Contenido AMPLIADO (escenarios 'interaccion' y 'cs'; el escenario 'lista' sigue con el de siempre):
#   \ROMS: ademas un .TXT de nombre largo y HOLA.COM (programa de prueba 8.3), la carpeta larga con 8 ficheros dentro
#   y una carpeta COPIA (8.3, vacia) como destino de las copias.
N_TXT = "Notas de la coleccion de Konami.txt"
N_COM = "HOLA.COM"
DIR_COPIA = "COPIA"
MSG_HOLA = b"HOLA desde HOLA.COM\r\n$"


def hola_com():
    """HOLA.COM hecho a mano (Z80): escribe MSG_HOLA con la funcion 9 de BDOS y termina (funcion 0). 8.3, 16 bytes
    de codigo mas el texto. LD DE,msg / LD C,9 / CALL 5 / LD C,0 / CALL 5."""
    codigo = bytes([0x11, 0x0D, 0x01, 0x0E, 0x09, 0xCD, 0x05, 0x00, 0x0E, 0x00, 0xCD, 0x05, 0x00])
    assert len(codigo) == 13       # el texto empieza en 0100h + 13 = 010Dh
    return codigo + MSG_HOLA


FICHEROS_DIR = [(n, 1000 * (i + 1) + 7 * i) for i, n in enumerate([
    "Contra (1987)(Konami).rom",
    "Castlevania - Vampire Killer (1986)(Konami).rom",
    "Nemesis 2 - Gradius 2 (1987)(Konami).rom",
    "Hydlide 3 - The Space Memories (1987)(T and E Soft).rom",
    "Salamander (1987)(Konami).rom",
    "The Maze of Galious - Knightmare 2 (1987)(Konami).rom",
    "GAME1.ROM",                                               # 8.3
    "LEEME.TXT",                                               # 8.3
])]
AMPLIADO = False       # lo pone main() segun el escenario
SIN_LFN_DIR = ("GAME1.ROM", "LEEME.TXT")
CORTOS_DIR = {}


def orden_roms():
    """Orden de los elementos de \\ROMS en el directorio (= el de la lista de MM: no ordena)."""
    if AMPLIADO:
        return [n for n, _ in FICHEROS] + [N_TXT, N_COM, N_DIR, DIR_COPIA]
    return [n for n, _ in FICHEROS] + [N_DIR]
# Ficheros de los que se captura File info (por defecto), con su etiqueta
INFO_DEFECTO = [
    "Metal Gear 2 - Solid Snake (1990)(Konami).rom",      # 45 > 31: 20 + '...' + 8 finales
    "Aleste 1 - Eleven Fighters (1988)(Compile)[a1].rom",  # misma raiz de 12 que otros dos
    "Pac.rom",                                             # 7 caracteres
    "Zanac-EX.rom",                                        # 12
    "King Kong.rom",                                       # 13
    "Space Manbow (1989)(Konami).rom",                     # 31: cabe entero
    FICHEROS[10][0],                                       # 32
    FICHEROS[11][0],                                       # 60
    FICHEROS[12][0],                                       # acentos
    "README.TXT",                                          # 8.3
    N_DIR,                                                 # carpeta con nombre largo
]


SIN_LFN = ("README.TXT", "notes.txt", "HOLA.COM", "COPIA")     # sin nombre largo (el segundo, 8.3 con los bits de minusculas de NT)
CORTOS = {}   # nombre largo (o 8.3) -> nombre corto que mtools ha dejado en la imagen (se llena al construirla)


def fmt83(sfn):
    """Como pinta MM un 8.3 en la lista: nombre a 8 columnas, punto y extension ('PAC     .ROM')."""
    nom, _, ext = sfn.partition(".")
    return nom.ljust(8) + "." + ext if ext else nom


def esperado_lista(nombre, parche=True):
    """Lo que debe verse en la lista. Con parche: los 12 primeros caracteres y '>' si sigue (ASCII sin acentos);
    las carpetas llevan una barra invertida en lugar de '>'; los que no tienen nombre largo salen en 8.3.
    Sin parche: el 8.3 (lo que haya dejado mtools en la imagen; un byte no ASCII sale como '?')."""
    es_dir = nombre in (N_DIR, "COPIA")
    corto = "".join(c if ord(c) < 128 else "?" for c in CORTOS.get(nombre, "?"))
    if not parche or nombre in SIN_LFN:
        return corto + "\\" if es_dir else fmt83(corto)
    s = _ascii(nombre)
    if es_dir:
        return s[:12] + "\\"
    return s if len(s) <= 12 else s[:12] + ">"


def esperado_info(nombre):
    """Lo que debe verse en el campo Name: de File info con el parche (hasta 31; si no, 20 + ... + 8)."""
    s = _ascii(nombre)
    return s if len(s) <= 31 else s[:20] + "..." + s[-8:]


def _ascii(s):
    import unicodedata
    return "".join(c if ord(c) < 128 else (unicodedata.normalize("NFD", c)[0] if ord(unicodedata.normalize("NFD", c)[0]) < 128 else "?") for c in s)


# ---- utilidades -----------------------------------------------------------------------------------------------
class Log:
    def __init__(self, ruta):
        self.f = open(ruta, "w", encoding="utf-8", newline="\n")

    def __call__(self, *a):
        s = " ".join(str(x) for x in a)
        print(s, flush=True)
        self.f.write(s + "\n")
        self.f.flush()


def wslpath(p):
    p = os.path.abspath(p).replace("\\", "/")
    return "/mnt/%s%s" % (p[0].lower(), p[2:])


def wsl(args, log, check=True, timeout=300):
    r = subprocess.run(["wsl", "-d", WSL_DISTRO, "--"] + args, capture_output=True, timeout=timeout)
    out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    if check and r.returncode != 0:
        log("WSL FALLO (%d): %s\n%s" % (r.returncode, " ".join(args), out[-1500:]))
        raise SystemExit(2)
    return out


def sha1(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()


def tclq(s):
    """Literal Tcl entre comillas dobles; todo lo que el parser de Tcl podria interpretar (\\ " [ ] $ { } ; y lo que
    no sea ASCII imprimible) va como \\uXXXX (4 digitos exactos, sin el problema de \\x, que se come todos los
    digitos hexadecimales que siguen)."""
    return '"' + "".join("\\u%04x" % ord(c) if (c in '\\"[]${};' or not 32 <= ord(c) < 127) else c for c in s) + '"'




def leer_dir_fat16(img, lba, ruta):
    """Lee a mano (sin mtools) un directorio de la particion FAT16: ([(8.3, atributos, byte NT, nombre largo o None,
    n.o de entradas LFN, checksum de las LFN correcto o None, tamaño)] en el orden del directorio, desplazamiento
    en la imagen del primer byte del directorio)."""
    import struct
    f = open(img, "rb")
    base = lba * 512
    f.seek(base)
    bs = f.read(512)
    bps, spc, rsv, nfat, nroot, tot16, _m, spf = struct.unpack_from("<HBHBHHBH", bs, 11)
    root_sec = rsv + nfat * spf
    root_secs = (nroot * 32 + bps - 1) // bps
    data_sec = root_sec + root_secs

    def rd(sec, n=1):
        f.seek(base + sec * bps)
        return f.read(n * bps)
    fat = rd(rsv, spf)

    def cadena(c):
        out = []
        while 2 <= c < 0xFFF8:
            out.append(c)
            c = struct.unpack_from("<H", fat, c * 2)[0]
        return out

    def entradas(raw):
        res, lfn = [], []
        for i in range(0, len(raw), 32):
            e = raw[i:i + 32]
            if e[0] == 0:
                break
            if e[0] == 0xE5:
                lfn = []
            elif e[11] == 0x0F:
                lfn.append(e)
            else:
                res.append((e, lfn))
                lfn = []
        return res
    raw = rd(root_sec, root_secs)
    off0 = base + root_sec * bps
    for parte in [x for x in ruta.split("/") if x]:
        for e, _l in entradas(raw):
            if e[:11].decode("cp850", "replace").strip().upper() == parte.upper():
                c = struct.unpack_from("<H", e, 26)[0]
                off0 = base + (data_sec + (c - 2) * spc) * bps
                raw = b"".join(rd(data_sec + (x - 2) * spc, spc) for x in cadena(c))
                break
        else:
            raise SystemExit("la imagen no tiene %s" % ruta)
    out = []
    for e, lfn in entradas(raw):
        nom, ext = e[:8].decode("cp850").rstrip(), e[8:11].decode("cp850").rstrip()
        ck = 0
        for b in e[:11]:
            ck = (((ck & 1) << 7) + (ck >> 1) + b) & 0xFF
        largo = None
        if lfn:
            trozos = []
            for le in reversed(lfn):
                u = (le[1:11] + le[14:26] + le[28:32]).decode("utf-16-le")
                trozos.append(u.split("\x00")[0] if "\x00" in u else u.split("\uffff")[0])
            largo = "".join(trozos)
        out.append((nom + ("." + ext if ext else ""), e[11], e[12], largo, len(lfn),
                    all(le[13] == ck for le in lfn) if lfn else None, struct.unpack_from("<I", e, 28)[0]))
    return out, off0


def leer_fichero_fat16(img, lba, ruta):
    """Lee a mano un fichero de la particion FAT16 (ruta 'MM/MM.COM'): {'datos': bytes (cortados al tamaño de la entrada
    de directorio), 'tam_dir': tamaño que dice la entrada, 'clusters': n.o de clusters de la cadena, 'cluster0': primero}."""
    import struct
    f = open(img, "rb")
    base = lba * 512
    f.seek(base)
    bs = f.read(512)
    bps, spc, rsv, nfat, nroot, tot16, _m, spf = struct.unpack_from("<HBHBHHBH", bs, 11)
    root_sec = rsv + nfat * spf
    root_secs = (nroot * 32 + bps - 1) // bps
    data_sec = root_sec + root_secs

    def rd(sec, n=1):
        f.seek(base + sec * bps)
        return f.read(n * bps)
    fat = rd(rsv, spf)

    def cadena(c):
        out = []
        while 2 <= c < 0xFFF8:
            out.append(c)
            c = struct.unpack_from("<H", fat, c * 2)[0]
        return out

    def entradas(raw):
        for i in range(0, len(raw), 32):
            e = raw[i:i + 32]
            if e[0] == 0:
                return
            if e[0] != 0xE5 and e[11] != 0x0F:
                yield e

    def nom11(parte):
        n, _, x = parte.partition(".")
        return (n.upper().ljust(8) + x.upper().ljust(3)).encode("cp850")

    raw = rd(root_sec, root_secs)
    partes = [x for x in ruta.split("/") if x]
    for k, parte in enumerate(partes):
        for e in entradas(raw):
            if bytes(e[:11]) == nom11(parte):
                c = struct.unpack_from("<H", e, 26)[0]
                if k == len(partes) - 1:
                    ch = cadena(c)
                    datos = b"".join(rd(data_sec + (x - 2) * spc, spc) for x in ch)
                    tam = struct.unpack_from("<I", e, 28)[0]
                    return {"datos": datos[:tam], "tam_dir": tam, "clusters": len(ch), "cluster0": c,
                            "bytes_cadena": len(datos)}
                raw = b"".join(rd(data_sec + (x - 2) * spc, spc) for x in cadena(c))
                break
        else:
            raise SystemExit("la imagen no tiene %s" % ruta)


def rangos_distintos(antes, despues):
    """[(inicio, fin_inclusive)] de los tramos en que antes y despues difieren (en la parte comun)."""
    res, ini = [], None
    for i in range(min(len(antes), len(despues))):
        if antes[i] != despues[i]:
            if ini is None:
                ini = i
        elif ini is not None:
            res.append((ini, i - 1))
            ini = None
    if ini is not None:
        res.append((ini, min(len(antes), len(despues)) - 1))
    return res


def analisis_cs(a, W, log):
    img = os.path.join(W, "mm_test.img")
    antes = open(mm_com_ruta(a), "rb").read()
    r = leer_fichero_fat16(img, a.lba, "MM/MM.COM")
    despues = r["datos"]
    log("== analisis de CS: \\MM\\MM.COM antes (%s) y despues (leido de la imagen) ==" % mm_com_ruta(a))
    log("  tamaño antes %d bytes (sha1 %s); despues %d bytes (entrada de directorio %d, %d clusters, cadena de %d bytes; "
        "sha1 %s)" % (len(antes), hashlib.sha1(antes).hexdigest()[:12], len(despues), r["tam_dir"], r["clusters"],
                      r["bytes_cadena"], hashlib.sha1(despues).hexdigest()[:12]))
    log("  tamaño: %s" % ("IGUAL" if len(antes) == len(despues) else "CAMBIA (%+d bytes)" % (len(despues) - len(antes))))
    rg = rangos_distintos(antes, despues)
    n_dif = sum(f - i + 1 for i, f in rg)
    log("  bytes distintos en la parte comun: %d en %d tramos" % (n_dif, len(rg)))
    for i, f in rg[:40]:
        log("    offset %04X-%04X (%d bytes; direccion en memoria %04X-%04X): antes %s | despues %s" % (
            i, f, f - i + 1, i + 0x100, f + 0x100, antes[i:min(f + 1, i + 16)].hex(), despues[i:min(f + 1, i + 16)].hex()))
    if len(rg) > 40:
        log("    ... y %d tramos mas" % (len(rg) - 40))
    if len(despues) > len(antes):
        log("  CS ha AÑADIDO %d bytes al final: %s..." % (len(despues) - len(antes), despues[len(antes):len(antes) + 16].hex()))
    elif len(despues) < len(antes):
        log("  CS ha TRUNCADO el fichero: faltan %d bytes del final" % (len(antes) - len(despues)))
    with open(os.path.join(a.salida, "cs_diferencias.txt"), "w", encoding="utf-8") as fo:
        fo.write("antes %d bytes, despues %d bytes\n" % (len(antes), len(despues)))
        for i, f in rg:
            fo.write("%04X-%04X %d bytes antes=%s despues=%s\n" % (i, f, f - i + 1, antes[i:f + 1].hex(), despues[i:f + 1].hex()))
    with open(os.path.join(a.salida, "MM_despues_de_CS.COM"), "wb") as fo:
        fo.write(despues)
    log("  (MM.COM tras CS guardado en %s)" % os.path.join(a.salida, "MM_despues_de_CS.COM"))


def volcado_final(a, W, log):
    img = os.path.join(W, "mm_test.img")
    sub = CORTOS[N_DIR]
    log("== estado final de la imagen (leido a mano) ==")
    with open(os.path.join(a.salida, "imagen_despues.txt"), "w", encoding="utf-8") as fo:
        for ruta in ("ROMS", "ROMS/" + sub, "ROMS/" + DIR_COPIA):
            ents, _o = leer_dir_fat16(img, a.lba, ruta)
            fo.write("# \\%s\n" % ruta.replace("/", "\\"))
            for sfn, at, nt, largo, nl, ck, sz in ents:
                fo.write("%-13s %02X %02X %d %-5s %7d  %s\n" % (sfn, at, nt, nl, ck, sz, largo if largo is not None else "(sin nombre largo)"))
            if ruta.endswith(DIR_COPIA):
                log("  \\ROMS\\COPIA: %s" % [(sfn, largo, sz) for sfn, at, nt, largo, nl, ck, sz in ents if sfn not in (".", "..")])
            if ruta == "ROMS":
                nombres = {sfn for sfn, *_r in ents}
                log("  \\ROMS: %d entradas; ALESTE~1.ROM %s" % (len(ents), "sigue" if "ALESTE~1.ROM" in nombres else "borrado"))
    log("  (volcado completo en imagen_despues.txt)")


def bp_resumen(txt, log):
    lin = [l.strip() for l in txt.splitlines() if "BP-INFORME" in l or " BP " in l]
    if lin:
        log("== puntos de ruptura (ejecuciones contadas) ==")
        for l in lin:
            log("  " + l)


def resumen_escenario(a, W, txt, log):
    if a.escenario == "cs":
        analisis_cs(a, W, log)
    elif a.escenario == "interaccion":
        volcado_final(a, W, log)
    bp_resumen(txt, log)


def fijar_fecha_punto(img, off0, epoch):
    """mmd da a '.' y '..' la hora actual: se les pone la fecha fija (File info enseña la de la entrada '..' al entrar)."""
    import struct
    t = time.gmtime(epoch)
    hora = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
    dia = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
    with open(img, "r+b") as f:
        for k in (0, 1):                       # entradas '.' y '..'
            f.seek(off0 + k * 32)
            e = bytearray(f.read(32))
            assert e[0] == 0x2E, "se esperaba '.'/'..' en la entrada %d" % k
            struct.pack_into("<HHHHHH", e, 14, hora, dia, dia, 0, hora, dia)   # creacion, acceso, (cluster alto), escritura
            f.seek(off0 + k * 32)
            f.write(bytes(e))


# ---- 1. imagen -------------------------------------------------------------------------------------------------
def mm_com_ruta(a):
    return a.mm_com or os.path.join(a.mm_dir, "MM.COM")


def construir_imagen(a, W, log):
    img = os.path.join(W, "mm_test.img")
    if os.path.exists(img):
        os.remove(img)
    log("== 1. imagen de SD (MSXsdmaker + mtools) ==")
    cmd = [sys.executable, a.sdmaker, "imagen", img, "--tamano", a.tamano, "--sistema", "nextor214",
           "--programas", "mm"]
    log("  $", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log("  " + "\n  ".join(r.stdout.strip().splitlines()[-4:]))
    if r.returncode != 0 or not os.path.exists(img):
        log("FALLO MSXsdmaker:", r.stderr[-800:])
        raise SystemExit(2)
    # tabla de particiones: la 1 empieza en el LBA del byte 454 de la MBR
    mbr = open(img, "rb").read(512)
    assert mbr[510:512] == b"\x55\xaa", "MBR sin firma 55AA"
    lba = int.from_bytes(mbr[454:458], "little")
    a.lba = lba
    tipo = mbr[450]
    log("  particion 1: tipo %02Xh, LBA %d (offset %d bytes)" % (tipo, lba, lba * 512))

    # ficheros de prueba en disco (con fecha fija)
    st = os.path.join(W, "stage_ROMS")
    shutil.rmtree(st, ignore_errors=True)
    os.makedirs(st)
    for n, size in FICHEROS:
        p = os.path.join(st, n)
        cab = ("MMTEST %s " % n).encode("utf-8")
        with open(p, "wb") as f:
            f.write((cab * (size // len(cab) + 1))[:size])
        os.utime(p, (FECHA, FECHA))
    os.makedirs(os.path.join(st, N_DIR), exist_ok=True)
    os.utime(os.path.join(st, N_DIR), (FECHA, FECHA))
    if AMPLIADO:
        with open(os.path.join(st, N_TXT), "wb") as f:
            f.write((b"Notas de la coleccion. " * 200)[:3000])
        os.utime(os.path.join(st, N_TXT), (FECHA, FECHA))
        with open(os.path.join(st, N_COM), "wb") as f:
            f.write(hola_com())
        os.utime(os.path.join(st, N_COM), (FECHA, FECHA))
        os.makedirs(os.path.join(st, DIR_COPIA), exist_ok=True)
        os.utime(os.path.join(st, DIR_COPIA), (FECHA, FECHA))
        std = os.path.join(st, "dentro")          # los ficheros de la carpeta larga, fuera del arbol de \\ROMS
        os.makedirs(std, exist_ok=True)
        for n, size in FICHEROS_DIR:
            cab = ("MMTEST %s " % n).encode("utf-8")
            with open(os.path.join(std, n), "wb") as f:
                f.write((cab * (size // len(cab) + 1))[:size])
            os.utime(os.path.join(std, n), (FECHA, FECHA))

    # carpeta de MM: todo lo de --mm-dir salvo ocultos y .bak
    mmfiles = sorted(f for f in os.listdir(a.mm_dir)
                     if os.path.isfile(os.path.join(a.mm_dir, f)) and not f.startswith(".")
                     and not f.lower().endswith(".bak"))
    for need in ("MM.COM", "MM.EXE"):
        if need not in [f.upper() for f in mmfiles]:
            log("FALTA %s en --mm-dir %s" % (need, a.mm_dir))
            raise SystemExit(2)

    sh = os.path.join(W, "construir_imagen.sh")
    L = ["#!/bin/bash", "set -eu", "export MTOOLS_SKIP_CHECK=1 LC_ALL=C.UTF-8 TZ=UTC",
         'MT="%s"' % WSL_MTOOLS, '[ -x "$MT/mcopy" ] || MT="$(dirname "$(command -v mcopy)")"',
         "P=%s" % shlex.quote("%s@@%d" % (wslpath(img), lba * 512)),
         '"$MT/mdeltree" -i "$P" ::/MM', '"$MT/mmd" -i "$P" ::/MM']
    for f in mmfiles:
        orig = a.mm_com if (a.mm_com and f.upper() == "MM.COM") else os.path.join(a.mm_dir, f)
        L.append('"$MT/mcopy" -i "$P" -m %s %s' % (shlex.quote(wslpath(orig)), shlex.quote("::/MM/" + f)))
    L.append('"$MT/mmd" -i "$P" ::/ROMS')
    for n, _ in FICHEROS:
        L.append('"$MT/mcopy" -i "$P" -m %s ::/ROMS/' % shlex.quote(wslpath(os.path.join(st, n))))
    if AMPLIADO:
        for n in (N_TXT, N_COM):
            L.append('"$MT/mcopy" -i "$P" -m %s ::/ROMS/' % shlex.quote(wslpath(os.path.join(st, n))))
    L.append('"$MT/mcopy" -i "$P" -s -m %s ::/ROMS/' % shlex.quote(wslpath(os.path.join(st, N_DIR))))
    if AMPLIADO:
        L.append('"$MT/mcopy" -i "$P" -s -m %s ::/ROMS/' % shlex.quote(wslpath(os.path.join(st, DIR_COPIA))))
        for n, _ in FICHEROS_DIR:
            L.append('"$MT/mcopy" -i "$P" -m %s %s' % (shlex.quote(wslpath(os.path.join(st, "dentro", n))),
                                                      shlex.quote("::/ROMS/%s/" % N_DIR)))
    L += ['echo "---- ::/MM"', '"$MT/mdir" -i "$P" ::/MM',
          'echo "---- ::/ROMS (nombres cortos y largos)"', '"$MT/mdir" -i "$P" ::/ROMS',
          'echo "---- ::/ROMS/%s"' % N_DIR, '"$MT/mdir" -i "$P" %s' % shlex.quote("::/ROMS/" + N_DIR),
          'echo "---- ::/AUTOEXEC.BAT"', '"$MT/mtype" -i "$P" ::/AUTOEXEC.BAT | tr -d "\\r"',
          'echo "---- sha1 de \\MM\\MM.COM dentro de la imagen"',
          '"$MT/mcopy" -i "$P" ::/MM/MM.COM - | sha1sum']
    open(sh, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    out = wsl(["bash", wslpath(sh)], log)
    shutil.copy(sh, os.path.join(a.salida, "construir_imagen.sh"))
    open(os.path.join(a.salida, "imagen_ROMS.txt"), "w", encoding="utf-8").write(out)
    m = re.search(r"([0-9a-f]{40})\s+-\s*$", out.strip())
    en_img = m.group(1) if m else "?"
    en_dir = sha1(mm_com_ruta(a))
    log("  \\MM\\MM.COM: sha1 en --mm-dir %s, en la imagen %s -> %s" % (en_dir, en_img,
                                                                       "IGUAL" if en_dir == en_img else "DISTINTO"))
    if en_dir != en_img:
        raise SystemExit(2)
    _r, off0 = leer_dir_fat16(img, lba, "ROMS")
    fijar_fecha_punto(img, off0, FECHA)
    reales, _o = leer_dir_fat16(img, lba, "ROMS")
    if AMPLIADO:     # '.' y '..' de las subcarpetas, y los ficheros de dentro
        cortos_n_dir = next(sfn for sfn, _a, _n, largo, *_r in reales if largo == N_DIR)
        for sub in (cortos_n_dir, DIR_COPIA):
            _x, off_sub = leer_dir_fat16(img, lba, "ROMS/" + sub)
            fijar_fecha_punto(img, off_sub, FECHA)
        dentro, _o = leer_dir_fat16(img, lba, "ROMS/" + cortos_n_dir)
        for sfn, at, nt, largo, nl, ck, sz in dentro:
            if sfn in (".", ".."):
                continue
            CORTOS_DIR[largo or next((n for n, _z in FICHEROS_DIR if n.upper() == sfn.upper()), sfn)] = sfn
        sin_d = [n for n, _z in FICHEROS_DIR if n not in CORTOS_DIR or (n not in SIN_LFN_DIR and CORTOS_DIR[n] == n.upper())]
        log("  \\ROMS\\%s en la imagen: %d ficheros (%d con nombre largo): %s" % (
            N_DIR, len(CORTOS_DIR), sum(1 for n in CORTOS_DIR if n not in SIN_LFN_DIR),
            ", ".join("%s=%s" % (v, k[:20]) for k, v in CORTOS_DIR.items())))
    with open(os.path.join(a.salida, "imagen_ROMS_LFN.txt"), "w", encoding="utf-8") as fo:
        fo.write("# entradas de \\ROMS leidas a mano de la imagen: 8.3 | attr | byte NT | n.o LFN | checksum ok"
                 " | tamaño | nombre largo\n")
        for sfn, at, nt, largo, nl, ck, sz in reales:
            fo.write("%-13s %02X %02X %d %-5s %7d  %s\n" % (sfn, at, nt, nl, ck, sz,
                                                           largo if largo is not None else "(sin nombre largo)"))
    for sfn, at, nt, largo, nl, ck, sz in reales:
        if sfn in (".", ".."):
            continue
        clave = largo or next((n for n, _z in FICHEROS if n.upper() == sfn.upper()), sfn)
        CORTOS[clave] = sfn
    esperados = {n: s_ for n, s_ in FICHEROS}
    esperados[N_DIR] = 0
    con_lfn = {l for _s, _a, _n, l, _c, ok_, _z in reales if l and ok_}
    if AMPLIADO:
        esperados[N_TXT] = 0
        esperados[N_COM] = 0
        esperados[DIR_COPIA] = 0
    sin = [n for n in esperados if n not in con_lfn and n not in SIN_LFN and n not in (N_COM, DIR_COPIA)]
    log("  \\ROMS en la imagen: %d entradas (con '.' y '..'), %d con nombre largo de checksum correcto; faltan sin LFN: %s"
        % (len(reales), len(con_lfn), sin or "ninguno"))
    if sin:
        raise SystemExit(2)
    log("  imagen lista: %s (%d bytes, %s), mdir de \\ROMS en imagen_ROMS.txt" %
        (img, os.path.getsize(img), time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(img)))))
    return img, mmfiles


# ---- 2. maquina + extension ----------------------------------------------------------------------------------
def preparar_openmsx(a, W, img, log):
    log("== 2. maquina y Sunrise IDE ==")
    share = os.path.join(os.path.dirname(a.openmsx), "share")
    src = os.path.join(share, "machines", a.maquina + ".xml")
    if not os.path.exists(src):
        log("No existe la maquina %s (%s)" % (a.maquina, src))
        raise SystemExit(2)
    xml = open(src, encoding="utf-8").read()
    mname = "MMbench_%s_%dKB" % (a.maquina, a.mapper_kb)
    if a.mapper_kb:
        m = re.search(r"(<MemoryMapper[^>]*>\s*<size>)(\d+)(</size>)", xml)
        if not m:
            log("La maquina %s no tiene <MemoryMapper><size>; no se puede cambiar el mapper" % a.maquina)
            raise SystemExit(2)
        log("  mapper de %s: %s KB -> %d KB" % (a.maquina, m.group(2), a.mapper_kb))
        xml = xml[:m.start(2)] + str(a.mapper_kb) + xml[m.end(2):]
    ud = os.path.join(W, "openmsx_userdata")
    shutil.rmtree(ud, ignore_errors=True)
    os.makedirs(os.path.join(ud, "machines"))
    os.makedirs(os.path.join(ud, "extensions"))
    open(os.path.join(ud, "machines", mname + ".xml"), "w", encoding="utf-8").write(xml)

    rom = a.nextor_rom or NEXTOR_ROMS.get(a.nextor) or os.path.join(share, "extensions",
                                                                    "Nextor-%s.SunriseIDE.ROM" % a.nextor)
    if not os.path.exists(rom):
        log("No existe el kernel Nextor %s: %s (usa --nextor-rom)" % (a.nextor, rom))
        raise SystemExit(2)
    ename = "MMbench_SunriseIDE"
    ext = """<?xml version="1.0" ?>
<!DOCTYPE msxconfig SYSTEM 'msxconfig2.dtd'>
<msxconfig>
  <info><name>MMbench Sunrise IDE</name><manufacturer>MMbench</manufacturer><code/><release_year>2026</release_year>
    <description>Sunrise IDE con Nextor %s y la imagen del banco de pruebas de Multi Mente</description>
    <type>external hard disk</type></info>
  <devices>
    <primary slot="any">
      <secondary slot="any">
        <SunriseIDE id="Sunrise IDE">
          <mem base="0x0000" size="0x10000"/>
          <rom><filename>%s</filename></rom>
          <master><type>IDEHD</type><filename>%s</filename></master>
        </SunriseIDE>
      </secondary>
    </primary>
  </devices>
</msxconfig>
""" % (a.nextor, rom.replace("\\", "/"), img.replace("\\", "/"))
    open(os.path.join(ud, "extensions", ename + ".xml"), "w", encoding="utf-8").write(ext)
    log("  maquina %s | kernel Nextor %s: %s (sha1 %s, %d bytes)" % (mname, a.nextor, rom, sha1(rom)[:12],
                                                                    os.path.getsize(rom)))
    return ud, mname, ename


# ---- 3. openMSX ---------------------------------------------------------------------------------------------------
def indice_en_lista(nombre):
    """Posicion (0-based) del elemento en la lista de MM: MM no ordena, enseña el orden del directorio (mcopy
    los creo en el orden de FICHEROS, la carpeta al final) y la entrada 0 es '..\\' (donde empieza el cursor)."""
    return 1 + orden_roms().index(nombre)


def slug(nombre):
    return re.sub(r"[^A-Za-z0-9]+", "_", _ascii(nombre))[:22].strip("_")


def acciones_libres(texto):
    """--acciones: una accion por linea o separadas por ';' (ver el DSL de probar_mm.tcl); 'dos', 'text', 'log',
    'paso' y 'shot' toman el resto de la linea como un solo argumento. Con @fichero se leen de un fichero."""
    if texto.startswith("@"):
        texto = open(texto[1:], encoding="utf-8").read()
    res = []
    for linea in re.split(r"[;\n]", texto):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        verbo, _, resto = linea.partition(" ")
        resto = resto.strip()
        if verbo in ("dos", "text", "log", "paso", "shot"):
            res.append([verbo, resto] if resto else [verbo])
        else:
            res.append([verbo] + resto.split())
    return res


def _tam(nombre):
    d = dict(FICHEROS)
    d[N_TXT] = 3000
    d[N_COM] = len(hola_com())
    return d.get(nombre, 0)


def _clave_orden(nombre):
    """Clave de la ordenacion por nombre de MM: carpetas primero; despues, nombre de 8 y extension de 3 del 8.3,
    comparados como bytes (CP850), que es como los guarda el disco."""
    sfn = CORTOS[nombre]
    base, _, ext = sfn.partition(".")
    return (0 if nombre in (N_DIR, DIR_COPIA) else 1, base.encode("cp850").ljust(8), ext.encode("cp850").ljust(3))


def orden_ordenado(desc, lista=None):
    """Orden esperado de la lista de MM tras [S]ort por nombre ascendente (o descendente): ['..', ...]."""
    ent = [n for n in (lista or orden_roms())]
    dirs = sorted((n for n in ent if n in (N_DIR, DIR_COPIA)), key=_clave_orden, reverse=desc)
    fich = sorted((n for n in ent if n not in (N_DIR, DIR_COPIA)), key=_clave_orden, reverse=desc)
    return ["..\\"] + dirs + fich


def _describe(nombre):
    if nombre == "..\\":
        return "..\\"
    return "%s = %s (%d bytes)" % (CORTOS.get(nombre, "?"), _ascii(nombre), _tam(nombre))


def acciones_interaccion(a):
    """Escenario 'interaccion' (ver el DSL en probar_mm.tcl): lista, ordenar, marcar, entrar y salir de una carpeta,
    volver 4 veces de un programa, borrar y copiar. Cada paso lleva su captura y, en el log, lo que se espera."""
    A = []
    num = [0]

    def add(*x):
        A.append([str(y) for y in x])

    def shot(nombre):
        num[0] += 1
        add("shot", "%02d_%s" % (num[0], nombre))

    def esperado(prefijo, orden, idxs):
        for i in idxs:
            add("log", "ESPERADO %s idx %d: %s" % (prefijo, i, _describe(orden[i])))

    base = orden_roms()
    ord_a = orden_ordenado(False)
    ord_d = orden_ordenado(True)
    n_aleste1 = "Aleste 1 - Eleven Fighters (1988)(Compile).rom"
    n_aleste1jp = "Aleste 1 - Eleven Fighters (1988)(Compile)(JP).rom"
    n_mg_a1 = "Metal Gear 2 - Solid Snake (1990)(Konami)[a1].rom"
    n_peng = "Penguin Adventure (1986)(Konami).rom"
    n_quarth = "Quarth (1989)(Konami).rom"
    n_musica = FICHEROS[12][0]
    sel_a = sorted(ord_a.index(n) for n in (n_aleste1, n_mg_a1, n_musica, n_quarth))
    sel_d = sorted(ord_d.index(n) for n in ("Zanac-EX.rom", n_peng, "Pac.rom", n_aleste1jp))
    marcas = sorted(ord_d.index(n) for n in (n_peng, "README.TXT", n_mg_a1))

    add("waitprompt")
    add("dos", "cd \\ROMS")
    add("dos", "mm")
    add("waitmm", 60)
    if a.contar_ejecucion:
        add("bp_on")
    # 1. lista inicial
    add("paso", "1_lista")
    add("top")
    add("hash_guarda", "lista0")
    add("log", "ESPERADO lista inicial (orden del directorio): " + " | ".join(
        "%d:%s" % (i + 1, CORTOS[n]) for i, n in enumerate(base)))
    shot("lista_inicial")
    # 2. ordenar (nombre, ascendente y descendente) y File info de varias entradas
    for nombre_paso, desc, orden, sel in (("2_sort_asc", False, ord_a, sel_a), ("2_sort_desc", True, ord_d, sel_d)):
        add("paso", nombre_paso)
        add("top")
        add("key", "s")
        add("wait", 0.7)
        if not desc:
            shot("sort_dialogo")
        add("key", "n")
        add("wait", 0.7)
        if not desc:
            shot("sort_dialogo_arriba_abajo")
        add("key", "d" if desc else "u")
        add("wait", 2)
        add("settle", 1.5)
        add("pos", 0)
        add("log", "ESPERADO orden %s: " % ("descendente" if desc else "ascendente") + " | ".join(
            "%d:%s" % (i, CORTOS.get(n, n)) for i, n in enumerate(orden)))
        shot("lista_" + ("descendente" if desc else "ascendente"))
        for i in sel:
            esperado("tras ordenar " + ("desc" if desc else "asc"), orden, [i])
            add("goto", i)
            add("wait", 0.5)
            add("settle", 1.0)
            shot("%s_info_%02d_%s" % ("desc" if desc else "asc", i, slug(orden[i])))
    # 3. marcar (estamos en orden descendente)
    add("paso", "3_marcas")
    for i in marcas:
        add("log", "MARCA idx %d: %s" % (i, _describe(ord_d[i])))
        add("goto", i)
        add("wait", 0.4)
        add("key", "tab")
        add("wait", 0.5)
    add("settle", 1.0)
    shot("marcadas_3")
    add("goto", marcas[0])
    add("wait", 0.4)
    add("settle", 1.0)
    shot("marcada_cursor_encima")
    for i in marcas:                       # se desmarcan (Borrar/Copiar actuaria sobre las marcadas)
        add("goto", i)
        add("wait", 0.4)
        add("key", "tab")
        add("wait", 0.5)
    add("settle", 1.0)
    shot("desmarcadas")
    # 4. entrar en la carpeta larga y volver
    add("paso", "4_carpeta")
    i_dir = ord_d.index(N_DIR)
    add("goto", i_dir)
    add("wait", 0.4)
    add("settle", 1.0)
    shot("cursor_en_la_carpeta")
    add("key", "return")
    add("wait", 2)
    add("settle", 2.0)
    add("pos", 0)
    add("log", "ESPERADO dentro de %s (orden del directorio): " % _ascii(N_DIR) + " | ".join(
        "%d:%s = %s" % (i + 1, CORTOS_DIR[n], _ascii(n)) for i, (n, _s) in enumerate(FICHEROS_DIR)))
    shot("dentro_carpeta")
    for i in (1, 4, 8):
        n = FICHEROS_DIR[i - 1][0]
        add("log", "ESPERADO dentro idx %d: %s = %s (%d bytes)" % (i, CORTOS_DIR[n], _ascii(n), FICHEROS_DIR[i - 1][1]))
        add("goto", i)
        add("wait", 0.5)
        add("settle", 1.0)
        shot("dentro_info_%02d_%s" % (i, slug(n)))
    add("top")
    add("goto", 0)
    add("key", "return")
    add("wait", 2)
    add("settle", 2.0)
    shot("raiz_de_vuelta")
    # 5. volver de un programa 4 veces seguidas con [X]ecom
    add("paso", "5_programas")
    add("top")
    add("wait", 0.5)
    add("settle", 1.5)
    add("hash_guarda", "raiz")
    shot("raiz_antes_de_programas")
    for k, cmd in enumerate(("ver", "hola", "dir", "hola"), 1):
        add("paso", "5_programa_%d_%s" % (k, cmd))
        add("key", "x")
        add("wait", 1)
        add("text", cmd)
        add("wait", 0.4)
        if k == 1:
            shot("x_dialogo")
        add("key", "return")
        add("waittext", "dos_hit_%d" % k, "Hit", 40)
        add("wait", 0.5)
        shot("x%d_%s_salida_dos" % (k, cmd))
        add("key", "return")
        add("waitmm", 40)
        add("hash_espera", "raiz", 40)
        add("settle", 1.0)
        shot("x%d_%s_vuelta_a_MM" % (k, cmd))
    # 6. borrar y copiar
    add("paso", "6_borrar")
    n_del, n_cp = n_aleste1, "Aleste 2 (1989)(Compile).rom"
    add("top")
    add("log", "ESPERADO borrar idx %d: %s" % (base.index(n_del) + 1, _describe(n_del)))
    add("goto", base.index(n_del) + 1)
    add("wait", 0.5)
    add("settle", 1.0)
    shot("borrar_cursor")
    add("key", "d")
    add("wait", 1)
    shot("borrar_confirmacion")
    add("key", "y")
    add("wait", 3)
    add("settle", 5.0)        # la RC5 borra con pausas largas a mitad: ventana de 5 s para no fiarse de una pausa
    shot("borrar_tras")
    base2 = [n for n in base if n != n_del]
    add("paso", "6_copiar")
    add("top")
    add("log", "ESPERADO copiar idx %d: %s -> \\ROMS\\COPIA" % (base2.index(n_cp) + 1, _describe(n_cp)))
    add("goto", base2.index(n_cp) + 1)
    add("wait", 0.5)
    add("settle", 1.0)
    shot("copiar_cursor")
    add("key", "c")
    add("wait", 1)
    add("text", "\\roms\\copia")
    add("wait", 0.5)
    shot("copiar_destino")
    add("key", "return")
    add("wait", 6)
    add("settle", 5.0)        # copiar tambien va con pausas largas (en la RC5 sigue 'Now Copying file..' a los 6 s)
    shot("copiar_tras")
    add("paso", "6_relista")                # entrar en COPIA y salir fuerza otro listado de \ROMS
    add("bottom", base2.index(DIR_COPIA) + 1)   # COPIA es la ultima entrada: SHIFT+DOWN (ir al final) y no 26 pulsaciones
    add("wait", 0.5)
    add("settle", 1.5)
    shot("cursor_en_COPIA")
    add("key", "return")
    add("wait", 3)
    add("settle", 3.0)
    shot("dentro_COPIA")
    add("top")
    add("goto", 0)
    add("key", "return")
    add("wait", 3)
    add("settle", 3.0)
    shot("raiz_final")
    # 7. salir de MM y mirar el disco desde DOS
    add("paso", "7_salida")
    add("key", "q")
    add("waittext", "mm_sale", "A:\\ROMS>", 20)
    add("dos", "dir copia")
    add("wait", 1.5)
    shot("dos_dir_copia")
    return A


def acciones_cs(a):
    """Escenario 'cs': 'CS MM' desde \\MM (CS.COM adapta MM.COM segun MM.CFG; el manual dice que despues lanza MM:
    si no lo hace, se lanza a mano con 'mm'); despues, con [H], se va a \\ROMS para ver los nombres largos. La
    comparacion de \\MM\\MM.COM antes/despues la hace el script al terminar, leyendo la imagen."""
    A = []
    num = [0]

    def add(*x):
        A.append([str(y) for y in x])

    def shot(nombre):
        num[0] += 1
        add("shot", "%02d_%s" % (num[0], nombre))

    add("waitprompt")
    add("paso", "cs")
    add("dos", "cd \\MM")
    add("dos", "dir mm.com")
    add("wait", 1)
    shot("dos_antes_de_cs")
    add("dos", "cs mm")
    add("wait", 3)
    shot("tras_cs_3s")
    add("waitmm", 8, "sin_mm", "suave")          # si CS lanza MM solo, MM aparece aqui
    add("log", "CS ha lanzado MM por su cuenta")
    add("saltar_a", "mm_ok")
    add("label", "sin_mm")
    add("log", "CS NO ha lanzado MM (vuelve al prompt de DOS): se lanza a mano")
    add("dos", "dir mm.com")
    add("wait", 1)
    shot("dos_tras_cs")
    add("dos", "mm")
    add("waitmm", 90, "fin_cs")
    add("label", "mm_ok")
    add("paso", "mm_tras_cs")
    add("top")
    shot("mm_en_MM_tras_cs")
    add("key", "h")
    add("wait", 1)
    shot("cambiar_ruta_dialogo")
    add("text", "\\roms")
    add("key", "return")
    add("wait", 3)
    add("settle", 3.0)
    add("pos", 0)
    shot("roms_tras_cs")
    for i in (1, 2, 12):
        n = FICHEROS[i - 1][0]
        add("log", "ESPERADO idx %d: %s = %s" % (i, CORTOS.get(n, "?"), _ascii(n)))
        add("goto", i)
        add("wait", 0.5)
        add("settle", 1.0)
        shot("roms_tras_cs_info_%02d" % i)
    add("key", "q")
    add("waitdos", 30)
    add("wait", 1)
    add("label", "fin_cs")
    add("paso", "fin_cs")
    add("dos", "dir \\mm\\mm.com")
    add("wait", 1.5)
    shot("dos_despues_de_cs")
    return A


def acciones_escenario(a):
    if a.escenario == "libre":
        return acciones_libres(a.acciones or "")
    if a.escenario == "interaccion":
        return acciones_interaccion(a)
    if a.escenario == "cs":
        return acciones_cs(a)
    raise SystemExit("escenario sin definir: %s" % a.escenario)


def lanzar(a, W, ud, mname, ename, log):
    log("== 3. openMSX ==")
    tcl_log = os.path.join(W, "guion.log")
    if os.path.exists(tcl_log):
        os.remove(tcl_log)
    if a.info_todos:
        objetivos = [n for n in orden_roms()]
    else:
        objetivos = INFO_DEFECTO
    objetivos = sorted(set(objetivos), key=indice_en_lista)
    prm = os.path.join(W, "params.tcl")
    L = ["# generado por probar_mm.py - no editar",
         "set ::P(log) %s" % tclq(tcl_log.replace("\\", "/")),
         "set ::P(salida) %s" % tclq(a.salida.replace("\\", "/")),
         "set ::P(etiqueta) %s" % tclq(a.etiqueta),
         "set ::P(escenario) %s" % tclq(a.escenario),
         "set ::P(contar) [list %s]" % " ".join(tclq(r) for r in a.contar_ejecucion.split()),
         "set ::P(mmcom) %s" % tclq(mm_com_ruta(a).replace("\\", "/")),
         "set ::P(acciones) {}",
         "set ::P(targets) {}"]
    if a.escenario != "lista":
        objetivos = []
        for acc in acciones_escenario(a):
            L.append("lappend ::P(acciones) [list %s]" % " ".join(tclq(x) for x in acc))
    # {num posicion slug nombre lista_con_parche lista_sin_parche info_con_parche}, todo ASCII (los acentos solo
    # van al manifiesto)
    for i, n in enumerate(objetivos if a.escenario == "lista" else []):
        L.append("lappend ::P(targets) [list %d %d %s %s %s %s %s]" % (
            i + 1, indice_en_lista(n), tclq(slug(n)), tclq(_ascii(n)), tclq(esperado_lista(n)),
            tclq(esperado_lista(n, False)), tclq(esperado_info(n))))
    open(prm, "w", encoding="utf-8").write("\n".join(L) + "\n")
    tcl = os.path.join(AQUI, "probar_mm.tcl")
    shutil.copy(tcl, os.path.join(W, "probar_mm.tcl"))   # copia del guion usado, junto a los resultados
    # PNG viejos fuera (no se puede confundir una captura vieja con una nueva)
    patron = re.compile(r"^(?:%s_)?\d\d_.*\.png$" % re.escape(a.etiqueta) if a.etiqueta else r"^\d\d_.*\.png$")
    for f in os.listdir(a.salida):
        if patron.match(f):
            os.remove(os.path.join(a.salida, f))
    env = dict(os.environ, OPENMSX_USER_DATA=ud)
    cmd = [a.openmsx, "-machine", mname, "-ext", ename, "-script", prm, "-script", tcl]
    log("  $ OPENMSX_USER_DATA=%s" % ud)
    log("  $", subprocess.list2cmdline(cmd))
    otros = subprocess.run(["tasklist", "/FI", "IMAGENAME eq openmsx.exe", "/NH", "/FO", "CSV"], capture_output=True,
                           text=True).stdout.strip()
    if "openmsx.exe" in otros.lower():
        log("  AVISO: ya hay otro openmsx.exe en marcha (no se toca): " + otros.replace("\n", " | "))
    t0 = time.time()
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log("  openMSX pid %d" % p.pid)
    out = b""
    try:
        out, _ = p.communicate(timeout=a.timeout)
        log("  openMSX termino con codigo %s en %.1f s (reales)" % (p.returncode, time.time() - t0))
    except subprocess.TimeoutExpired:
        log("  TIMEOUT de %d s: se mata openMSX (pid %d)" % (a.timeout, p.pid))
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        out, _ = p.communicate()
    finally:
        # no dejar colgada ESTA instancia (solo la suya, por pid) pase lo que pase (Ctrl+C, error...)
        if p.poll() is None:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            log("  openMSX pid %d matado al salir" % p.pid)
    if out:
        log("  stdout/stderr de openMSX:\n    " + out.decode("utf-8", "replace").strip().replace("\n", "\n    "))
    return tcl_log, objetivos, t0


# ---- 4. resultados -----------------------------------------------------------------------------------------------
def resultados(a, W, tcl_log, objetivos, t0, mmfiles, log):
    log("== 4. resultados ==")
    ok = True
    if not os.path.exists(tcl_log):
        log("FALLA: el guion Tcl no escribio su log (%s): openMSX no arranco o no cargo la maquina/extension" % tcl_log)
        return 2
    txt = open(tcl_log, encoding="utf-8", errors="replace").read()
    log("---- registro del guion Tcl (%s) ----" % tcl_log)
    log(txt.rstrip())
    log("---- fin del registro ----")
    checks = re.findall(r"CHECK (\S+) (OK|FALLA)", txt)
    fallos = [c for c, r in checks if r == "FALLA"]
    for marca in ("WATCHDOG", "ERROR en"):
        if marca in txt:
            log("FALLA: el registro del guion contiene '%s'" % marca)
            ok = False
    if "FIN" not in txt:
        log("FALLA: el guion no llego al FIN (openMSX se cerro antes o hubo timeout)")
        ok = False
    log("  checks: %d OK, %d FALLA %s" % (sum(1 for _, r in checks if r == "OK"), len(fallos), fallos or ""))
    patron = re.compile(r"^(?:%s_)?\d\d_.*\.png$" % re.escape(a.etiqueta) if a.etiqueta else r"^\d\d_.*\.png$")
    caps = sorted(f for f in os.listdir(a.salida) if patron.match(f))
    log("  capturas (deben ser posteriores al arranque de openMSX, %s):" % time.strftime("%H:%M:%S", time.localtime(t0)))
    for f in caps:
        p = os.path.join(a.salida, f)
        nuevo = os.path.getmtime(p) >= t0
        log("    %-34s %7d bytes  %s  %s" % (f, os.path.getsize(p), time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p))),
                                              "NUEVA" if nuevo else "ANTIGUA!!"))
        ok &= nuevo and os.path.getsize(p) > 0
    try:
        resumen_escenario(a, W, txt, log)
    except Exception as e:      # el analisis es un extra: que no tire el resultado de los CHECK
        log("FALLO en el analisis posterior: %r" % (e,))
    json.dump({
        "mm_dir": a.mm_dir, "mm_com": mm_com_ruta(a), "mm_com_sha1": sha1(mm_com_ruta(a)), "mm_files": mmfiles,
        "maquina": a.maquina, "mapper_kb": a.mapper_kb, "nextor": a.nextor,
        "ficheros": [{"nombre": n, "len": len(n), "tamano": s, "corto": CORTOS.get(n),
                      "lista_con_parche": esperado_lista(n), "lista_sin_parche": esperado_lista(n, False),
                      "info_con_parche": esperado_info(n)} for n, s in FICHEROS] +
                    [{"nombre": N_DIR, "len": len(N_DIR), "carpeta": True, "corto": CORTOS.get(N_DIR),
                      "lista_con_parche": esperado_lista(N_DIR), "lista_sin_parche": esperado_lista(N_DIR, False),
                      "info_con_parche": esperado_info(N_DIR)}],
        "info_capturados": objetivos, "capturas": caps, "checks": checks,
    }, open(os.path.join(a.salida, "manifiesto.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log("RESULTADO:", "OK" if ok and not fallos else "FALLA")
    return 0 if ok and not fallos else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mm-dir", required=True, help="carpeta con MM.COM, MM.EXE, MM.CFG, MMRET.DAT, MMMCR.DAT...")
    ap.add_argument("--mm-com", help="MM.COM alternativo: se copia a \\MM\\MM.COM en lugar del de --mm-dir")
    ap.add_argument("--salida", required=True, help="carpeta de resultados (capturas, log, imagen)")
    ap.add_argument("--maquina", default="Philips_NMS_8245", help="maquina de openMSX (defecto %(default)s)")
    ap.add_argument("--nextor", default="2.1.1", choices=sorted(NEXTOR_ROMS),
                    help="kernel Nextor del Sunrise IDE (defecto %(default)s, el de openMSX)")
    ap.add_argument("--nextor-rom", help="ROM de Nextor para el Sunrise IDE (anula --nextor)")
    ap.add_argument("--mapper-kb", type=int, default=4096, help="tamaño del mapper en KB (0 = el de la maquina)")
    ap.add_argument("--tamano", default="256M", help="tamaño de la imagen de SD (defecto %(default)s)")
    ap.add_argument("--openmsx", default=OPENMSX_EXE)
    ap.add_argument("--sdmaker", default=SDMAKER)
    ap.add_argument("--timeout", type=int, default=420, help="segundos reales maximos de openMSX")
    ap.add_argument("--info-todos", action="store_true", help="captura File info de TODOS los elementos")
    ap.add_argument("--escenario", default="lista", choices=["lista", "interaccion", "cs", "libre"],
                    help="lista (defecto): lista y File info; interaccion: ordenar, marcar, entrar/salir de carpetas, "
                         "volver de programas, borrar y copiar; cs: CS MM; libre: las --acciones que se den")
    ap.add_argument("--acciones", help="solo con --escenario libre: acciones separadas por ';' o @fichero")
    ap.add_argument("--contar-ejecucion", default="", metavar="RANGOS",
                    help="rangos hex 'ini-fin' separados por espacios (p.ej. '3D60-3DDD 5CD0-5CFF'): cuenta cuantas veces "
                         "se ejecuta una instruccion alli durante el escenario (solo en escenarios con acciones)")
    ap.add_argument("--etiqueta", default="", help="texto para los nombres de las capturas (p.ej. A o B)")
    ap.add_argument("--borrar-imagen", action="store_true", help="borra la imagen de SD (256 MB) al terminar")
    ap.add_argument("--sin-openmsx", action="store_true", help="solo construye la imagen y los XML (para depurar)")
    a = ap.parse_args()
    global AMPLIADO
    AMPLIADO = a.escenario in ("interaccion", "libre")
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except Exception:
            pass
    a.mm_dir = os.path.abspath(a.mm_dir)
    a.mm_com = os.path.abspath(a.mm_com) if a.mm_com else None
    a.salida = os.path.abspath(a.salida)
    a.openmsx = os.path.abspath(a.openmsx)
    os.makedirs(a.salida, exist_ok=True)
    W = os.path.join(a.salida, "work")
    os.makedirs(W, exist_ok=True)
    log = Log(os.path.join(a.salida, "probar_mm.log"))
    log("probar_mm.py %s | mm-dir %s | salida %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), a.mm_dir, a.salida))
    for f, nombre in ((a.openmsx, "openmsx.exe"), (a.sdmaker, "MSXsdmaker.py"), (a.mm_dir, "--mm-dir"),
                      (os.path.join(a.mm_dir, "MM.COM"), "MM.COM de --mm-dir"),
                      (os.path.join(a.mm_dir, "MM.EXE"), "MM.EXE de --mm-dir")):
        if not os.path.exists(f):
            log("FALTA %s: %s" % (nombre, f))
            return 2
    if a.mm_com and not os.path.exists(a.mm_com):
        log("FALTA --mm-com: %s" % a.mm_com)
        return 2
    log("MM.COM que se copia a \\MM: %s sha1 %s (%d bytes)" % (mm_com_ruta(a), sha1(mm_com_ruta(a)),
                                                               os.path.getsize(mm_com_ruta(a))))
    img, mmfiles = construir_imagen(a, W, log)
    ud, mname, ename = preparar_openmsx(a, W, img, log)
    if a.sin_openmsx:
        log("--sin-openmsx: OPENMSX_USER_DATA=%s  -machine %s -ext %s" % (ud, mname, ename))
        return 0
    tcl_log, objetivos, t0 = lanzar(a, W, ud, mname, ename, log)
    rc = resultados(a, W, tcl_log, objetivos, t0, mmfiles, log)
    if a.borrar_imagen and os.path.exists(img):
        os.remove(img)
        log("imagen borrada (--borrar-imagen)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
