#!/usr/bin/env python3
"""SR_LFN - long file names for SofaRun / nombres largos para SofaRun.

  python aplicar.py SR.COM               ->  SR_LFN.COM, next to SR.COM / al lado de SR.COM
  python aplicar.py SR.COM -o OUT.COM

Hace falta el SR.COM ORIGINAL de SofaRun, sin tocar / You need the ORIGINAL, untouched SofaRun SR.COM:
  SofaRun 8.1 (34929 bytes, sha1 2f13bb7303d4cc4f9c0a54c084907e320777be22); SofaRun 8.1 (2025-11) (35115 bytes, sha1 2d95ca7d366f7ac87b299102e1b148692d934706)
No hace falta nada mas que Python 3 / Nothing else is needed but Python 3.

Fichero generado por tools/hacer_parche.py: no lo edites a mano / generated file, do not edit.
"""
import base64
import hashlib
import locale
import os
import sys

# sha1 del SR.COM original -> el parche (IPS) y lo que sale
BASES = {
  "2f13bb7303d4cc4f9c0a54c084907e320777be22": {
    "nombre": "8.1",
    "original": "2f13bb7303d4cc4f9c0a54c084907e320777be22",
    "tam_original": 34929,
    "parcheado": "c2f56896a09bf856ec21ae842752cb8925aede71",
    "tam_parcheado": 36242,
    "ips": "UEFUQ0gAC9IABMMWiwAADVgAA806igAOhgADzeWJAD1UAAPNxIoAXpUAApWOAF6eAAKVjgBeoQAClY4AXr4AApeOAIhxBSEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOHFOnGJtyAD/eXp5c33ieHV6SpyiXy1KBrdbvLdZvMpKSkpKSntW3KJGVRdAT8ACX63wCF0iRF1iTYgAT4A7bD95eERdIkGDX63KAUSIxMQ9xF0icn1xdXd5f3lOnGJtyhyKht9fLUoaykpKSkpKSLCiQEQAAnlzcNf0bftUjhU7VvCic3WWyJyiVRdEzYA7UvCiQvtsM3DXxFYA7ftUjgmEUgDzdZbIsSJIsaJEQACGSLIiRFAABkiyonNPovtW8SJzbRcGA3tW3KJIQAAInKJzbRc/eHd4dHB8SpRdMnF1eU67H3+UD4AIAE8MnGJIfKKBgleI1YjTiM6cYm3KAFOI3kSEO7h0cE67H3JhQ8MP5UPBgehDww/zQ8NQf8PEkY4EBRQfRAUIEsQE0+dEhRQ9cXl3eX95dXtW3KJerMoCSEAACJyic20XNH94d3h4cHx1SpVdMPWDA4ZzQUAMsyJIR19ftZBIcyJvsDtW8iJLgAOMc0FALfAKsiJIyMjfjLNiREEABleI1btU86JEQUAGV4jVu1T0IntW8aJDhrNBQDNkosRgAAOGsMFAD7/MtqJIQAAOiB9tygW3SrIiRFMjAYQDkDNBQC3wN1uE91mFHy1IBwq0Iki1okhAAAi2IkqzokGBMs8yx0Q+iLUiRgy6yrIia8Ofs0FALfAKsiJEQQAGRHWiQEEAO2wXiNWI34jy14oAxEAAO1T0olvJgAi1Ik6zIkGAe1b1okq2IkOc80FALfAIdaJBgQ0IAMjEPrdKsaJBhDFzU6MwcgRIADdGRDzKtSJKyLUiXy1IMQq0ol8tSCLyS4A3X4At8j+5Sge3X4L/g8oHuYIIBM62om3IA3d5eHN6owh24m+zGSNPv8y2om3yd1+AMt3KAbdfg0y24ndfg0h24m+IOPdfgDLdygT5h8o2P4VMNQy2onN2ow2AN1+AOYfKMUh2om+IL81fs3ajOshF40GDcXlTgYA3eXhCU4jfs3zjBIT4SPBEOr2AclvJgBNRCkJKSkJ7UvKiQnJBguvD4YjEPvJtyAYebfI/iA4F/5/2NbAOBAhJI2FbzABJH7JPCADeTzIPj/JAQMFBwkOEBIUFhgcHkFBQUFBQUFDRUVFRUlJSUlETk9PT09PeE9VVVVVWVRzYWFhYWFhYWNlZWVlaWlpaWRub29vb28vb3V1dXV5dHndfgD+Lsjd5eERtIkGCH7+ICgFEhMjEPbd5eEBCAAJfv4gKBA+LhITBgN+/iAoBRITIxD2rxLdfgvmECgCPn0y3IkqG318tcgrIt+JIQAAIt2J7VvdiSrfibftUtgq3YntW9+JGcs8yx0i4YnNHo4i44kRDQAZfv59OAT+gDgBr0c63Im4KAl4IdyJvjggGBUq44kRtIl+Txq5IAe3KCojExjzOAkq4YkjIt2JGKQq4Yl8tcgrIt+JGJhUXSkpKSnrKRntW1V0Gckq4YkpKSkpKSntW3KJGevVKsqJAQAAfrcoBCMDGPgqyol4sSg+eLcgF3n+QDASxe2wwT4/kSgkRz4gEhMQ+hgbxQEsAO2wBgM+LhITEPrBKsqJCQEQALftQu2w4RE/ABk2AcnhyUVPRg==",
    "fichero_ips": "SR_LFN.ips"
  },
  "2d95ca7d366f7ac87b299102e1b148692d934706": {
    "nombre": "8.1 (2025-11)",
    "original": "2d95ca7d366f7ac87b299102e1b148692d934706",
    "tam_original": 35115,
    "parcheado": "0b3ff3bec96d550ce4902ea3830c95ace5499199",
    "tam_parcheado": 36428,
    "ips": "UEFUQ0gAC9IABMPQiwAADVgAA830igAOhgADzZ+KAD1dAAPNfosAX08AAk+PAF9YAAJPjwBfWwACT48AX3gAAlGPAIkrBSEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOHFOiuKtyAD/eXp5c2xiuHV6Sosiny1KBrdbvLdZvMpKSkpKSntWyyKGVRdAT8ACX63wCEuihEvijYgAT4A7bD95eERLooGDX63KAUSIxMQ9xEuisn1xdXd5f3lOiuKtyhyKtV9fLUoaykpKSkpKSJ8igEQAAnlzX1g0bftUjhU7Vt8is2QXCIsilRdEzYA7Ut8igvtsM19YBFYA7ftUjgmEUgDzZBcIn6KIoCKEQACGSKCihFAABkihIrN+IvtW36KzW5dGA3tWyyKIQAAIiyKzW5d/eHd4dHB8SoLdcnF1eU6pn7+UD4AIAE8MiuKIayLBgleI1YjTiM6K4q3KAFOI3kSEO7h0cE6pn7JhQ8MP5UPBgehDww/zQ8NQf8PEkY4EBRQfRAUIEsQE0+dEhRQ9cXl3eX95dXtWyyKerMoCSEAACIsis1uXdH94d3h4cHx1SoPdcPWDA4ZzQUAMoaKIdd9ftZBIYaKvsDtW4KKLgAOMc0FALfAKoKKIyMjfjKHihEEABleI1btU4iKEQUAGV4jVu1TiortW4CKDhrNBQDNTIwRgAAOGsMFAD7/MpSKIQAAOtp9tygW3SqCihEGjQYQDkDNBQC3wN1uE91mFHy1IBwqiooikIohAAAikooqiIoGBMs8yx0Q+iKOihgy6yqCiq8Ofs0FALfAKoKKEQQAGRGQigEEAO2wXiNWI34jy14oAxEAAO1TjIpvJgAijoo6hooGAe1bkIoqkooOc80FALfAIZCKBgQ0IAMjEPrdKoCKBhDFzQiNwcgRIADdGRDzKo6KKyKOiny1IMQqjIp8tSCLyS4A3X4At8j+5Sge3X4L/g8oHuYIIBM6lIq3IA3d5eHNpI0hlYq+zB6OPv8ylIq3yd1+AMt3KAbdfg0ylYrdfg0hlYq+IOPdfgDLdygT5h8o2P4VMNQylIrNlI02AN1+AOYfKMUhlIq+IL81fs2Ujesh0Y0GDcXlTgYA3eXhCU4jfs2tjRIT4SPBEOr2AclvJgBNRCkJKSkJ7UuEignJBguvD4YjEPvJtyAYebfI/iA4F/5/2NbAOBAh3o2FbzABJH7JPCADeTzIPj/JAQMFBwkOEBIUFhgcHkFBQUFBQUFDRUVFRUlJSUlETk9PT09PeE9VVVVVWVRzYWFhYWFhYWNlZWVlaWlpaWRub29vb28vb3V1dXV5dHndfgD+Lsjd5eERbooGCH7+ICgFEhMjEPbd5eEBCAAJfv4gKBA+LhITBgN+/iAoBRITIxD2rxLdfgvmECgCPn0ylooq1X18tcgrIpmKIQAAIpeK7VuXiiqZirftUtgql4rtW5mKGcs8yx0im4rN2I4inYoRDQAZfv59OAT+gDgBr0c6loq4KAl4IZaKvjggGBUqnYoRbop+Txq5IAe3KCojExjzOAkqm4ojIpeKGKQqm4p8tcgrIpmKGJhUXSkpKSnrKRntWw91Gckqm4opKSkpKSntWyyKGevVKoSKAQAAfrcoBCMDGPgqhIp4sSg+eLcgF3n+QDASxe2wwT4/kSgkRz4gEhMQ+hgbxQEsAO2wBgM+LhITEPrBKoSKCQEQALftQu2w4RE/ABk2AcnhyUVPRg==",
    "fichero_ips": "SR_LFN_2025-11.ips"
  }
}

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
