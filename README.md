# SR_LFN — long file names for SofaRun (MSX)

An unofficial patch that makes **SofaRun 8.1** (`SR.COM`, by Louthrax) show **long file names** (VFAT, the ones you see
in Windows) in a **single column**, instead of `METALG~1.ROM` in four narrow columns. [Versión en castellano](LEEME.md).

```
before:   ALESTE~1.ROM  24.0K   ALESTE~2.ROM  32.0K   F-1SPI~1.ROM   152K   GOLVEL~1.ROM   168K
after:    Aleste 1 - Eleven Fighters (1988)(Compile).rom                                    24.0K
          Golvellius - Valley of Doom (1987)(Compile)(JP).rom                                168K
```

- Up to **63 characters** of the long name, size on the right. Longer names show the first 44, `...` and the last 16, so
  the extension stays visible. Files without a long name show their 8.3 name as always.
- With a 40-column screen (or "Force 40 columns") SofaRun is left as it was.
- Launching, settings and everything else work on the 8.3 name, as before: this is **view only**.

## Apply it

You need your own copy of the original `SR.COM` of SofaRun 8.1 (34,929 bytes, sha1
`2f13bb7303d4cc4f9c0a54c084907e320777be22`). It is **not** included here. Pick any of these:

1. **Web page, nothing to install:** open [the online patcher](https://papipapito.github.io/SofaRun_LFN/aplicar.html)
   (or the downloaded [`aplicar.html`](aplicar.html)) in a browser and drop your `SR.COM` on it. It runs in your
   browser; the file is not uploaded anywhere.
2. **Python 3:** `python aplicar.py SR.COM` → writes `SR_LFN.COM` next to it.
3. **Any IPS patcher** (Floating IPS, Lunar IPS…): apply [`SR_LFN.ips`](SR_LFN.ips) to `SR.COM`. IPS patchers do not check the
   source file, so check the sha1 above first.

Then copy the result to the card as `SR.COM`, in the SofaRun folder (next to `SR.INI`). `aplicar.py` and `aplicar.html`
refuse any file that is not exactly the original 8.1 and check the sha1 of the result (36,242 bytes,
`c2f56896a09bf856ec21ae842752cb8925aede71`).

## Requirements and limits

- **Nextor 2.1 or 3.0**, FAT16 or FAT12, and an **80-column** screen (MSX2 or newer). With another DOS, or if anything
  fails, you just see the 8.3 names.
- **Memory is the limit.** The names are kept in SofaRun's heap, which is small (about 16 KB). With 64-byte entries it
  holds the names of roughly **180-200 files per folder** (180 works in the tests, 230 does not); with more files than that the list shows the 8.3 names, as the
  original does (it does not crash). Moving the table to a mapper segment would lift this; it is not done yet.
- Only ASCII: accented Latin letters show without the accent, anything else as `?`. The title of the Game menu still
  shows the 8.3 name. Sorting is the original one (by 8.3 name). Inside ZIP files nothing changes.
- Entering a folder takes a little longer: the folder is read again to find the long names.
- Tested **only in openMSX** (Philips NMS 8245, Sunrise IDE, Nextor 2.1.4, FAT16): lists of 25, 180 and 430 files, entering
  and leaving folders, moving the cursor, the Game menu. Not tried on real hardware, with Nextor 3.0, with ZIP files or
  with a real 40-column screen.

## Rebuild and test

The patch is hand-written Z80 (`src/srlfn.asm`) over the disassembly of the binary. With
[pasmo](http://pasmo.speccy.org/) (or WSL on Windows) and the original in `original/SR.COM`:

```
python tools/hacer_parche.py     # builds SR_LFN.ips, aplicar.py and aplicar.html
python tests/probar.py           # checks the three ways of applying it (node is optional)
```

`tests/openmsx/probar_mm.py` is the openMSX bench (originally made for Multi Mente). `--escenario libre --acciones "..."`
runs free actions; for SofaRun put `SR.COM` in the folder given with `--mm-dir`, and see its header for the rest.
`BENCH_EXTRA=400` adds 400 long-named files to `\ROMS`.

## About SofaRun and this patch

SofaRun is the work of Louthrax. This repository is an unofficial add-on and is not endorsed by the author. It contains
**none of SofaRun's code**: `SR_LFN.ips` holds only the new bytes (about 1.4 KB) and the tools check that every byte of the
patch differs from the original at its place. You must supply your own `SR.COM`. If the author objects, tell us and it will
be taken down. The code in this repository is under the GNU GPL v3, see [LICENSE](LICENSE).
