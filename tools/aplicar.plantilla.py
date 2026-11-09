#!/usr/bin/env python3
"""SR_LFN - long file names for SofaRun / nombres largos para SofaRun.

  python aplicar.py SR.COM               ->  SR_LFN.COM, next to SR.COM / al lado de SR.COM
  python aplicar.py SR.COM -o OUT.COM

Hace falta el SR.COM ORIGINAL de SofaRun, sin tocar / You need the ORIGINAL, untouched SofaRun SR.COM:
  __LISTA__
No hace falta nada mas que Python 3 / Nothing else is needed but Python 3.

Fichero generado por tools/hacer_parche.py: no lo edites a mano / generated file, do not edit.
"""
import base64
import hashlib
import locale
import os
import sys

# sha1 del SR.COM original -> el parche (IPS) y lo que sale
BASES = __BASES__

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass
ES = (os.environ.get("SRLFN_LANG") or locale.getlocale()[0] or os.environ.get("LANG", "")).lower().startswith(("es", "spanish"))


def T(es, en):
    return es if ES else en


def aplicar_ips(datos, ips):
    if ips[:5] != b"PATCH":
        raise ValueError("not an IPS patch")
    out = bytearray(datos)
    i = 5
    while ips[i:i + 3] != b"EOF":
        off = int.from_bytes(ips[i:i + 3], "big")
        n = int.from_bytes(ips[i + 3:i + 5], "big")
        i += 5
        if n:
            dato = ips[i:i + n]
            i += n
        else:  # registro RLE / RLE record
            n = int.from_bytes(ips[i:i + 2], "big")
            dato = ips[i + 2:i + 3] * n
            i += 3
        if off > len(out):
            out.extend(bytes(off - len(out)))
        out[off:off + n] = dato
    return bytes(out)


def procesar(datos):
    """Devuelve (estado, bytes nuevos, base): estado 'original' (con los bytes nuevos), 'parcheado' u 'otro'."""
    sha = hashlib.sha1(datos).hexdigest()
    base = BASES.get(sha)
    if base is None:
        ya = next((b for b in BASES.values() if b["parcheado"] == sha), None)
        return ("parcheado" if ya else "otro"), None, ya
    nuevo = aplicar_ips(datos, base64.b64decode(base["ips"]))
    if hashlib.sha1(nuevo).hexdigest() != base["parcheado"] or len(nuevo) != base["tam_parcheado"]:
        raise RuntimeError(T("Error interno: el resultado no es el esperado.", "Internal error: unexpected result."))
    return "original", nuevo, base


def main(argv):
    salida = None
    if "-o" in argv:
        k = argv.index("-o")
        if k + 1 >= len(argv):
            sys.exit(__doc__)
        salida = argv[k + 1]
        del argv[k:k + 2]
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        sys.exit(__doc__)
    entrada = argv[0]
    try:
        datos = open(entrada, "rb").read()
    except OSError as e:
        sys.exit(T("No puedo leer %s: %s", "Cannot read %s: %s") % (entrada, e))
    estado, nuevo, base = procesar(datos)
    if estado == "parcheado":
        sys.exit(T("%s ya lleva el parche de nombres largos.", "%s already has the long-name patch.") % entrada)
    if estado == "otro":
        versiones = "\n    ".join("SofaRun %s: %d bytes, sha1 %s" % (b["nombre"], b["tam_original"], s) for s, b in BASES.items())
        sys.exit(T(
            "%s no es un SR.COM original que conozca.\n  sha1 de tu fichero: %s\n  Valen:\n    %s\n"
            "El parche solo vale para esas versiones exactas, sin tocar.",
            "%s is not an original SR.COM I know.\n  your file's sha1: %s\n  These fit:\n    %s\n"
            "The patch only fits those exact versions, untouched.") % (entrada, hashlib.sha1(datos).hexdigest(), versiones))
    if salida is None:
        salida = os.path.join(os.path.dirname(os.path.abspath(entrada)), "SR_LFN.COM")
    if os.path.abspath(salida) == os.path.abspath(entrada):
        sys.exit(T("No sobrescribo el original: usa otro nombre con -o.", "Not overwriting the original: use another name with -o."))
    with open(salida, "wb") as f:
        f.write(nuevo)
    print(T("SofaRun %s: hecho. %s (%d bytes, sha1 %s)", "SofaRun %s: done. %s (%d bytes, sha1 %s)")
          % (base["nombre"], salida, len(nuevo), base["parcheado"]))
    print(T("Copialo a la tarjeta como SR.COM, en la carpeta de SofaRun (junto a SR.INI).",
            "Copy it to the card as SR.COM, in the SofaRun folder (next to SR.INI)."))


if __name__ == "__main__":
    main(sys.argv[1:])
