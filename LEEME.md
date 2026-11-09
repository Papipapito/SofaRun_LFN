# SR_LFN — nombres largos para SofaRun (MSX)

Parche no oficial que hace que **SofaRun 8.1** (`SR.COM`, de Louthrax; las dos compilaciones, ver abajo) enseñe los **nombres largos** (VFAT, los que se
ven en Windows) en **una sola columna**, en vez de `METALG~1.ROM` en cuatro columnas estrechas.
[English version](README.md).

```
antes:    ALESTE~1.ROM  24.0K   ALESTE~2.ROM  32.0K   F-1SPI~1.ROM   152K   GOLVEL~1.ROM   168K
ahora:    Aleste 1 - Eleven Fighters (1988)(Compile).rom                                    24.0K
          Golvellius - Valley of Doom (1987)(Compile)(JP).rom                                168K
```

- Hasta **63 caracteres** del nombre largo, con el tamaño a la derecha. Si es más largo salen los 44 primeros, `...` y los
  16 últimos, para que se vea la extensión. Los ficheros sin nombre largo salen en 8.3, como siempre.
- Con una pantalla de 40 columnas (o «Force 40 columns») SofaRun se queda como era.
- Lanzar, ajustes y todo lo demás siguen yendo con el 8.3, como antes: es **solo para ver**.

## Cómo aplicarlo

Hace falta tu propia copia del `SR.COM` original. **No** va en este repositorio. SofaRun 8.1 existe en dos compilaciones
que por dentro dicen «v8.1»; se distinguen por el tamaño de `SR.COM`:

| Compilación | `SR.COM` | sha1 | Resultado |
| --- | --- | --- | --- |
| 8.1 | 34.929 bytes | `2f13bb7303d4cc4f9c0a54c084907e320777be22` | 36.242 bytes, `c2f56896a09bf856ec21ae842752cb8925aede71` |
| 8.1, noviembre de 2025 (la del zip de la web de SofaRun) | 35.115 bytes | `2d95ca7d366f7ac87b299102e1b148692d934706` | 36.428 bytes, `0b3ff3bec96d550ce4902ea3830c95ace5499199` |

Elige una de estas:

1. **Página web, sin instalar nada:** abre [el aplicador en línea](https://papipapito.github.io/SofaRun_LFN/aplicar.html)
   (o el [`aplicar.html`](aplicar.html) descargado) en el navegador y suelta encima tu `SR.COM`. Todo ocurre en tu
   navegador: el fichero no se sube a ningún sitio.
2. **Python 3:** `python aplicar.py SR.COM` → escribe `SR_LFN.COM` al lado.
3. **Cualquier parcheador de IPS** (Floating IPS, Lunar IPS…): aplica [`SR_LFN.ips`](SR_LFN.ips) (34.929 bytes) o
   [`SR_LFN_2025-11.ips`](SR_LFN_2025-11.ips) (35.115 bytes) a `SR.COM`. Los parcheadores de IPS no comprueban el fichero de
   origen: comprueba antes el sha1 de arriba.

Después copia el resultado a la tarjeta como `SR.COM`, en la carpeta de SofaRun (junto a `SR.INI`). `aplicar.py` y
`aplicar.html` reconocen la compilación por el sha1, rechazan cualquier fichero que no sea exactamente uno de los originales de arriba y
comprueban el sha1 del resultado.

## Requisitos y límites

- **Nextor 2.1 o 3.0**, FAT16 o FAT12, y una pantalla de **80 columnas** (MSX2 o superior). Con otro DOS, o si algo
  falla, se ven los 8.3.
- **El límite es la memoria.** Los nombres van en el montón de SofaRun, que es pequeño (unos 16 KB). Con entradas de 64
  bytes caben los nombres de unos **180-200 ficheros por carpeta** (con 180 funciona en las pruebas, con 230 no); con más, la lista enseña los 8.3 como la original (no se
  cuelga). Pasar la tabla a un segmento del mapper lo arreglaría; todavía no está hecho.
- Solo ASCII: las letras latinas acentuadas salen sin acento y lo demás como `?`. El título del menú Game sigue
  enseñando el 8.3. El orden es el de siempre (por el 8.3). Dentro de un ZIP no cambia nada.
- Entrar en una carpeta tarda algo más: se vuelve a leer para buscar los nombres largos.
- Probado **solo en openMSX** (Philips NMS 8245, Sunrise IDE, Nextor 2.1.4, FAT16): con la primera compilación, listas de
  25, 180 y 430 ficheros, entrar y salir de carpetas, mover el cursor y el menú Game; con la de noviembre de 2025, la lista
  de 25 ficheros y entrar y salir de una carpeta (su código de lista, dibujo y orden es el mismo, solo se movieron las
  direcciones). No probado en hardware real, con Nextor 3.0, con ZIP ni con una pantalla real de 40 columnas.

## Reconstruirlo y probarlo

El parche es Z80 escrito a mano (`src/srlfn.asm`) sobre el desensamblado del binario. Con
[pasmo](http://pasmo.speccy.org/) (o WSL en Windows) y los originales en `original/` (`SR.COM` para la primera
compilación, `SR_2025-11.COM` para la segunda):

```
python tools/hacer_parche.py     # construye los .ips, aplicar.py y aplicar.html
python tests/probar.py           # prueba las tres formas de aplicarlo (node es opcional)
```

`tests/openmsx/probar_mm.py` es el banco de openMSX (hecho antes para Multi Mente). `--escenario libre --acciones "..."`
ejecuta acciones sueltas; para SofaRun pon `SR.COM` en la carpeta de `--mm-dir` y mira su cabecera. `BENCH_EXTRA=400` añade
400 ficheros de nombre largo a `\ROMS`.

## Sobre SofaRun y este parche

SofaRun es obra de Louthrax. Este repositorio es un complemento no oficial y no cuenta con el aval del autor.
**No contiene nada del código de SofaRun**: `SR_LFN.ips` lleva solo los bytes nuevos (unos 1,4 KB) y las herramientas
comprueban que cada byte del parche es distinto del original en su sitio. Hay que traer el propio `SR.COM`. Si el autor se
opone, que lo diga y se retira. El código de este repositorio va bajo la GNU GPL v3, ver [LICENSE](LICENSE).
