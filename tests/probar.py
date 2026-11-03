"""probar.py — pruebas de los aplicadores (aplicar.py, aplicar.html y SR_LFN.ips).

Uso:  python tests/probar.py

Necesita original/SR.COM (SofaRun 8.1; no va en el repo). Para el aplicador de la pagina web, node.
No necesita pasmo: prueba lo que se reparte, no la compilacion (eso lo hace tools/hacer_parche.py).
"""
import base64
import hashlib
import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHA_ORIG = "2f13bb7303d4cc4f9c0a54c084907e320777be22"
fallos = []


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def comprueba(nombre, cond, detalle=""):
    print(("  ok    " if cond else "  FALLA ") + nombre + ("" if cond else "  " + str(detalle)))
    if not cond:
        fallos.append(nombre)


def aplicar(*args):
    return subprocess.run([sys.executable, os.path.join(RAIZ, "aplicar.py"), *args], capture_output=True, text=True,
                          env={**os.environ, "SRLFN_LANG": "en", "PYTHONIOENCODING": "utf-8"})


def main():
    ruta = os.path.join(RAIZ, "original", "SR.COM")
    if not os.path.exists(ruta):
        sys.exit("Falta original/SR.COM (SofaRun 8.1; no va en el repo).")
    orig = open(ruta, "rb").read()
    assert sha1(orig) == SHA_ORIG, "original/SR.COM no es el SR.COM de SofaRun 8.1"
    sys.path.insert(0, RAIZ)
    mod = importlib.import_module("aplicar")
    ips = open(os.path.join(RAIZ, "SR_LFN.ips"), "rb").read()
    parcheado = mod.aplicar_ips(orig, ips)
    sha_nuevo = mod.BASE["parcheado"]
    node = shutil.which("node")
    with tempfile.TemporaryDirectory() as tmp:
        d = lambda *f: os.path.join(tmp, *f)
        print("SR_LFN.ips")
        comprueba("IPS sobre el original da el sha1 esperado", sha1(parcheado) == sha_nuevo)
        comprueba("el IPS es el que lleva aplicar.py", base64.b64decode(mod.BASE["ips"]) == ips)
        comprueba("el IPS pesa mucho menos que el programa (solo bytes nuevos)", len(ips) < len(orig) // 10, len(ips))

        print("aplicar.py")
        open(d("SR.COM"), "wb").write(orig)
        r = aplicar(d("SR.COM"))
        nuevo = open(d("SR_LFN.COM"), "rb").read() if os.path.exists(d("SR_LFN.COM")) else b""
        comprueba("original -> SR_LFN.COM al lado, codigo 0", r.returncode == 0 and sha1(nuevo) == sha_nuevo, r.stderr)
        comprueba("el original no se toca", open(d("SR.COM"), "rb").read() == orig)
        r = aplicar(d("SR_LFN.COM"), "-o", d("otro.com"))
        comprueba("un SR.COM ya parcheado se rechaza", r.returncode != 0 and "already" in r.stderr
                  and not os.path.exists(d("otro.com")), r.stderr)
        malo = bytearray(orig)
        malo[0x500] ^= 1
        open(d("malo.com"), "wb").write(malo)
        r = aplicar(d("malo.com"), "-o", d("malo_out.com"))
        comprueba("un byte distinto se rechaza y no escribe nada",
                  r.returncode != 0 and "sha1" in r.stderr and not os.path.exists(d("malo_out.com")), r.stderr)
        open(d("corto.com"), "wb").write(orig[:1000])
        comprueba("un fichero truncado se rechaza", aplicar(d("corto.com")).returncode != 0)
        r = aplicar(d("SR.COM"), "-o", d("SR.COM"))
        comprueba("no sobrescribe el original", r.returncode != 0 and open(d("SR.COM"), "rb").read() == orig, r.stderr)
        r = aplicar("-o", d("x.com"), d("SR.COM"))
        comprueba("-o antes del fichero", r.returncode == 0 and os.path.exists(d("x.com")), r.stderr)
        comprueba("fichero inexistente", aplicar(d("no_existe.com")).returncode != 0)
        comprueba("sin argumentos: ayuda", "python aplicar.py" in aplicar().stderr)

        print("aplicar.html (nucleo en node)")
        if not node:
            print("  (sin node: se salta)")
        else:
            html = open(os.path.join(RAIZ, "aplicar.html"), encoding="utf-8").read()
            js = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
            open(d("nucleo.js"), "w", encoding="utf-8").write(js + r"""
;(function () {
  const fs = require("fs"), crypto = require("crypto");
  const sal = [], ok = (n, c) => sal.push((c ? "  ok    " : "  FALLA ") + n);
  const hex = b => crypto.createHash("sha1").update(b).digest("hex");
  for (const n of [0, 1, 55, 56, 63, 64, 65, 119, 120, 1000, 34929, 100003]) {
    const b = crypto.randomBytes(n);
    ok("sha1 de " + n + " bytes", sha1(new Uint8Array(b)) === hex(b));
  }
  const orig = new Uint8Array(fs.readFileSync(process.argv[2])), py = new Uint8Array(fs.readFileSync(process.argv[3]));
  const r = procesar(orig);
  ok("original -> parcheado, identico byte a byte al de aplicar.py",
     r.estado === "original" && Buffer.compare(Buffer.from(r.salida), Buffer.from(py)) === 0);
  ok("parcheado -> ya esta", procesar(py).estado === "parcheado" && procesar(py).salida === null);
  const malo = orig.slice(); malo[0x500] ^= 1;
  ok("un byte distinto -> otro", procesar(malo).estado === "otro");
  ok("vacio -> otro", procesar(new Uint8Array(0)).estado === "otro");
  console.log(sal.join("\n")); process.exit(sal.some(s => s.includes("FALLA")) ? 1 : 0);
})();
""")
            r = subprocess.run([node, d("nucleo.js"), ruta, d("SR_LFN.COM")], capture_output=True, text=True)
            print(r.stdout.rstrip())
            if r.returncode:
                fallos.append("node")
                print(r.stderr)

    print("\n%s" % ("TODO BIEN" if not fallos else "FALLAN: " + ", ".join(fallos)))
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
