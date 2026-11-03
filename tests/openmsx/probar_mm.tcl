# probar_mm.tcl - guion de openMSX del banco de pruebas de Multi Mente (lo lanza probar_mm.py).
#
# Se carga DESPUES de params.tcl (que define ::P(log), ::P(salida), ::P(etiqueta), ::P(targets)).
# Es una cola de pasos: cada paso hace lo suyo y llama a q_next al terminar. Todos los tiempos son de
# tiempo EMULADO (con 'throttle off' pasan mucho mas deprisa que en tiempo real).
#   1. espera el prompt de DOS (get_screen en modo texto)               CHECK dos_prompt
#   2. VER (para dejar escritas las versiones de Nextor), CD \ROMS, MM  CHECK cd_roms, CHECK mm_arranca
#   3. espera a que la VRAM deje de cambiar y captura la LISTA          <etiqueta>_01_lista.png
#   4. baja el cursor a cada objetivo y captura el panel File info      <etiqueta>_NN_info_<nombre>.png
#   5. sale de MM con Q (comprueba que vuelve al prompt de DOS) y sale de openMSX   CHECK mm_sale
# Cada captura va con un volcado en el log (modo de pantalla y hash de la VRAM; si la pantalla esta en
# modo texto, tambien el texto). MM usa SCREEN 7 (graficos): ahi el contenido solo se ve en la captura.
#
# OJO: la ventana de openMSX tiene que poder dibujar (no se usa 'renderer none': no hay capturas sin ella).

set save_settings_on_exit off
catch {set throttle off}
catch {set mute on}
set ::fallos 0
set ::perdidas 0
set ::q {}
set ::pos 0

# ---------------------------------------------------------------- utilidades
proc lg {msg} {
	set f [open $::P(log) a]
	puts $f [format "%8.2f %s" [machine_info time] $msg]
	close $f
}
proc check {nombre ok detalle} {
	lg "CHECK $nombre [expr {$ok ? {OK} : {FALLA}}] $detalle"
	if {!$ok} {incr ::fallos}
}
proc q_add {args} { lappend ::q $args }
proc q_next {} {
	if {[llength $::q] == 0} { s_fin; return }
	set cmd [lindex $::q 0]
	set ::q [lrange $::q 1 end]
	if {[catch {uplevel #0 $cmd} err]} {
		lg "ERROR en paso {$cmd}: $err"
		incr ::fallos
		s_fin
	}
}
proc pantalla_texto {} {
	if {[catch {get_screen} s]} { return "" }
	return $s
}
proc modo {} { return [get_screen_mode] }
proc vram_hash {} {
	# suma de comprobacion de la pagina 0 de SCREEN 7 desde la linea 32 (2000h-D3FFh): sirve para ver si la
	# pantalla cambia. Se salta la cabecera porque MM pinta ahi el reloj (cambia cada segundo).
	set d [debug read_block VRAM 0x2000 0xB400]
	binary scan $d c* bytes
	set s 0
	foreach b $bytes { set s [expr {($s * 31 + ($b & 0xFF)) & 0xFFFFFF}] }
	return [format %06X $s]
}
proc volcado {nombre} {
	lg "-- $nombre: modo [modo], VRAM hash [vram_hash]"
	set t [pantalla_texto]
	if {$t ne ""} {
		foreach l [split $t "\n"] { if {[string trim $l] ne ""} { lg "   | [string trimright $l]" } }
	}
}

# teclas por la matriz del teclado: {fila mascara}
array set ::KEY {
	RIGHT {8 0x80} DOWN {8 0x40} UP {8 0x20} LEFT {8 0x10} SPACE {8 0x01}
	RETURN {7 0x80} ESC {7 0x04} TAB {7 0x08} BS {7 0x20} SELECT {7 0x40}
	SHIFT {6 0x01} CTRL {6 0x02} GRAPH {6 0x04}
	Q {4 0x40} I {3 0x40} Y {5 0x40}
}
# letras, cifras y simbolos de la matriz del teclado MSX (cada fila, de bit 0 a bit 7)
foreach {r chars} {0 {0 1 2 3 4 5 6 7} 3 {c d e f g h i j} 4 {k l m n o p q r} 5 {s t u v w x y z}} {
	set bit 0
	foreach ch $chars {
		set ::KEY($ch) [list $r [format 0x%02X [expr {1 << $bit}]]]
		set ::KEY([string toupper $ch]) $::KEY($ch)
		incr bit
	}
}
set ::KEY(8) {1 0x01}
set ::KEY(9) {1 0x02}
set ::KEY(a) {2 0x40}
set ::KEY(A) {2 0x40}
set ::KEY(b) {2 0x80}
set ::KEY(B) {2 0x80}
proc key_down {k} { lassign $::KEY($k) r m; keymatrixdown $r $m }
proc key_up {k} { lassign $::KEY($k) r m; keymatrixup $r $m }

# ---------------------------------------------------------------- pasos
proc s_wait {segundos} { after time $segundos q_next }

# escribe en la linea de comandos de DOS (buffer de teclado de la BIOS)
proc s_type {texto} {
	type_via_keybuf $texto
	after time [expr {0.5 + 0.15 * [string length $texto]}] q_next
}

# pulsa la tecla n veces: pulsada 0.15 s, suelta 0.30 s (y luego q_next)
proc s_key {k {n 1}} {
	if {$n <= 0} { q_next; return }
	key_down $k
	after time 0.15 [list s_key_up $k $n]
}
proc s_key_up {k n} {
	key_up $k
	after time 0.30 [list s_key $k [expr {$n - 1}]]
}

# espera a que aparezca un texto (literal) en la pantalla de texto
proc s_waittext {nombre texto limite} {
	set ::wt_t0 [machine_info time]
	wt_poll $nombre $texto $limite
}
proc wt_poll {nombre texto limite} {
	set t [pantalla_texto]
	if {[string first $texto $t] >= 0} {
		check $nombre 1 "visto '$texto' tras [format %.1f [expr {[machine_info time] - $::wt_t0}]] s emulados"
		volcado $nombre
		q_next
	} elseif {[machine_info time] - $::wt_t0 > $limite} {
		check $nombre 0 "no aparecio '$texto' en $limite s emulados"
		volcado "$nombre (timeout)"
		s_fin
	} else {
		after time 0.5 [list wt_poll $nombre $texto $limite]
	}
}

# espera a que el modo de pantalla deje de ser el dado (MM ha tomado la pantalla)
proc s_waitmode_not {nombre modo_viejo limite} {
	set ::wt_t0 [machine_info time]
	wm_poll $nombre $modo_viejo $limite
}
proc wm_poll {nombre modo_viejo limite} {
	if {[modo] ne $modo_viejo} {
		check $nombre 1 "modo [modo] tras [format %.1f [expr {[machine_info time] - $::wt_t0}]] s emulados"
		q_next
	} elseif {[machine_info time] - $::wt_t0 > $limite} {
		check $nombre 0 "el modo de pantalla sigue siendo $modo_viejo tras $limite s emulados"
		volcado "$nombre (timeout)"
		s_fin
	} else {
		after time 0.5 [list wm_poll $nombre $modo_viejo $limite]
	}
}

# espera a que la VRAM no cambie durante 'estable' s emulados
proc s_settle {nombre estable limite} {
	set ::st_t0 [machine_info time]
	set ::st_h ""
	set ::st_desde [machine_info time]
	st_poll $nombre $estable $limite
}
proc st_poll {nombre estable limite} {
	set h [vram_hash]
	set ahora [machine_info time]
	if {$h ne $::st_h} { set ::st_h $h; set ::st_desde $ahora }
	if {$ahora - $::st_desde >= $estable} {
		lg "settle $nombre: VRAM estable ($h) tras [format %.1f [expr {$ahora - $::st_t0}]] s"
		q_next
	} elseif {$ahora - $::st_t0 > $limite} {
		check $nombre 0 "la VRAM no se estabilizo en $limite s"
		q_next
	} else {
		after time 0.25 [list st_poll $nombre $estable $limite]
	}
}

# captura (PNG de 640x480 solo con la imagen MSX) + volcado en el log.
# TRUCO: con 'throttle off' el emulador corre muy por delante del reloj real y la ventana solo se repinta en
# tiempo real, asi que 'screenshot' sacaba un fotograma de hace varios segundos EMULADOS (la lista vacia, el
# prompt de DOS...). Por eso para cada captura se vuelve a velocidad normal, se esperan 0.6 s emulados (36
# fotogramas pintados de verdad) y se saca; luego se vuelve a 'throttle off'.
proc s_shot {nombre} {
	set ::throttle on
	after time 0.6 [list s_shot2 $nombre]
}
proc s_shot2 {nombre} {
	set et [expr {$::P(etiqueta) eq "" ? "" : "$::P(etiqueta)_"}]
	set f "$::P(salida)/${et}${nombre}.png"
	screenshot -raw -size 640 $f
	set ::throttle off
	lg "captura $f"
	volcado $nombre
	q_next
}

# pulsa la tecla n veces y COMPRUEBA que cada pulsacion ha cambiado la pantalla (hash de la VRAM): MM a veces
# no ve una pulsacion corta (se perdia la primera tras arrancar); si no cambia, se repite (hasta 4 veces)
proc s_keyc {k n} {
	if {$n <= 0} { q_next; return }
	set ::kc_h [vram_hash]
	set ::kc_try 0
	kc_press $k $n
}
proc kc_press {k n} {
	key_down $k
	after time 0.25 [list kc_release $k $n]
}
proc kc_release {k n} {
	key_up $k
	after time 0.40 [list kc_verify $k $n]
}
proc kc_verify {k n} {
	if {[vram_hash] ne $::kc_h} {
		s_keyc $k [expr {$n - 1}]
	} elseif {$::kc_try < 4} {
		incr ::kc_try
		incr ::perdidas
		lg "tecla $k sin efecto (intento $::kc_try), se repite"
		kc_press $k $n
	} else {
		check tecla_$k 0 "la pantalla no cambia tras 5 pulsaciones"
		q_next
	}
}

proc s_mover {destino} {
	set d [expr {$destino - $::pos}]
	set ::pos $destino
	if {$d > 0} { s_keyc DOWN $d } elseif {$d < 0} { s_keyc UP [expr {-$d}] } else { q_next }
}

proc s_objetivo {num pos slug nombre esp_lista esp_lista83 esp_info} {
	lg "OBJETIVO $num: posicion $pos de la lista, fichero '$nombre'"
	lg "   esperado con parche: lista '$esp_lista', File info Name: '$esp_info'"
	lg "   esperado sin parche: lista '$esp_lista83'"
	q_next
}

set ::fin_hecho 0
proc s_fin {} {
	if {$::fin_hecho} { return }
	set ::fin_hecho 1
	if {[info exists ::bp_ids] && [llength $::bp_ids] > 0} {
		if {[catch {bp_informe} err]} { lg "ERROR en bp_informe: $err" }
	}
	lg "FIN fallos=$::fallos pulsaciones_repetidas=$::perdidas"
	exit
}

# vigilante: si en 900 s emulados no ha acabado, sale
after time 900 {lg "WATCHDOG: 900 s emulados sin terminar"; incr ::fallos; s_fin}

# ================================================================ escenarios con acciones (DSL)
# Los escenarios 'interaccion', 'cs' y 'libre' los define probar_mm.py como una lista de acciones
# (::P(acciones)); cada accion es una lista Tcl {verbo args...}. Verbos:
#   waitprompt                 espera el prompt 'A:\>' de DOS
#   dos CMD                    teclea CMD + RETURN en el DOS (buffer de teclado de la BIOS)
#   waittext NOMBRE TEXTO [s]  espera TEXTO en la pantalla de texto (CHECK NOMBRE)
#   waitmm [s]                 espera a que MM tome la pantalla (SCREEN 7) y a que deje de cambiar
#   waitdos [s]                espera a que vuelva un modo de texto
#   key TECLA [n]              pulsa la tecla n veces (A..Z, 0..9, RETURN, ESC, TAB, SPACE, UP, DOWN, LEFT,
#                              RIGHT, SELECT, BS, ... y combinaciones con '+': SHIFT+UP, CTRL+R)
#   keyc TECLA n               igual, y comprueba que cada pulsacion cambia la pantalla (repite si no)
#   text CADENA                teclea la cadena por la matriz del teclado (letras, cifras, \ . - / : espacio)
#   wait S                     espera S segundos emulados
#   settle [S]                 espera a que la VRAM (sin la cabecera) no cambie durante S s (defecto 1.5)
#   shot NOMBRE                captura <etiqueta>_NOMBRE.png + volcado en el log
#   pos N                      el cursor de la lista esta en la entrada N (0 = '..\')
#   goto N                     mueve el cursor (verificado) hasta la entrada N desde la posicion conocida
#   paso NOMBRE                marca el paso en curso (sale en el log y en los puntos de ruptura)
#   log TEXTO                  escribe TEXTO en el log
#   bp_on                      pone los puntos de ruptura de ::P(contar) (ver bp_on)
#   fin                        sale de openMSX
# Cada accion termina con q_next.
proc char_key {c} {
	# {fila mascara shift} de un caracter
	if {[string match {[a-z]} $c]} { return [list {*}$::KEY($c) 0] }
	if {[string match {[A-Z]} $c]} { return [list {*}$::KEY([string tolower $c]) 1] }
	if {[string match {[0-9]} $c]} { return [list {*}$::KEY($c) 0] }
	switch -- $c {
		" " { return [list {*}$::KEY(SPACE) 0] }
		"\\" { return {1 0x10 0} }
		"." { return {2 0x08 0} }
		"-" { return {1 0x04 0} }
		"/" { return {2 0x10 0} }
		":" { return {1 0x80 1} }
		"*" { return {1 0x01 1} }
		"," { return {2 0x04 0} }
	}
	error "tecla desconocida para '$c'"
}
proc s_text {texto} {
	set ::tx_chars [split $texto ""]
	tx_next
}
proc tx_next {} {
	if {[llength $::tx_chars] == 0} { after time 0.3 q_next; return }
	set c [lindex $::tx_chars 0]
	set ::tx_chars [lrange $::tx_chars 1 end]
	lassign [char_key $c] r m sh
	if {$sh} { keymatrixdown 6 1 }
	keymatrixdown $r $m
	after time 0.18 [list tx_up $r $m $sh]
}
proc tx_up {r m sh} {
	keymatrixup $r $m
	if {$sh} { keymatrixup 6 1 }
	after time 0.18 tx_next
}

# teclas con '+' (SHIFT+UP): se pulsan todas a la vez
proc s_keys {spec n} {
	if {$n <= 0} { q_next; return }
	foreach k [split $spec +] { key_down [string toupper $k] }
	after time 0.20 [list s_keys_up $spec $n]
}
proc s_keys_up {spec n} {
	foreach k [split $spec +] { key_up [string toupper $k] }
	after time 0.35 [list s_keys $spec [expr {$n - 1}]]
}

proc s_waitmm {limite {etiq ""} {suave 0}} {
	set ::wt_t0 [machine_info time]
	wmm_poll $limite $etiq $suave
}
# si MM no arranca y se dio una etiqueta, se saltan las acciones hasta 'label ETIQUETA' (y se sigue desde alli)
proc q_saltar_a {etiq} {
	while {[llength $::q] > 0} {
		set c [lindex $::q 0]
		if {[lindex $c 0] eq "s_accion" && [lindex [lindex $c 1] 0] eq "label" && [lindex [lindex $c 1] 1] eq $etiq} { break }
		set ::q [lrange $::q 1 end]
	}
}
proc wmm_poll {limite etiq suave} {
	if {[modo] eq "7"} {
		lg "MM en pantalla (modo 7) tras [format %.1f [expr {[machine_info time] - $::wt_t0}]] s"
		q_add_front s_settle mm 2.0 40
		q_add_front s_wait 2.5
		q_next
	} elseif {[machine_info time] - $::wt_t0 > $limite} {
		if {$suave} {
			lg "MM no ha tomado la pantalla en $limite s (modo [modo]): se sigue (espera 'suave', sin CHECK)"
		} else {
			check waitmm 0 "MM no tomo la pantalla en $limite s (modo [modo])"
		}
		volcado "waitmm (timeout)"
		if {$etiq eq ""} { s_fin } else { lg "se salta hasta la etiqueta $etiq"; q_saltar_a $etiq; q_next }
	} else {
		after time 0.25 [list wmm_poll $limite $etiq $suave]
	}
}
proc s_waitdos {limite} {
	set ::wt_t0 [machine_info time]
	wd_poll $limite
}
proc wd_poll {limite} {
	if {[string match TEXT* [modo]]} {
		q_next
	} elseif {[machine_info time] - $::wt_t0 > $limite} {
		check waitdos 0 "no volvio un modo de texto en $limite s (modo [modo])"
		s_fin
	} else {
		after time 0.25 [list wd_poll $limite]
	}
}

proc s_setpos {n} { set ::pos $n; q_next }

# lleva el cursor a un extremo de la lista pulsando UP (o DOWN) hasta que la pantalla deja de cambiar (dos pulsaciones
# seguidas sin efecto): no depende de donde estuviera ni de si SHIFT+UP/DOWN ('principio/final del directorio' en el
# manual de 2.07A) hace algo en esa version (en la RC5, SHIFT+DOWN no va al final). Deja ::pos = idx.
proc s_alextremo {tecla idx} {
	set ::ax_tecla $tecla
	set ::ax_idx $idx
	set ::ax_try 0
	set ::ax_n 0
	set ::ax_h [vram_hash]
	ax_press
}
proc ax_press {} {
	key_down $::ax_tecla
	after time 0.25 ax_rel
}
proc ax_rel {} {
	key_up $::ax_tecla
	after time 0.40 ax_ver
}
proc ax_ver {} {
	set h [vram_hash]
	incr ::ax_n
	if {$h ne $::ax_h} {
		set ::ax_h $h
		set ::ax_try 0
		ax_press
	} elseif {$::ax_try < 1} {
		incr ::ax_try
		ax_press
	} else {
		set ::pos $::ax_idx
		lg "cursor en el extremo ($::ax_tecla) tras $::ax_n pulsaciones: entrada $::ax_idx"
		q_next
	}
}

# guarda el hash de la VRAM de la pantalla actual con un nombre, y compara luego (CHECK) con el guardado:
# sirve para comprobar que la lista vuelve a quedar igual tras volver de un programa
proc s_hash_guarda {nombre} {
	set ::HG($nombre) [vram_hash]
	lg "hash '$nombre' guardado: $::HG($nombre)"
	q_next
}
# espera (hasta 'limite' s emulados) a que la VRAM vuelva a ser la guardada con ese nombre: MM puede tardar varios
# segundos en repintar la lista tras volver de un programa y tiene pausas largas a mitad de pintado (la RC5 mas),
# asi que 'settle' solo no basta. CHECK OK con el tiempo que ha tardado, o FALLA si no se alcanza.
proc s_hash_espera {nombre limite} {
	set ::he_t0 [machine_info time]
	he_poll $nombre $limite
}
proc he_poll {nombre limite} {
	set h [vram_hash]
	set dt [expr {[machine_info time] - $::he_t0}]
	if {$h eq $::HG($nombre)} {
		check hash_$::paso 1 "la lista vuelve a ser la guardada '$nombre' ($h) tras [format %.1f $dt] s"
		q_next
	} elseif {$dt > $limite} {
		check hash_$::paso 0 "tras $limite s la VRAM es $h y la guardada '$nombre' es $::HG($nombre)"
		q_next
	} else {
		after time 0.25 [list he_poll $nombre $limite]
	}
}
proc s_hash_compara {nombre} {
	set h [vram_hash]
	check hash_$::paso [expr {$h eq $::HG($nombre)}] "hash actual $h, guardado '$nombre' $::HG($nombre)"
	q_next
}

proc s_goto {destino} {
	if {$::pos < 0} { error "posicion del cursor desconocida (usa 'pos N')" }
	s_mover $destino
}

proc s_accion {a} {
	set v [lindex $a 0]
	set args [lrange $a 1 end]
	switch -- $v {
		waitprompt { q_add_front s_monitor_on; q_add_front s_wait 1; q_add_front s_waittext dos_prompt "A:\\>" 150 }
		dos        { lg "DOS> [lindex $args 0]"; q_add_front s_wait 0.5; q_add_front s_type "[lindex $args 0]\r" }
		waittext   { q_add_front s_waittext [lindex $args 0] [lindex $args 1] [expr {[llength $args] > 2 ? [lindex $args 2] : 30}] }
		waitmm     { q_add_front s_waitmm [expr {[llength $args] > 0 ? [lindex $args 0] : 60}] [expr {[llength $args] > 1 ? [lindex $args 1] : ""}] [expr {[llength $args] > 2 ? 1 : 0}] }
		saltar_a   { q_saltar_a [lindex $args 0]; q_add_front s_wait 0 }
		label      { q_add_front s_wait 0 }
		waitdos    { q_add_front s_waitdos [expr {[llength $args] > 0 ? [lindex $args 0] : 30}] }
		key        {
			set n [expr {[llength $args] > 1 ? [lindex $args 1] : 1}]
			q_add_front s_keys [lindex $args 0] $n
		}
		keyc       { q_add_front s_keyc [string toupper [lindex $args 0]] [lindex $args 1] }
		text       { lg "TEXT '[lindex $args 0]'"; q_add_front s_text [lindex $args 0] }
		wait       { q_add_front s_wait [lindex $args 0] }
		settle     { q_add_front s_settle $::paso [expr {[llength $args] > 0 ? [lindex $args 0] : 1.5}] 40 }
		shot       { q_add_front s_shot [lindex $args 0] }
		pos        { set ::pos [lindex $args 0]; q_add_front s_wait 0 }
		top        { q_add_front s_alextremo UP 0; q_add_front s_wait 0.4; q_add_front s_keys SHIFT+UP 1 }
		bottom     { q_add_front s_alextremo DOWN [lindex $args 0]; q_add_front s_wait 0.4; q_add_front s_keys SHIFT+DOWN 1 }
		hash_guarda { q_add_front s_hash_guarda [lindex $args 0] }
		hash_compara { q_add_front s_hash_compara [lindex $args 0] }
		hash_espera { q_add_front s_hash_espera [lindex $args 0] [expr {[llength $args] > 1 ? [lindex $args 1] : 30}] }
		goto       { q_add_front s_goto [lindex $args 0] }
		paso       { set ::paso [lindex $args 0]; lg "=== PASO [lindex $args 0]"; q_add_front s_wait 0 }
		log        { lg [lindex $args 0]; q_add_front s_wait 0 }
		bp_on      { bp_on; q_add_front s_wait 0 }
		peek       {
			set a [expr "0x[lindex $args 0]"]
			set n [expr {[llength $args] > 1 ? [lindex $args 1] : 16}]
			set s ""
			for {set i 0} {$i < $n} {incr i} { append s [format "%02X " [peek [expr {$a + $i}]]] }
			lg "PEEK [lindex $args 0]: $s"
			q_add_front s_wait 0
		}
		trace      {
			set a [expr "0x[lindex $args 0]"]
			set ::tr_n($a) 0
			set ::tr_lim($a) [expr {[llength $args] > 1 ? [lindex $args 1] : 60}]
			debug set_bp $a {} [list tr_hit $a]
			q_add_front s_wait 0
		}
		regs       {
			lg [format "REGS PC=%04X SP=%04X AF=%04X BC=%04X DE=%04X HL=%04X IX=%04X IY=%04X" [reg PC] [reg SP] [reg AF] [reg BC] [reg DE] [reg HL] [reg IX] [reg IY]]
			q_add_front s_wait 0
		}
		fin        { s_fin; return }
		default    { error "accion desconocida: $a" }
	}
	q_next
}
# (las acciones se ejecutan una a una: s_accion mete sus pasos al principio de la cola y sigue)

# 'trace ADDR [N]': registra las N primeras veces que se ejecuta ADDR (registros, pila y la cadena a la que apunta SP+2)
proc tr_hit {a} {
	if {$::tr_n($a) >= $::tr_lim($a)} { return }
	incr ::tr_n($a)
	set sp [reg SP]
	set ptr [expr {[peek [expr {$sp + 2}]] | ([peek [expr {$sp + 3}]] << 8)}]
	set len [peek [expr {$sp + 4}]]
	set s ""
	for {set i 0} {$i < 14} {incr i} { set c [peek [expr {$ptr + $i}]]; append s [expr {$c >= 32 && $c < 127 ? [format %c $c] : "."}] }
	lg [format "TRACE %04X C=%02X E=%02X ptr=%04X len=%02X \"%s\"" $a [expr {[reg BC] & 255}] [expr {[reg DE] & 255}] $ptr $len $s]
}
proc q_add_front {args} { set ::q [linsert $::q 0 $args] }
# un paso por accion: se expande cuando le toca (asi 'pos'/'paso' usan los valores del momento)
proc q_accion {a} { lappend ::q [list s_accion $a] }
set ::paso inicio

# ---- puntos de ruptura: cuenta cuantas veces se EJECUTA una instruccion en unos rangos de direcciones -------------
# ::P(contar) = lista de rangos hexadecimales 'ini-fin' (p.ej. 3D60-3DDD 5CD0-5CFF). Se pone un 'debug set_bp' en
# CADA direccion del rango (un punto de ruptura solo salta si el PC vale exactamente esa direccion: o sea, al
# empezar a ejecutarse una instruccion que empieza ahi; una direccion en medio de una instruccion no salta nunca).
# Se distingue si el PC esta en la RAM principal (la de la pagina 3: el TPA donde vive MM.COM) o en otro slot
# (BIOS, kernel de DOS...). El comando del punto de ruptura no para el emulador.
set ::bp_ids {}
proc bp_on {} {
	if {![info exists ::P(contar)] || [llength $::P(contar)] == 0} { lg "bp_on: sin ::P(contar)"; return }
	lassign [get_selected_slot 3] ::bp_ps ::bp_ss
	lg "puntos de ruptura: RAM principal = slot $::bp_ps-$::bp_ss"
	# bytes del MM.COM que se esta probando: sirven para distinguir si lo que se ejecuta en esa direccion es el
	# codigo del propio MM.COM (los 4 bytes de memoria coinciden con los del fichero cargado en 0100h) o OTRO programa
	# que ocupa ahora el TPA (COMMAND2.COM cuando MM lanza una orden con [X], HOLA.COM...)
	set ::mm_bytes ""
	if {[info exists ::P(mmcom)] && $::P(mmcom) ne ""} {
		set fh [open $::P(mmcom) rb]
		set ::mm_bytes [read $fh]
		close $fh
		lg "MM.COM de referencia: $::P(mmcom) ([string length $::mm_bytes] bytes)"
	}
	set ::bp_n 0
	foreach r $::P(contar) {
		lassign [split $r -] a b
		for {set x [expr "0x$a"]} {$x <= [expr "0x$b"]} {incr x} {
			lappend ::bp_ids [debug set_bp $x {} [list bp_hit $x]]
			set ::bp_mm($x) 0
			set ::bp_ext($x) 0
			set ::bp_otro($x) 0
			incr ::bp_n
		}
	}
	lg "puntos de ruptura puestos: $::bp_n en $::P(contar)"
}
set ::bp_logs 0
# cada instruccion que empieza en una direccion vigilada cae en uno de tres cajones:
#   mm   = RAM principal y la memoria coincide con el MM.COM de referencia (codigo de MM.COM)
#   ext  = RAM principal pero la memoria NO coincide con MM.COM (otro programa ocupa el TPA: COMMAND2.COM, HOLA.COM)
#   otro = el PC esta en otro slot (BIOS, kernel de DOS...)
set ::bp_err 0
proc bp_hit {x} {
	# el error de un punto de ruptura no se ve (lo traga openMSX): se deja una sola vez en el log
	if {[catch {bp_hit_ $x} err]} {
		if {!$::bp_err} { set ::bp_err 1; lg "ERROR en bp_hit ($x): $err" }
	}
}
proc bp_hit_ {x} {
	if {![pc_in_slot $::bp_ps $::bp_ss]} {
		incr ::bp_otro($x)
		set cl otro
	} else {
		set mem [debug read_block memory $x 4]
		set off [expr {$x - 0x100}]
		# (se compara con hasta 4 bytes; en los ultimos bytes del fichero, con los que queden)
		set n [expr {[string length $::mm_bytes] - $off}]
		if {$n > 4} { set n 4 }
		if {$n > 0 && [string range $::mm_bytes $off [expr {$off + $n - 1}]] eq [string range $mem 0 [expr {$n - 1}]]} {
			incr ::bp_mm($x)
			set cl mm
		} else {
			incr ::bp_ext($x)
			set cl ext
		}
	}
	if {[info exists ::bp_pp($::paso,$cl)]} { incr ::bp_pp($::paso,$cl) } else { set ::bp_pp($::paso,$cl) 1 }
	if {$::bp_logs < 40 && ($cl eq "mm" || ($cl eq "ext" && ![info exists ::bp_visto($::paso,ext)]) || ($cl eq "otro" && $::bp_otro($x) < 2))} {
		incr ::bp_logs
		if {$cl eq "ext"} { set ::bp_visto($::paso,ext) 1 }
		set sp [reg SP]
		binary scan [debug read_block memory $x 8] H* hx
		binary scan [string range $::mm_bytes [expr {$x - 0x100}] [expr {$x - 0x100 + 7}]] H* hf
		lg [format "BP %s en %04X (paso=%s) SP=%04X (SP)=%04X memoria=%s fichero=%s" $cl $x $::paso $sp [peek16 $sp] $hx $hf]
	}
}
proc bp_informe {} {
	set t(mm) 0; set t(ext) 0; set t(otro) 0
	set d(mm) {}; set d(ext) {}; set d(otro) {}
	foreach x [lsort -integer [array names ::bp_mm]] {
		foreach {cl arr} {mm ::bp_mm ext ::bp_ext otro ::bp_otro} {
			set v [set ${arr}($x)]
			if {$v > 0} { incr t($cl) $v; lappend d($cl) [format "%04X=%d" $x $v] }
		}
	}
	lg "BP-INFORME: $::bp_n direcciones vigiladas en $::P(contar)"
	lg "BP-INFORME: (1) ejecuciones del codigo de MM.COM (memoria == fichero): total $t(mm); direcciones: [expr {$d(mm) eq {} ? {NINGUNA} : $d(mm)}]"
	lg "BP-INFORME: (2) ejecuciones de OTRO programa en el TPA (memoria != MM.COM; p.ej. COMMAND2.COM lanzado por X): total $t(ext)"
	lg "BP-INFORME:     direcciones: [expr {$d(ext) eq {} ? {ninguna} : $d(ext)}]"
	lg "BP-INFORME: (3) ejecuciones con el PC en otro slot (BIOS/DOS): total $t(otro); direcciones: [expr {$d(otro) eq {} ? {ninguna} : $d(otro)}]"
	foreach x {0x3D60 0x3D63 0x3D67 0x3D81 0x3DCD 0x3DDF 0x5CD0} {
		if {[info exists ::bp_mm([expr $x])]} {
			lg [format "BP-INFORME: %04X  MM.COM=%d  otro-programa=%d  otro-slot=%d" $x $::bp_mm([expr $x]) $::bp_ext([expr $x]) $::bp_otro([expr $x])]
		}
	}
	foreach k [lsort [array names ::bp_pp]] { lg "BP-INFORME: por paso $k = $::bp_pp($k)" }
}

# ---- monitor de pantallas de texto: deja en el log todo lo que sale en un modo de texto (salida de VER, DIR, CS...)
set ::txt_ultimo ""
set ::mon_on 0
proc s_monitor_on {} { set ::mon_on 1; q_next }
proc monitor_texto {} {
	if {$::mon_on && [string match TEXT* [modo]]} {
		set t [pantalla_texto]
		if {$t ne $::txt_ultimo} {
			set ::txt_ultimo $t
			lg "TEXTO (paso $::paso, modo [modo]):"
			foreach l [split $t "\n"] { if {[string trim $l] ne ""} { lg "   | [string trimright $l]" } }
			if {[string first "Unrecognized command" $t] >= 0} { check dos_error_$::paso 0 "DOS dice 'Unrecognized command': una tecla/RETURN ha caido donde no debia" }
		}
	}
	after time 0.2 monitor_texto
}

# ---------------------------------------------------------------- guion
set ::escenario [expr {[info exists ::P(escenario)] ? $::P(escenario) : "lista"}]
if {$::escenario ne "lista"} {
	lg "escenario $::escenario: [llength $::P(acciones)] acciones"
	set ::pos -1
	foreach a $::P(acciones) { q_accion $a }
	after time 1 monitor_texto
	q_add s_wait 0.5
	q_add s_accion {fin}
} else {
# 1. DOS
q_add s_waittext dos_prompt "A:\\>" 150
q_add s_wait 1
q_add s_type "VER\r"
q_add s_wait 1
q_add volcado_q VER
proc volcado_q {n} { volcado $n; q_next }
# 2. CD y MM
q_add s_type "CD \\ROMS\r"
q_add s_waittext cd_roms "A:\\ROMS>" 30
q_add s_type "MM\r"
q_add s_waitmode_not mm_arranca TEXT80 40
q_add s_wait 3
q_add s_settle lista 2.0 40
q_add s_shot 01_lista
# 3. File info de cada objetivo (el cursor empieza en la entrada 0 = '..\')
foreach t $::P(targets) {
	# (variables con prefijo t_: 'pos' a secas seria la global ::pos que usa s_mover)
	lassign $t t_num t_pos t_slug t_nombre t_esp_lista t_esp_lista83 t_esp_info
	q_add s_objetivo $t_num $t_pos $t_slug $t_nombre $t_esp_lista $t_esp_lista83 $t_esp_info
	q_add s_mover $t_pos
	q_add s_wait 0.5
	q_add s_settle info_$t_num 1.0 20
	q_add s_shot [format "%02d_info_%s" [expr {$t_num + 1}] $t_slug]
}
# 4. salir de MM (Q) y comprobar que DOS recupera el prompt
q_add s_key Q 1
q_add s_waittext mm_sale "A:\\ROMS>" 20
q_add s_shot 99_salida_mm
}

after time 1 q_next
