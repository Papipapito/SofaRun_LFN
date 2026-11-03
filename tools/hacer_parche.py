"""hacer_parche.py — del SR.COM original de SofaRun 8.1 a todo lo que se reparte.

Uso:  python tools/hacer_parche.py

Necesita original/SR.COM (SofaRun 8.1, 34.929 bytes, sha1 2f13bb73...: no va en el repositorio) y pasmo
(http://pasmo.speccy.org/: en el PATH o, en Windows, dentro de WSL).
1. Parchea con src/parchear.py (ensambla src/srlfn.asm).
2. Saca de la diferencia el IPS (SR_LFN.ips): SOLO los bytes nuevos, ni un byte del original.
3. Lo reaplica sobre el original y comprueba que sale el mismo fichero.
Y escribe aplicar.py y aplicar.html (con el parche dentro).
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
ORIGINAL = "original/SR.COM"
SHA1 = "2f13bb7303d4cc4f9c0a54c084907e320777be22"


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


def main():
    ruta = os.path.join(RAIZ, ORIGINAL)
    orig = open(ruta, "rb").read()
    if sha1(orig) != SHA1:
        sys.exit("%s no es el SR.COM de SofaRun 8.1 original (sha1 %s)" % (ruta, SHA1))
    with tempfile.TemporaryDirectory() as tmp:
        nuevo_ruta = os.path.join(tmp, "SR_LFN.COM")
        subprocess.run([sys.executable, os.path.join(RAIZ, "src", "parchear.py"), ruta, nuevo_ruta], check=True)
        nuevo = open(nuevo_ruta, "rb").read()
    ips, trozos = hacer_ips(orig, nuevo)
    assert aplicar_ips(orig, ips) == nuevo, "el IPS no reproduce el SR.COM parcheado"
    for off, datos in trozos:           # nada del original dentro del parche
        for k, b in enumerate(datos):
            assert off + k >= len(orig) or orig[off + k] != b
    open(os.path.join(RAIZ, "SR_LFN.ips"), "wb").write(ips)
    print("SR_LFN.ips: %d bytes en %d trozos (%d bytes nuevos o cambiados de %d)"
          % (len(ips), len(trozos), sum(len(d) for _, d in trozos), len(nuevo)))
    print("   original  %d bytes sha1 %s" % (len(orig), SHA1))
    print("   parcheado %d bytes sha1 %s" % (len(nuevo), sha1(nuevo)))
    base = dict(nombre="8.1", original=SHA1, tam_original=len(orig), parcheado=sha1(nuevo), tam_parcheado=len(nuevo),
                ips=base64.b64encode(ips).decode())
    datos = dict(BASE=json.dumps(base, indent=2), LISTA="%s: %d bytes, sha1 %s" % ("SofaRun 8.1", len(orig), SHA1))
    for plant, destino in (("aplicar.plantilla.py", "aplicar.py"), ("aplicar.plantilla.html", "aplicar.html")):
        with open(os.path.join(RAIZ, destino), "w", encoding="utf-8", newline="\n") as f:
            f.write(plantilla(plant, **datos))


if __name__ == "__main__":
    main()
