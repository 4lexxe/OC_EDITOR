"""Motor de validación y verificación de soluciones para ejercicios de microprogramación.
Ejecuta la secuencia de microoperaciones provista por el alumno en múltiples casos de prueba
y compara los resultados de registros y memoria contra los valores esperados.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from bitstring import BitArray

from compilador.AnalizadorSintactico import parsear_ciclo, preprocesar_linea_microop
from modelo.Von_Neumann import VonNeuman
from modelo.ciclos import ejecutar_ciclo
from modelo.seguimiento_f import analizar_f
from modelo.ejercicios import obtener_ejercicio_por_id, Ejercicio, CasoPrueba


def _formatear_hex(val: int, bits: int = 12) -> str:
    hex_len = (bits + 3) // 4
    return f"0x{val & ((1 << bits) - 1):0{hex_len}X}"


def validar_solucion_ejercicio(ejercicio_id: str, codigo_usuario: str) -> Dict[str, Any]:
    ej = obtener_ejercicio_por_id(ejercicio_id)
    if not ej:
        return {
            "ok": False,
            "error": f"Ejercicio con ID '{ejercicio_id}' no encontrado.",
            "casos_aprobados": 0,
            "casos_totales": 0,
            "detalles_casos": [],
            "feedback": "El ejercicio seleccionado no existe."
        }

    codigo_limpio = (codigo_usuario or "").strip()
    if not codigo_limpio:
        return {
            "ok": False,
            "error": "El código está vacío. Escribí tu secuencia de microoperaciones para verificar.",
            "casos_aprobados": 0,
            "casos_totales": len(ej.get("casos_prueba", [])),
            "detalles_casos": [],
            "feedback": "Escribí al menos una microoperación (por ejemplo `ACC! -> ACC` o `GPR(AD) -> MAR`)."
        }

    # Pre-parsear sintaxis de todas las líneas
    lineas_crudas = codigo_limpio.split("\n")
    ciclos_parsed: List[List[str]] = []
    for idx, raw_line in enumerate(lineas_crudas, start=1):
        linea = preprocesar_linea_microop(raw_line)
        if not linea:
            continue
        try:
            ops = parsear_ciclo(linea)
            if not ops:
                return {
                    "ok": False,
                    "error": f"Error de sintaxis en la línea {idx}: '{raw_line.strip()}'",
                    "casos_aprobados": 0,
                    "casos_totales": len(ej.get("casos_prueba", [])),
                    "detalles_casos": [],
                    "feedback": f"Verificá la sintaxis de la línea {idx}. Recordá la notación de la cátedra (ej: `ACC+1 -> ACC`, `ROR F, ACC`, `M -> GPR`)."
                }
            ciclos_parsed.append(ops)
        except Exception as ex:
            return {
                "ok": False,
                "error": f"Error de sintaxis en la línea {idx}: {ex}",
                "casos_aprobados": 0,
                "casos_totales": len(ej.get("casos_prueba", [])),
                "detalles_casos": [],
                "feedback": f"La línea {idx} no corresponde a una microoperación válida de la arquitectura Von Neumann básica."
            }

    if not ciclos_parsed:
        return {
            "ok": False,
            "error": "No se encontraron microoperaciones válidas para ejecutar.",
            "casos_aprobados": 0,
            "casos_totales": len(ej.get("casos_prueba", [])),
            "detalles_casos": [],
            "feedback": "Ingresá microoperaciones ejecutables."
        }

    analisis_f = analizar_f(ciclos_parsed)
    if ej.get("sin_memoria") and any(op in {"PC_TO_MAR", "M_TO_GPR", "M_TO_ACC", "GPR_TO_M", "GPR_AD_TO_MAR"}
                                    for ops in ciclos_parsed for op in ops):
        return {"ok": False, "error": "Este ejercicio pide solo ejecución en modo implicado, sin accesos a RAM.",
                "feedback": "Quitá la búsqueda y los accesos a memoria: usá ACC, GPR y F como indica la consigna.",
                "casos_aprobados": 0, "casos_totales": len(ej.get("casos_prueba", [])),
                "detalles_casos": [], "analisis_f": analisis_f}

    casos = ej.get("casos_prueba", [])
    detalles_casos: List[Dict[str, Any]] = []
    todos_pasaron = True
    primer_error_msg = ""
    ciclos_totales_usados = len(ciclos_parsed)

    for i, caso in enumerate(casos, start=1):
        cpu = VonNeuman()
        
        # Inicializar registros
        regs = caso.get("registros", {})
        if "PC" in regs:
            cpu.PC = BitArray(uint=regs["PC"] & 0xFF, length=8)
        if "ACC" in regs:
            cpu.ACC = BitArray(uint=regs["ACC"] & 0xFFF, length=12)
        if "GPR" in regs:
            cpu.GPR = BitArray(uint=regs["GPR"] & 0xFFF, length=12)
            cpu._sync_ir_fields()
        if "F" in regs:
            cpu.F = BitArray(uint=regs["F"] & 0x1, length=1)
        if "M" in regs:
            cpu.M = BitArray(uint=regs["M"] & 0xFFF, length=12)

        # Inicializar memoria RAM
        mem_init = caso.get("memoria", {})
        for addr, val in mem_init.items():
            cpu.RAM.escribir(addr, val & 0xFFF)

        # Ejecutar secuencia
        error_ejecucion = None
        for ciclo_idx, ops in enumerate(ciclos_parsed, start=1):
            try:
                ejecutar_ciclo(cpu, ops)
            except Exception as ex:
                error_ejecucion = f"Error en ciclo {ciclo_idx} ({' · '.join(ops)}): {ex}"
                break

        detalle: Dict[str, Any] = {
            "caso_num": i,
            "nombre": caso.get("nombre", f"Caso de prueba {i}"),
            "paso": False,
            "error_msg": error_ejecucion,
            "esperado": {},
            "obtenido": {},
            "discrepancias": [],
            "f_inicial": regs.get("F", 0),
            "f_final": cpu.F.uint,
        }

        if error_ejecucion:
            todos_pasaron = False
            detalle["discrepancias"].append(error_ejecucion)
            if not primer_error_msg:
                primer_error_msg = error_ejecucion
            detalles_casos.append(detalle)
            continue

        # Validar registros esperados
        caso_ok = True
        esp_regs = caso.get("esperado_registros", {})
        for r_name, r_exp in esp_regs.items():
            val_exp = r_exp & (0x1 if r_name == "F" else 0xFF if r_name == "PC" else 0xFFF)
            val_obt = getattr(cpu, r_name).uint if hasattr(cpu, r_name) else 0
            detalle["esperado"][r_name] = _formatear_hex(val_exp, 1 if r_name == "F" else 8 if r_name == "PC" else 12)
            detalle["obtenido"][r_name] = _formatear_hex(val_obt, 1 if r_name == "F" else 8 if r_name == "PC" else 12)
            if val_obt != val_exp:
                caso_ok = False
                msg = f"{r_name}: esperado {_formatear_hex(val_exp)}, obtenido {_formatear_hex(val_obt)} (decimal {val_exp} vs {val_obt})"
                detalle["discrepancias"].append(msg)
                if not primer_error_msg:
                    primer_error_msg = f"En {caso.get('nombre')}: {msg}"

        # Validar memoria esperada
        esp_mem = caso.get("esperado_memoria", {})
        for addr, val_exp in esp_mem.items():
            val_exp_masked = val_exp & 0xFFF
            raw_mem = cpu.RAM.leer(addr)
            val_obt = raw_mem.uint if hasattr(raw_mem, "uint") else int(raw_mem)
            val_obt &= 0xFFF
            addr_str = f"M[{_formatear_hex(addr, 8)}]"
            detalle["esperado"][addr_str] = _formatear_hex(val_exp_masked, 12)
            detalle["obtenido"][addr_str] = _formatear_hex(val_obt, 12)
            if val_obt != val_exp_masked:
                caso_ok = False
                msg = f"{addr_str}: esperado {_formatear_hex(val_exp_masked)}, obtenido {_formatear_hex(val_obt)} (decimal {val_exp_masked} vs {val_obt})"
                detalle["discrepancias"].append(msg)
                if not primer_error_msg:
                    primer_error_msg = f"En {caso.get('nombre')}: {msg}"

        detalle["paso"] = caso_ok
        if not caso_ok:
            todos_pasaron = False
        detalles_casos.append(detalle)

    aprobados = sum(1 for d in detalles_casos if d["paso"])
    
    if todos_pasaron:
        feedback = f"Tu secuencia aprobó los {len(casos)} casos de prueba en {ciclos_totales_usados} ciclos."
    else:
        feedback = f"⚠️ Se aprobaron {aprobados} de {len(casos)} casos de prueba. {primer_error_msg}"

    return {
        "ok": todos_pasaron,
        "ejercicio_id": ejercicio_id,
        "titulo": ej.get("titulo", ""),
        "dificultad": ej.get("dificultad", ""),
        "ciclos_usados": ciclos_totales_usados,
        "casos_totales": len(casos),
        "casos_aprobados": aprobados,
        "detalles_casos": detalles_casos,
        "feedback": feedback,
        "analisis_f": analisis_f,
    }
