"""hacer_parche.py — de los SR.COM originales de SofaRun a todo lo que se reparte.

Uso:  python tools/hacer_parche.py

Necesita los originales en original/ (no van en el repositorio) y pasmo (http://pasmo.speccy.org/: en el PATH o, en
Windows, dentro de WSL):
  original/SR.COM              SofaRun 8.1, 34.929 bytes, sha1 2f13bb73...        -> SR_LFN.ips
  original/SR_2025-11.COM      SofaRun 8.1 de la web (2025-11), 35.115 bytes, sha1 2d95ca7d...  -> SR_LFN_2025-11.ips
Para cada uno:
1. Lo parchea con src/parchear.py (ensambla src/srlfn.asm).
2. Saca de la diferencia el parche IPS: SOLO los bytes nuevos, ni un byte del original.
3. Lo reaplica sobre el original y comprueba que sale el mismo fichero.
Y escribe aplicar.py y aplicar.html (con todos los parches dentro).
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASES = [
    dict(nombre="8.1", sha1="2f13bb7303d4cc4f9c0a54c084907e320777be22", ruta="original/SR.COM", ips="SR_LFN.ips"),
    dict(nombre="8.1 (2025-11)", sha1="2d95ca7d366f7ac87b299102e1b148692d934706", ruta="original/SR_2025-11.COM",
         ips="SR_LFN_2025-11.ips"),
]


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def hacer_ips(orig, nuevo):
    """IPS con solo los bytes que cambian (y todo lo que se anade al final)."""
    assert len(nuevo) >= len(orig)
    trozos = []
    i = 0
    while i < len(nuevo):
        if i < len(orig) and orig[i] == nuevo[i]:
            i += 1
            continue
        j = i
        while j < len(nuevo) and (j >= len(orig) or orig[j] != nuevo[j]) and j - i < 0xFFFF:
            j += 1
        trozos.append((i, nuevo[i:j]))
        i = j
    out = bytearray(b"PATCH")
    for off, datos in trozos:
        assert off != 0x454F46, "el desplazamiento coincide con la marca EOF del IPS"
        out += off.to_bytes(3, "big") + len(datos).to_bytes(2, "big") + datos
    out += b"EOF"
    return bytes(out), trozos


def aplicar_ips(datos, ips):
    out = bytearray(datos)
    i = 5
    while ips[i:i + 3] != b"EOF":
        off = int.from_bytes(ips[i:i + 3], "big")
        n = int.from_bytes(ips[i + 3:i + 5], "big")
        i += 5
        assert n, "RLE no soportado"
        if off > len(out):
            out.extend(bytes(off - len(out)))
        out[off:off + n] = ips[i:i + n]
        i += n
    return bytes(out)


def plantilla(nombre, **datos):
    texto = open(os.path.join(RAIZ, "tools", nombre), encoding="utf-8").read()
    for k, v in datos.items():
        texto = texto.replace("__%s__" % k, v)
    sobran = re.findall(r"__[A-Z0-9_]+__", texto)
    assert not sobran, "%s: marcas sin rellenar %s" % (nombre, sobran)
    return texto


def hacer_base(base):
    ruta = os.path.join(RAIZ, base["ruta"])
    if not os.path.exists(ruta):
        sys.exit("falta %s (el SR.COM %s original; no va en el repositorio)" % (base["ruta"], base["nombre"]))
    orig = open(ruta, "rb").read()
    if sha1(orig) != base["sha1"]:
        sys.exit("%s no es el SR.COM %s original (sha1 %s)" % (ruta, base["nombre"], base["sha1"]))
    with tempfile.TemporaryDirectory() as tmp:
        nuevo_ruta = os.path.join(tmp, "SR_LFN.COM")
        subprocess.run([sys.executable, os.path.join(RAIZ, "src", "parchear.py"), ruta, nuevo_ruta], check=True)
        nuevo = open(nuevo_ruta, "rb").read()
    ips, trozos = hacer_ips(orig, nuevo)
    assert aplicar_ips(orig, ips) == nuevo, "el IPS no reproduce el SR.COM parcheado"
    for off, datos in trozos:           # nada del original dentro del parche
        for k, b in enumerate(datos):
            assert off + k >= len(orig) or orig[off + k] != b
    open(os.path.join(RAIZ, base["ips"]), "wb").write(ips)
    print("%s: %s %d bytes en %d trozos (%d bytes nuevos o cambiados de %d)"
          % (base["nombre"], base["ips"], len(ips), len(trozos), sum(len(d) for _, d in trozos), len(nuevo)))
    print("   original  %d bytes sha1 %s" % (len(orig), base["sha1"]))
    print("   parcheado %d bytes sha1 %s" % (len(nuevo), sha1(nuevo)))
    return dict(nombre=base["nombre"], original=base["sha1"], tam_original=len(orig), parcheado=sha1(nuevo),
                tam_parcheado=len(nuevo), ips=base64.b64encode(ips).decode(), fichero_ips=base["ips"])


def main():
    hechas = [hacer_base(b) for b in BASES]
    por_sha = {h["original"]: h for h in hechas}
    lista = "; ".join("SofaRun %s (%d bytes, sha1 %s)" % (h["nombre"], h["tam_original"], h["original"]) for h in hechas)
    datos = dict(BASES=json.dumps(por_sha, indent=2), LISTA=lista)
    for plant, destino in (("aplicar.plantilla.py", "aplicar.py"), ("aplicar.plantilla.html", "aplicar.html")):
        with open(os.path.join(RAIZ, destino), "w", encoding="utf-8", newline="\n") as f:
            f.write(plantilla(plant, **datos))


if __name__ == "__main__":
    main()
