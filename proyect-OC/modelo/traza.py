"""
Simulación secuencial de microoperaciones para tabla de traza (apuntes).
No altera la CPU principal: se trabaja sobre un clon.
"""
from __future__ import annotations

from bitstring import BitArray

from modelo.Von_Neumann import VonNeuman
from modelo.ciclos import ejecutar_ciclo
from modelo.seguimiento_f import SeguimientoF
from compilador.AnalizadorSintactico import parsear_ciclo, preprocesar_linea_microop

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
    return str(v & 0xFF) if mar_pc_decimal else f"{v & 0xFF:02X}"


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
    if not mem_log:
        return "Sin accesos a RAM. M es la palabra de memoria seleccionada por MAR."
    lines = ["Accesos a RAM · direcciones de 8 bits y palabras de 12 bits (hex)", ""]
    for evento in mem_log:
        accion = "Escritura" if evento["tipo"] == "escritura" else "Lectura"
        lines.append(f"Ciclo {evento['ciclo']:>2} · {accion} · M[${evento['dir']:02X}] = ${evento['dato']:03X}")
    lines += ["", "Memoria al finalizar la traza:"]
    for direccion in sorted({evento["dir"] for evento in mem_log}):
        lines.append(f"M[${direccion:02X}] = ${cpu.RAM.leer(direccion).uint:03X}")
    return "\n".join(lines)


_PREFIJO_FETCH = ("PC -> MAR", "M -> GPR, PC+1 -> PC", "GPR(OP) -> OPR")


def simular_traza(
    codigo: str,
    cpu_base: VonNeuman,
    *,
    prefijo_fetch: bool = False,
    mar_pc_decimal: bool = False,
    omitir_repetidos: bool = False,
    estado_inicial: bool = False,
) -> tuple[list[dict], str | None, str]:
    """Una fila por ciclo de reloj (línea), con todas sus microoperaciones.

    El ciclo de búsqueda tiene tres filas. Solo se agrega si se solicita y
    el código todavía no comienza con PC->MAR. La CPU recibida no se modifica.
    Cada fila conserva valores completos y cambios para inspección y exportación.
    """
    lineas = [(numero, preprocesar_linea_microop(linea))
              for numero, linea in enumerate(codigo.splitlines(), 1)]
    lineas = [(numero, linea) for numero, linea in lineas if linea]
    if prefijo_fetch and lineas:
        try:
            ya_tiene_fetch = parsear_ciclo(lineas[0][1])[0] == "PC_TO_MAR"
        except (ValueError, IndexError):
            ya_tiene_fetch = False
        if not ya_tiene_fetch:
            lineas = [(None, linea) for linea in _PREFIJO_FETCH] + lineas

    cpu = clonar_cpu(cpu_base)
    seguimiento_f = SeguimientoF()
    filas = []
    mem_log = []
    anterior = _fila_estado(0, "Estado inicial", cpu, mar_pc_decimal=mar_pc_decimal)
    if estado_inicial:
        anterior.update(fase="Inicial", linea=None, ops=[], cambios=[],
                        valores={k: anterior[k] for k in _COLUMNAS_SIN_REPETIR}, accesos=[],
                        procedencia_f=seguimiento_f.estado())
        filas.append(dict(anterior))
    fase = "Ejecución"
    error = None
    for numero, linea in lineas:
        ciclo = len(filas) + (0 if estado_inicial else 1)
        try:
            ops = parsear_ciclo(linea)
            direccion_anterior = cpu.MAR.uint
            ejecutar_ciclo(cpu, ops)
        except (ValueError, IndexError, TypeError) as exc:
            origen = f"Línea {numero}" if numero is not None else f"Búsqueda, ciclo {ciclo}"
            error = f"{origen}: {exc}"
            break
        if "PC_TO_MAR" in ops:
            fase = "Búsqueda"
        texto = ", ".join(_OP_TEXTO[op] for op in ops)
        fila = _fila_estado(ciclo, texto, cpu, mar_pc_decimal=mar_pc_decimal)
        accesos = []
        for op in ops:
            if op in ("PC_TO_MAR", "GPR_AD_TO_MAR", "GPR_TO_M"):
                escribe = op == "GPR_TO_M"
                direccion = direccion_anterior if escribe else cpu.MAR.uint
                evento = {"ciclo": ciclo, "tipo": "escritura" if escribe else "lectura",
                          "dir": direccion, "dato": cpu.RAM.leer(direccion).uint}
                accesos.append(evento)
                mem_log.append(evento)
        fila.update(
            fase=fase, linea=numero, ops=ops, accesos=accesos,
            procedencia_f=seguimiento_f.avanzar(ops, ciclo),
            valores={k: fila[k] for k in _COLUMNAS_SIN_REPETIR},
            cambios=[k for k in _COLUMNAS_SIN_REPETIR if fila[k] != anterior[k]],
        )
        filas.append(fila)
        anterior = fila
        if "GPR_OP_TO_OPR" in ops:
            fase = "Ejecución"

    if omitir_repetidos:
        filas = compactar_filas_traza(filas)
    return filas, error, _formatear_panel_memoria_traza(mem_log, cpu)
