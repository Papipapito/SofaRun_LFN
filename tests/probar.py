"""probar.py — pruebas de los aplicadores (aplicar.py, aplicar.html y los .ips).

Uso:  python tests/probar.py

Necesita los SR.COM originales en original/ (no van en el repo): SR.COM (SofaRun 8.1) y/o SR_2025-11.COM (el de la web,
de 2025-11); se prueba cada uno que este. Para el aplicador de la pagina web, node.
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
# nombre, fichero original, sha1 del original, fichero IPS
BASES = [
    ("8.1", "SR.COM", "2f13bb7303d4cc4f9c0a54c084907e320777be22", "SR_LFN.ips"),
    ("8.1 (2025-11)", "SR_2025-11.COM", "2d95ca7d366f7ac87b299102e1b148692d934706", "SR_LFN_2025-11.ips"),
]
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


def prueba_base(nombre, orig, sha_orig, ips_nombre, tmp, node):
    print("== SofaRun %s" % nombre)
    d = os.path.join(tmp, re.sub(r"\W", "_", nombre))
    os.makedirs(d)
    p = lambda *f: os.path.join(d, *f)
    sys.path.insert(0, RAIZ)
    mod = importlib.import_module("aplicar")
    base = mod.BASES[sha_orig]
    sha_nuevo = base["parcheado"]
    ips = open(os.path.join(RAIZ, ips_nombre), "rb").read()
    print("%s (IPS)" % ips_nombre)
    comprueba("IPS sobre el original da el sha1 esperado", sha1(mod.aplicar_ips(orig, ips)) == sha_nuevo)
    comprueba("el IPS es el que lleva aplicar.py", base64.b64decode(base["ips"]) == ips)
    comprueba("el IPS pesa mucho menos que el programa (solo bytes nuevos)", len(ips) < len(orig) // 10, len(ips))

    print("aplicar.py")
    open(p("SR.COM"), "wb").write(orig)
    r = aplicar(p("SR.COM"))
    nuevo = open(p("SR_LFN.COM"), "rb").read() if os.path.exists(p("SR_LFN.COM")) else b""
    comprueba("original -> SR_LFN.COM al lado, codigo 0", r.returncode == 0 and sha1(nuevo) == sha_nuevo, r.stderr)
    comprueba("dice la version", nombre in r.stdout, r.stdout)
    comprueba("el original no se toca", open(p("SR.COM"), "rb").read() == orig)
    r = aplicar(p("SR_LFN.COM"), "-o", p("otro.com"))
    comprueba("un SR.COM ya parcheado se rechaza", r.returncode != 0 and "already" in r.stderr
              and not os.path.exists(p("otro.com")), r.stderr)
    malo = bytearray(orig)
    malo[0x500] ^= 1
    open(p("malo.com"), "wb").write(malo)
    r = aplicar(p("malo.com"), "-o", p("malo_out.com"))
    comprueba("un byte distinto se rechaza, lista las versiones y no escribe nada",
              r.returncode != 0 and "sha1" in r.stderr and "2025-11" in r.stderr and not os.path.exists(p("malo_out.com")), r.stderr)
    open(p("corto.com"), "wb").write(orig[:1000])
    comprueba("un fichero truncado se rechaza", aplicar(p("corto.com")).returncode != 0)
    r = aplicar(p("SR.COM"), "-o", p("SR.COM"))
    comprueba("no sobrescribe el original", r.returncode != 0 and open(p("SR.COM"), "rb").read() == orig, r.stderr)
    r = aplicar("-o", p("x.com"), p("SR.COM"))
    comprueba("-o antes del fichero", r.returncode == 0 and os.path.exists(p("x.com")), r.stderr)

    print("aplicar.html (nucleo en node)")
    if not node:
        print("  (sin node: se salta)")
        return
    html = open(os.path.join(RAIZ, "aplicar.html"), encoding="utf-8").read()
    js = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    open(p("nucleo.js"), "w", encoding="utf-8").write(js + r"""
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
  const ya = procesar(py);
  ok("parcheado -> ya esta (con su version)", ya.estado === "parcheado" && ya.salida === null && ya.base.original === r.base.original);
  const malo = orig.slice(); malo[0x500] ^= 1;
  ok("un byte distinto -> otro", procesar(malo).estado === "otro");
  ok("vacio -> otro", procesar(new Uint8Array(0)).estado === "otro");
  console.log(sal.join("\n")); process.exit(sal.some(s => s.includes("FALLA")) ? 1 : 0);
})();
""")
    r = subprocess.run([node, p("nucleo.js"), p("SR.COM"), p("SR_LFN.COM")], capture_output=True, text=True)
    print(re.sub(r"(?m)^  ok    sha1 de .*\n", "", r.stdout).rstrip())
    if r.returncode:
        fallos.append("node " + nombre)
        print(r.stderr)


def main():
    hechas = 0
    node = shutil.which("node")
    with tempfile.TemporaryDirectory() as tmp:
        for nombre, fichero, sha_orig, ips_nombre in BASES:
            ruta = os.path.join(RAIZ, "original", fichero)
            if not os.path.exists(ruta):
                print("== SofaRun %s: falta original/%s, se salta" % (nombre, fichero))
                continue
            orig = open(ruta, "rb").read()
            assert sha1(orig) == sha_orig, "%s no es el SR.COM %s original" % (ruta, nombre)
            prueba_base(nombre, orig, sha_orig, ips_nombre, tmp, node)
            hechas += 1
        if not hechas:
            sys.exit("Faltan los SR.COM originales en original/ (no van en el repo).")
        print("== comunes")
        comprueba("fichero inexistente", aplicar(os.path.join(tmp, "no_existe.com")).returncode != 0)
        comprueba("sin argumentos: ayuda", "python aplicar.py" in aplicar().stderr)
        open(os.path.join(tmp, "basura.com"), "wb").write(os.urandom(5000))
        r = aplicar(os.path.join(tmp, "basura.com"))
        comprueba("un fichero cualquiera se rechaza y lista las versiones", r.returncode != 0 and "2025-11" in r.stderr, r.stderr)

    print("\n%s" % ("TODO BIEN" if not fallos else "FALLAN: " + ", ".join(fallos)))
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
