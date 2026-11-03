; SRLFN: nombres largos (VFAT) en SofaRun 8.1 (SR.COM, de Louthrax)
;
; La lista de ficheros de SofaRun ensena 63 caracteres del nombre largo (el 8.3 si no lo tiene) en una sola
; columna de 80 (con 80 columnas de pantalla; con 40 se queda como era). Las constantes de la rejilla se cambian
; al empezar el modo de pantalla (3E54h): setlay, con la tabla de lay.inc que escribe parchear.py.
;
; Va detras del final de SR.COM (8971h): el parche mueve alli el principio del monton (parchear.py).
; Se desvian estos sitios:
;   3E54h  LD A,(7DECh)           -> CALL setlay   (la pantalla ya tiene su ancho: la rejilla ancha o la de siempre)
;   0F86h  PUSH BC / PUSH IY      -> CALL mk       (el nombre que se pinta en cada celda de la lista)
;   0E58h  LD HL,(7451h)          -> CALL build    (acabada la lista y ordenada: la tabla de nombres)
;   0CD2h  PUSH DE / LD HL,(7455h)-> JP lfnfree    (se libera la lista: tambien la tabla)
;
; La lista de SofaRun: entradas de 18 bytes (nombre 8.3 en 13, +13 tipo, +14 tamano) en el monton desde (7455h),
; (7D1Bh) entradas, ordenadas (primero por clase: '..' 7Fh, unidades 7Eh, carpetas 7Dh y el resto 0, de mayor a
; menor; y dentro de cada clase por el nombre). La rutina que pinta la pagina (0F0Eh) llama a 3FE9h con la cadena
; (que copia tal cual: el largo que se le da) y el indice de la entrada en (IX-14).
;
; Solo lee. Acabada la lista, "build" hace una tabla de 64 bytes por entrada (63 caracteres y una marca) y la pasada
; recorre el directorio con _RDDRV (un sector cada vez), junta las entradas LFN de cada 8.3 (comprobando el orden y el
; checksum) y busca la entrada de la lista con una busqueda binaria por clase y nombre. Si no cabe en el monton (o
; algo falla) la lista se queda en 8.3.

BDOS            equ     0005h
MALLOC          equ     5BD6h           ; DE = bytes -> HL = puntero. Si no hay sitio SofaRun se acaba: antes MAXFREE
FREE            equ     5CB4h           ; DE = puntero
MAXFREE         equ     5FC3h           ; -> HL = el bloque libre mas grande, en bytes
ARRAY           equ     7455h           ; puntero a la lista de entradas
COUNT           equ     7D1Bh           ; numero de entradas
SORTED          equ     7451h           ; lo que cargaba la instruccion de 0E58h
PATHV           equ     7D1Dh           ; la ruta que se lista: "A:\ROMS\"

_CURDRV         equ     19h
_SETDTA         equ     1Ah
_DPARM          equ     31h
_FFIRST         equ     40h
_RDDRV          equ     73h
_GETCLUS        equ     7Eh

WIDTH           equ     63              ; caracteres que se pintan del nombre (la entrada de la tabla es de 64 bytes)
HEADW           equ     44              ; recortado: 44 + "..." + 16
TAILW           equ     16
LFNSEQ          equ     20              ; 20 partes x 13 = 260 caracteres
SECSZ           equ     512
FIBSZ           equ     64
NOMSZ           equ     LFNSEQ*13+4
TMPSZ           equ     SECSZ+FIBSZ+NOMSZ
MARGIN          equ     16              ; de sobra al pedir memoria

                org     8971h

wide:           db      0               ; 1: pantalla de 80 columnas y rejilla ancha
lfntab:         dw      0               ; la tabla (64 bytes por entrada: 63 caracteres + marca), 0 = no hay
nbuf:           ds      WIDTH+1,0       ; el nombre 8.3 de una entrada sin nombre largo, relleno con espacios
keybuf:         ds      14,0            ; el 8.3 que se busca, como lo pone SofaRun ("NOMBRE.EXT")
tabsz:          dw      0
tmp:            dw      0               ; el bloque de trabajo: sector (512), FIB (64), nombre (264)
frame:          dw      0
fibuf:          dw      0
nombre:         dw      0
drive:          db      0
spc:            db      0               ; sectores por cluster
rootent:        dw      0               ; entradas de la raiz
rootsec:        dw      0               ; primer sector de la raiz
clus:           dw      0
left:           dw      0
sect:           dw      0,0
expect:         db      0               ; parte LFN que toca; FFh = ninguna
chk:            db      0               ; checksum LFN de la cadena que se junta
kcls:           db      0               ; clase de la clave (0 ficheros, 7Dh carpetas)
lo:             dw      0
hi:             dw      0
mid:            dw      0
eptr:           dw      0

; ---------------------------------------------------------------- 0F86h
; Estaba: PUSH BC (BC = el largo) / PUSH IY (la cadena). Ahora la cadena es la nuestra.
mk:             pop     hl              ; la vuelta a 0F89h
                push    bc
                ld      a,(wide)
                or      a
                jr      nz,mk1
                push    iy              ; 40 columnas: lo de siempre
                jp      (hl)
mk1:            push    hl
                call    getname         ; DE = lo que se pinta
                pop     hl
                push    de
                jp      (hl)

; DE = el nombre que se pinta para la entrada IY (indice en IX-14/IX-13): los 63 caracteres de la tabla, o el 8.3
getname:        ld      hl,(lfntab)
                ld      a,h
                or      l
                jr      z,gn83
                ld      l,(ix-14)
                ld      h,(ix-13)
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl           ; indice x 64
                ld      de,(lfntab)
                add     hl,de           ; HL = &tabla[i]
                ld      d,h
                ld      e,l
                ld      bc,WIDTH
                add     hl,bc
                ld      a,(hl)          ; la marca: 1 = tiene nombre largo
                or      a
                ret     nz
gn83:           ld      hl,nbuf         ; 31 espacios y encima el 8.3
                ld      de,nbuf+1
                ld      (hl),' '
                ld      bc,WIDTH-1
                ldir
                push    iy
                pop     hl
                ld      de,nbuf
                ld      b,13
g1:             ld      a,(hl)
                or      a
                jr      z,g2
                ld      (de),a
                inc     hl
                inc     de
                djnz    g1
g2:             ld      de,nbuf
                ret

; ---------------------------------------------------------------- 0E58h
; Acabada la lista (ordenada): se hace la tabla de nombres largos.
build:          push    af
                push    bc
                push    de
                push    ix
                push    iy
                ld      a,(wide)
                or      a
                jr      z,bx            ; 40 columnas: sin nombres largos
                ld      hl,(COUNT)
                ld      a,h
                or      l
                jr      z,bx
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl           ; x 64
                ld      (tabsz),hl
                ld      bc,MARGIN
                add     hl,bc
                push    hl
                call    MAXFREE
                pop     de              ; lo que hace falta
                or      a
                sbc     hl,de
                jr      c,bx            ; no cabe: la lista sigue en 8.3
                ld      de,(tabsz)
                call    MALLOC
                ld      (lfntab),hl
                ld      d,h
                ld      e,l
                inc     de
                ld      (hl),0
                ld      bc,(tabsz)
                dec     bc
                ldir                    ; la tabla vacia (sin marcas)
                call    MAXFREE
                ld      de,TMPSZ+MARGIN
                or      a
                sbc     hl,de
                jr      c,bfree         ; sin sitio para la pasada
                ld      de,TMPSZ
                call    MALLOC
                ld      (tmp),hl
                ld      (frame),hl
                ld      de,SECSZ
                add     hl,de
                ld      (fibuf),hl
                ld      de,FIBSZ
                add     hl,de
                ld      (nombre),hl
                call    lfnscan
                ld      de,(tmp)
                call    FREE
                jr      bx
bfree:          ld      de,(lfntab)
                ld      hl,0
                ld      (lfntab),hl
                call    FREE
bx:             pop     iy
                pop     ix
                pop     de
                pop     bc
                pop     af
                ld      hl,(SORTED)     ; lo que habia
                ret

; ---------------------------------------------------------------- 3E54h
; La pantalla ya tiene su ancho (7DECh): con 80 columnas la rejilla ancha, con 40 la de siempre. Las constantes
; de lay (direccion, de siempre, ancha) se escriben en el codigo de SofaRun. Estaba: LD A,(7DECh)
setlay:         push    bc
                push    de
                push    hl
                ld      a,(7DECh)
                cp      50h
                ld      a,0
                jr      nz,sl0
                inc     a
sl0:            ld      (wide),a
                ld      hl,lay
                ld      b,LAYN
sl1:            ld      e,(hl)
                inc     hl
                ld      d,(hl)
                inc     hl
                ld      c,(hl)          ; la de siempre
                inc     hl
                ld      a,(wide)
                or      a
                jr      z,sl2
                ld      c,(hl)          ; la ancha
sl2:            inc     hl
                ld      a,c
                ld      (de),a
                djnz    sl1
                pop     hl
                pop     de
                pop     bc
                ld      a,(7DECh)       ; lo que habia
                ret

                include "lay.inc"       ; lay: dw direccion / db de_siempre, ancha ... (LAYN entradas)

; ---------------------------------------------------------------- 0CD2h
; Se libera la lista de entradas: tambien la tabla. Estaba: PUSH DE / LD HL,(ARRAY), y sigue en 0CD6h.
lfnfree:        push    af
                push    bc
                push    hl
                push    ix
                push    iy
                push    de
                ld      de,(lfntab)
                ld      a,d
                or      e
                jr      z,lf1
                ld      hl,0
                ld      (lfntab),hl
                call    FREE
lf1:            pop     de
                pop     iy
                pop     ix
                pop     hl
                pop     bc
                pop     af
                push    de
                ld      hl,(ARRAY)
                jp      0CD6h

; ---------------------------------------------------------------- la pasada por el directorio
; Solo si la ruta que se lista es de la unidad actual. Todo en el bloque de trabajo (tmp).
lfnscan:        ld      c,_CURDRV
                call    BDOS
                ld      (drive),a
                ld      hl,PATHV
                ld      a,(hl)
                sub     'A'
                ld      hl,drive
                cp      (hl)
                ret     nz
                ld      de,(fibuf)      ; los parametros del disco (L = unidad: 0, la actual)
                ld      l,0
                ld      c,_DPARM
                call    BDOS
                or      a
                ret     nz
                ld      hl,(fibuf)
                inc     hl
                inc     hl
                inc     hl
                ld      a,(hl)          ; DPB+3: sectores por cluster
                ld      (spc),a
                ld      de,4
                add     hl,de
                ld      e,(hl)          ; DPB+7: entradas de la raiz
                inc     hl
                ld      d,(hl)
                ld      (rootent),de
                ld      de,5
                add     hl,de
                ld      e,(hl)          ; DPB+13: primer sector de la raiz
                inc     hl
                ld      d,(hl)
                ld      (rootsec),de
                ld      de,(frame)
                ld      c,_SETDTA
                call    BDOS
                call    full
                ld      de,80h          ; el DTA de siempre
                ld      c,_SETDTA
                jp      BDOS

full:           ld      a,0FFh
                ld      (expect),a
                ld      hl,0
                ld      a,(PATHV+3)     ; en la raiz no hay "."
                or      a
                jr      z,f_root
                ld      ix,(fibuf)      ; el cluster de la carpeta: el de su entrada "."
                ld      de,dotstr
                ld      b,10h
                ld      c,_FFIRST
                call    BDOS
                or      a
                ret     nz
                ld      l,(ix+19)
                ld      h,(ix+20)
f_root:         ld      a,h
                or      l
                jr      nz,nextclus
                ld      hl,(rootsec)    ; raiz de FAT12/16: sectores seguidos
                ld      (sect),hl
                ld      hl,0
                ld      (sect+2),hl
                ld      hl,(rootent)    ; entradas / 16
                ld      b,4
div16:          srl     h
                rr      l
                djnz    div16
                ld      (left),hl
                jr      rdsec

nextclus:       ex      de,hl           ; DE = cluster
                ld      hl,(fibuf)
                xor     a
                ld      c,_GETCLUS
                call    BDOS
                or      a
                ret     nz
                ld      hl,(fibuf)
                ld      de,4
                add     hl,de
                ld      de,sect
                ld      bc,4
                ldir                    ; primer sector del cluster
                ld      e,(hl)
                inc     hl
                ld      d,(hl)          ; DE = siguiente cluster
                inc     hl
                ld      a,(hl)          ; sectores por cluster
                inc     hl
                bit     3,(hl)          ; ultimo cluster
                jr      z,nc1
                ld      de,0
nc1:            ld      (clus),de
                ld      l,a
                ld      h,0
                ld      (left),hl

; lee (left) sectores desde (sect) y luego los clusters que siga (clus)
rdsec:          ld      a,(drive)
                ld      b,1
                ld      de,(sect)
                ld      hl,(sect+2)
                ld      c,_RDDRV
                call    BDOS
                or      a
                ret     nz
                ld      hl,sect
                ld      b,4
inc32:          inc     (hl)
                jr      nz,rd1
                inc     hl
                djnz    inc32
rd1:            ld      ix,(frame)
                ld      b,16
scan:           push    bc
                call    entry
                pop     bc
                ret     z               ; fin del directorio
                ld      de,32
                add     ix,de
                djnz    scan
                ld      hl,(left)
                dec     hl
                ld      (left),hl
                ld      a,h
                or      l
                jr      nz,rdsec
                ld      hl,(clus)
                ld      a,h
                or      l
                jr      nz,nextclus
                ret

dotstr:         db      ".",0

; IX = entrada del directorio. Vuelve NZ para seguir, o Z en el fin del directorio.
entry:          ld      a,(ix+0)
                or      a
                ret     z               ; fin
                cp      0E5h
                jr      z,e_reset       ; borrada
                ld      a,(ix+11)
                cp      0Fh
                jr      z,e_lfn
                and     8
                jr      nz,e_reset      ; la etiqueta del volumen
                ld      a,(expect)      ; una cadena LFN completa y de este 8.3?
                or      a
                jr      nz,e_reset
                push    ix
                pop     hl
                call    cksum
                ld      hl,chk
                cp      (hl)
                call    z,attach
e_reset:        ld      a,0FFh
                ld      (expect),a
                or      a               ; NZ
                ret

e_lfn:          ld      a,(ix+0)
                bit     6,a
                jr      z,e_lfn1
                ld      a,(ix+13)       ; la ultima parte (la primera que sale): empieza una cadena
                ld      (chk),a
e_lfn1:         ld      a,(ix+13)
                ld      hl,chk
                cp      (hl)
                jr      nz,e_reset      ; de otro fichero
                ld      a,(ix+0)
                bit     6,a
                jr      z,e_lfn2
                and     1Fh
                jr      z,e_reset
                cp      LFNSEQ+1
                jr      nc,e_reset
                ld      (expect),a
                call    mul13
                ld      (hl),0          ; fin de cadena tras la ultima parte
                ld      a,(ix+0)
e_lfn2:         and     1Fh
                jr      z,e_reset       ; parte 0: no existe (directorio estropeado)
                ld      hl,expect
                cp      (hl)
                jr      nz,e_reset      ; una parte suelta
                dec     (hl)            ; la siguiente sera la anterior
                ld      a,(hl)          ; = numero de parte - 1
                call    mul13
                ex      de,hl
                ld      hl,offs
                ld      b,13
e_chr:          push    bc
                push    hl
                ld      c,(hl)
                ld      b,0
                push    ix
                pop     hl
                add     hl,bc
                ld      c,(hl)
                inc     hl
                ld      a,(hl)
                call    conv
                ld      (de),a
                inc     de
                pop     hl
                inc     hl
                pop     bc
                djnz    e_chr
                or      1               ; NZ
                ret

; HL = nombre + A*13
mul13:          ld      l,a
                ld      h,0
                ld      c,l
                ld      b,h
                add     hl,hl
                add     hl,bc           ; 3
                add     hl,hl
                add     hl,hl           ; 12
                add     hl,bc           ; 13
                ld      bc,(nombre)
                add     hl,bc
                ret

; A = checksum LFN de los 11 bytes de HL
cksum:          ld      b,11
                xor     a
ck1:            rrca
                add     a,(hl)
                inc     hl
                djnz    ck1
                ret

; UTF-16 (A = alto, C = bajo) -> caracter que se puede pintar (0 = fin)
conv:           or      a
                jr      nz,conv_hi
                ld      a,c
                or      a
                ret     z
                cp      20h
                jr      c,conv_q
                cp      7Fh
                ret     c
                sub     0C0h
                jr      c,conv_q
                ld      hl,latin1
                add     a,l
                ld      l,a
                jr      nc,conv1
                inc     h
conv1:          ld      a,(hl)
                ret
conv_hi:        inc     a               ; FFFFh = relleno
                jr      nz,conv_q
                ld      a,c
                inc     a
                ret     z
conv_q:         ld      a,'?'
                ret

offs:           db      1,3,5,7,9,14,16,18,20,22,24,28,30
latin1:         db      "AAAAAAACEEEEIIIIDNOOOOOxOUUUUYTs"      ; C0h-DFh
                db      "aaaaaaaceeeeiiiidnooooo/ouuuuyty"      ; E0h-FFh

; IX = una entrada 8.3 con su cadena LFN completa y buena: se busca en la lista y se pone su nombre en la tabla
attach:         ld      a,(ix+0)
                cp      '.'
                ret     z               ; "." y ".."
                push    ix
                pop     hl
                ld      de,keybuf       ; el 8.3 como lo pone SofaRun: NOMBRE.EXT
                ld      b,8
ak1:            ld      a,(hl)
                cp      ' '
                jr      z,ak2
                ld      (de),a
                inc     de
                inc     hl
                djnz    ak1
ak2:            push    ix
                pop     hl
                ld      bc,8
                add     hl,bc
                ld      a,(hl)
                cp      ' '
                jr      z,ak5
                ld      a,'.'
                ld      (de),a
                inc     de
                ld      b,3
ak3:            ld      a,(hl)
                cp      ' '
                jr      z,ak5
                ld      (de),a
                inc     de
                inc     hl
                djnz    ak3
ak5:            xor     a
                ld      (de),a
                ld      a,(ix+11)       ; la clase: carpetas 7Dh, el resto 0
                and     10h
                jr      z,ak6
                ld      a,7Dh
ak6:            ld      (kcls),a
                ld      hl,(COUNT)
                ld      a,h
                or      l
                ret     z
                dec     hl
                ld      (hi),hl
                ld      hl,0
                ld      (lo),hl
bs:             ld      de,(lo)         ; mientras lo <= hi
                ld      hl,(hi)
                or      a
                sbc     hl,de
                ret     c
                ld      hl,(lo)
                ld      de,(hi)
                add     hl,de
                srl     h
                rr      l
                ld      (mid),hl
                call    entp
                ld      (eptr),hl
                ld      de,13
                add     hl,de
                ld      a,(hl)          ; el tipo de la entrada -> su clase
                cp      7Dh
                jr      c,cl0
                cp      80h
                jr      c,cl1
cl0:            xor     a
cl1:            ld      b,a             ; B = clase de la entrada
                ld      a,(kcls)
                cp      b
                jr      z,bs_name
                ld      a,b             ; las clases van de mayor a menor
                ld      hl,kcls
                cp      (hl)
                jr      c,bs_hi         ; la entrada es de clase menor: va despues de la clave
                jr      bs_lo
bs_name:        ld      hl,(eptr)       ; mismas clases: por el nombre (bytes sin signo)
                ld      de,keybuf
bn1:            ld      a,(hl)
                ld      c,a             ; C = la entrada
                ld      a,(de)          ; A = la clave
                cp      c
                jr      nz,bn2
                or      a
                jr      z,found         ; iguales hasta el fin
                inc     hl
                inc     de
                jr      bn1
bn2:            jr      c,bs_hi         ; clave < entrada
bs_lo:          ld      hl,(mid)        ; clave > entrada: la entrada va antes
                inc     hl
                ld      (lo),hl
                jr      bs
bs_hi:          ld      hl,(mid)
                ld      a,h
                or      l
                ret     z               ; ya no hay nada antes
                dec     hl
                ld      (hi),hl
                jr      bs

; HL = indice -> HL = &lista[indice] (18 bytes por entrada)
entp:           ld      d,h
                ld      e,l
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl           ; x 16
                ex      de,hl
                add     hl,hl           ; x 2
                add     hl,de           ; x 18
                ld      de,(ARRAY)
                add     hl,de
                ret

; la entrada (mid) esta en la lista: su nombre largo, tal como se pinta, a la tabla
found:          ld      hl,(mid)
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl           ; x 64
                ld      de,(lfntab)
                add     hl,de
                ex      de,hl           ; DE = &tabla[mid]
                push    de
                ld      hl,(nombre)     ; longitud del nombre (hasta el 0)
                ld      bc,0
fl1:            ld      a,(hl)
                or      a
                jr      z,fl2
                inc     hl
                inc     bc
                jr      fl1
fl2:            ld      hl,(nombre)
                ld      a,b
                or      c
                jr      z,fm_ret        ; vacio: sin nombre largo
                ld      a,b
                or      a
                jr      nz,fm_long      ; mas de 255
                ld      a,c
                cp      WIDTH+1
                jr      nc,fm_long
                push    bc              ; cabe: se copia y se rellena con espacios
                ldir
                pop     bc
                ld      a,WIDTH
                sub     c
                jr      z,fm_ok
                ld      b,a
fm_pad:         ld      a,' '
                ld      (de),a
                inc     de
                djnz    fm_pad
                jr      fm_ok
fm_long:        push    bc              ; los 20 primeros, "..." y los 8 ultimos
                ld      bc,HEADW
                ldir
                ld      b,3
fm_dot:         ld      a,'.'
                ld      (de),a
                inc     de
                djnz    fm_dot
                pop     bc
                ld      hl,(nombre)
                add     hl,bc
                ld      bc,TAILW
                or      a
                sbc     hl,bc
                ldir
fm_ok:          pop     hl
                ld      de,WIDTH
                add     hl,de
                ld      (hl),1
                ret
fm_ret:         pop     hl
                ret

codeend:
