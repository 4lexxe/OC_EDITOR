"""
Simulación secuencial de microoperaciones para tabla de traza (apuntes).
No altera la CPU principal: se trabaja sobre un clon.
"""
from __future__ import annotations

from bitstring import BitArray

from modelo.Von_Neumann import VonNeuman

# Texto mostrado en la columna «Microoperación» (notación apuntes)
_OP_TEXTO = {
    "INC_ACC": "ACC+1 -> ACC",
    "INC_GPR": "GPR+1 -> GPR",
    "INC_PC": "PC+1 -> PC",
    "NOT_ACC": "ACC! -> ACC",
    "NOT_F": "F! -> F",
    "ROL_F_ACC": "ROL F, ACC",
    "ROR_F_ACC": "ROR F, ACC",
    "SUM_ACC_GPR": "GPR+ACC -> ACC",
    "ACC_TO_GPR": "ACC -> GPR",
    "GPR_TO_ACC": "GPR -> ACC",
    "ZERO_ACC": "0 -> ACC",
    "ZERO_F": "0 -> F",
    "GPR_AD_TO_MAR": "GPR(AD) -> MAR",
    "GPR_TO_M": "GPR -> M",
    "M_TO_GPR": "M -> GPR",
    "M_TO_ACC": "M -> ACC",
    "PC_TO_MAR": "PC -> MAR",
    "GPR_OP_TO_OPR": "GPR(OP) -> OPR",
}


def _fmt12(ba: BitArray) -> str:
    return f"{ba.uint & 0xFFF:03X}"


def _fmt_f(ba: BitArray) -> str:
    return str(ba.uint & 1)


def _fmt_ir_op(ba: BitArray) -> str:
    """Campo OP (4 bits), estilo filmina Ej. 1: «9»."""
    return f"{ba.uint & 0xF:X}"


def _fmt_ir_ad(ba: BitArray) -> str:
    """Campo AD (8 bits), hex 2 dígitos: «83», «20»."""
    return f"{ba.uint & 0xFF:02X}"


def clonar_cpu(cpu: VonNeuman) -> VonNeuman:
    n = VonNeuman()
    n.ACC = cpu.ACC.copy()
    n.F = cpu.F.copy()
    n.GPR = cpu.GPR.copy()
    n._sync_ir_fields()
    n.M = cpu.M.copy()
    n.MAR = cpu.MAR.copy()
    n.PC = cpu.PC.copy()
    n.OPR = cpu.OPR.copy()
    for i in range(cpu.RAM.size):
        n.RAM.ram[i] = cpu.RAM.ram[i].copy()
    return n


def _fmt_pc_mar(cpu: VonNeuman, mar_pc_decimal: bool, attr: str) -> str:
    ba = getattr(cpu, attr)
    v = ba.uint & 0xFFF
    return str(v) if mar_pc_decimal else _fmt12(ba)


def _fila_estado(
    ciclo: int,
    texto_op: str,
    cpu: VonNeuman,
    *,
    mar_pc_decimal: bool = False,
) -> dict:
    return {
        "ciclo": ciclo,
        "micro": texto_op,
        "PC": _fmt_pc_mar(cpu, mar_pc_decimal, "PC"),
        "MAR": _fmt_pc_mar(cpu, mar_pc_decimal, "MAR"),
        "GPR": _fmt12(cpu.GPR),
        "GPR_OP": _fmt_ir_op(cpu.GPR_OP),
        "GPR_AD": _fmt_ir_ad(cpu.GPR_AD),
        "OPR": _fmt_ir_op(cpu.OPR),
        "ACC": _fmt12(cpu.ACC),
        "F": _fmt_f(cpu.F),
        "M": _fmt12(cpu.M),
    }


# Columnas donde se omiten celdas si el valor es igual al ciclo anterior (como tablas de apuntes).
_COLUMNAS_SIN_REPETIR = (
    "PC",
    "MAR",
    "GPR",
    "GPR_OP",
    "GPR_AD",
    "OPR",
    "ACC",
    "F",
    "M",
)


def compactar_filas_traza(filas: list[dict]) -> list[dict]:
    """Deja en blanco cada celda que no cambió respecto al renglón anterior."""
    prev: dict[str, str | None] = dict.fromkeys(_COLUMNAS_SIN_REPETIR, None)
    out: list[dict] = []
    for f in filas:
        row = dict(f)
        for k in _COLUMNAS_SIN_REPETIR:
            val = row[k]
            if prev[k] == val:
                row[k] = ""
            else:
                prev[k] = val
        out.append(row)
    return out


def _formatear_panel_memoria_traza(mem_log: list[dict], cpu: VonNeuman) -> str:
    """Texto para la UI: lecturas detectadas y valores finales en esas direcciones."""
    if not mem_log:
        return (
            "Sin lecturas desde RAM en esta traza.\n\n"
            "Aquí se registran los accesos que cargan el registro M desde la RAM:\n"
            "  • PC -> MAR (fetch de instrucción)\n"
            "  • GPR(AD) -> MAR (acceso a operando)\n\n"
            "El modelo no escribe en RAM desde microoperaciones; lo que importa es lo "
            "que cargaste en el panel «Memoria RAM» antes de simular."
        )
    lines = ["Lecturas desde memoria (dirección y palabra en hex, 12 bits):", ""]
    for e in mem_log:
        lines.append(f"  Ciclo {e['ciclo']}: lectura @{e['dir']:03X}  →  palabra {e['dato']:03X}")
    dirs = sorted({e["dir"] for e in mem_log})
    lines += ["", "Contenido actual de esas celdas al finalizar la traza:", ""]
    for d in dirs:
        v = cpu.RAM.leer(d).uint & 0xFFF
        lines.append(f"  @{d:03X}  =  {v:03X}")
    return "\n".join(lines)


# Tres líneas de fetch como en Generador / filminas (al parsear, son 4 microops).
_PREFIJO_FETCH = (
    "PC -> MAR\n"
    "M -> GPR, PC+1 -> PC\n"
    "GPR(OP) -> OPR\n"
)


def simular_traza(
    codigo: str,
    cpu_base: VonNeuman,
    *,
    prefijo_fetch: bool = False,
    mar_pc_decimal: bool = False,
    omitir_repetidos: bool = False,
    estado_inicial: bool = False,
) -> tuple[list[dict], str | None, str]:
    """
    Devuelve (filas, error, texto_memoria). Cada fila es el estado *después* de esa microoperación.

    prefijo_fetch: antepone el ciclo de captación (PC→MAR, M→GPR+PC, GPR(OP)→OPR).
    mar_pc_decimal: muestra PC y MAR en decimal 0…4095 (como «83» en algunas filminas).
    omitir_repetidos: celdas en blanco si el registro no cambió respecto al ciclo anterior.
    estado_inicial: si True, primera fila ciclo 0 «Estado inicial» antes de cualquier μop (como en parciales).
    texto_memoria: resumen de lecturas RAM (PC→MAR, GPR(AD)→MAR) y valores finales en esas direcciones.
    """
    texto = codigo.replace("\r\n", "\n")
    if prefijo_fetch:
        texto = _PREFIJO_FETCH + texto
    lineas = texto.split("\n")
    from compilador.AnalizadorSintactico import parser, preprocesar_linea_microop

    dispatch = {
        "INC_ACC": VonNeuman.INC_ACC,
        "INC_GPR": VonNeuman.INC_GPR,
        "NOT_ACC": VonNeuman.NOT_ACC,
        "NOT_F": VonNeuman.NOT_F,
        "ROL_F_ACC": VonNeuman.ROL_F_ACC,
        "ROR_F_ACC": VonNeuman.ROR_F_ACC,
        "SUM_ACC_GPR": VonNeuman.SUM_ACC_GPR,
        "ACC_TO_GPR": VonNeuman.ACC_TO_GPR,
        "GPR_TO_ACC": VonNeuman.GPR_TO_ACC,
        "ZERO_ACC": VonNeuman.ZERO_TO_ACC,
        "ZERO_F": VonNeuman.ZERO_TO_F,
        "GPR_AD_TO_MAR": VonNeuman.GPR_AD_TO_MAR,
        "GPR_TO_M": VonNeuman.GPR_TO_M,
        "M_TO_GPR": VonNeuman.M_TO_GPR,
        "M_TO_ACC": VonNeuman.M_TO_ACC,
        "PC_TO_MAR": VonNeuman.PC_TO_MAR,
        "INC_PC": VonNeuman.INC_PC,
        "GPR_OP_TO_OPR": VonNeuman.GPR_OP_TO_OPR,
    }

    c = clonar_cpu(cpu_base)
    filas: list[dict] = []
    mem_log: list[dict] = []
    ciclo = 0

    if estado_inicial:
        filas.append(_fila_estado(0, "Estado inicial", c, mar_pc_decimal=mar_pc_decimal))

    for num_linea, linea in enumerate(lineas, start=1):
        linea = preprocesar_linea_microop(linea)
        if not linea or linea.startswith("#"):
            continue
        try:
            instr = parser.parse(linea)
        except Exception as e:
            return filas, f"Línea {num_linea}: error al parsear ({e})", _formatear_panel_memoria_traza(mem_log, c)

        if not instr:
            return filas, f"Línea {num_linea}: sintaxis inválida", _formatear_panel_memoria_traza(mem_log, c)

        ops_linea = [t[0] for t in instr if t is not None and t[0] is not None]
        if not ops_linea:
            return (
                filas,
                f"Línea {num_linea}: sin operaciones reconocidas",
                _formatear_panel_memoria_traza(mem_log, c),
            )

        for op in ops_linea:
            if op not in dispatch:
                return (
                    filas,
                    f"Línea {num_linea}: microoperación no soportada en traza: {op}",
                    _formatear_panel_memoria_traza(mem_log, c),
                )
            try:
                dispatch[op](c)
            except Exception as e:
                return filas, f"Línea {num_linea} ({op}): {e}", _formatear_panel_memoria_traza(mem_log, c)
            ciclo += 1
            texto = _OP_TEXTO.get(op, op)
            if op == "PC_TO_MAR":
                mem_log.append(
                    {
                        "ciclo": ciclo,
                        "dir": c.MAR.uint & 0xFFF,
                        "dato": c.M.uint & 0xFFF,
                    }
                )
            elif op == "GPR_AD_TO_MAR":
                mem_log.append(
                    {
                        "ciclo": ciclo,
                        "dir": c.MAR.uint & 0xFFF,
                        "dato": c.M.uint & 0xFFF,
                    }
                )
            filas.append(_fila_estado(ciclo, texto, c, mar_pc_decimal=mar_pc_decimal))

    mem_txt = _formatear_panel_memoria_traza(mem_log, c)
    if filas and omitir_repetidos:
        filas = compactar_filas_traza(filas)

    return filas, None, mem_txt
