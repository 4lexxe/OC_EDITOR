"""Ejecución de un ciclo de reloj: todas sus entradas usan el estado anterior."""
from copy import deepcopy

from modelo.Von_Neumann import VonNeuman


OPERACIONES = {
    "INC_ACC": ("INC_ACC", ("ACC",)),
    "INC_GPR": ("INC_GPR", ("GPR",)),
    "INC_PC": ("INC_PC", ("PC",)),
    "NOT_ACC": ("NOT_ACC", ("ACC",)),
    "NOT_F": ("NOT_F", ("F",)),
    "ROL_F_ACC": ("ROL_F_ACC", ("ACC", "F")),
    "ROR_F_ACC": ("ROR_F_ACC", ("ACC", "F")),
    "SUM_ACC_GPR": ("SUM_ACC_GPR", ("ACC",)),
    "ACC_TO_GPR": ("ACC_TO_GPR", ("GPR",)),
    "GPR_TO_ACC": ("GPR_TO_ACC", ("ACC",)),
    "ZERO_ACC": ("ZERO_TO_ACC", ("ACC",)),
    "ZERO_F": ("ZERO_TO_F", ("F",)),
    "GPR_AD_TO_MAR": ("GPR_AD_TO_MAR", ("MAR", "M")),
    "GPR_TO_M": ("GPR_TO_M", ("M",)),
    "M_TO_GPR": ("M_TO_GPR", ("GPR",)),
    "M_TO_ACC": ("M_TO_ACC", ("ACC",)),
    "PC_TO_MAR": ("PC_TO_MAR", ("MAR", "M")),
    "GPR_OP_TO_OPR": ("GPR_OP_TO_OPR", ("OPR",)),
}


def validar_ciclo(ops: list[str]) -> None:
    """Rechaza operaciones desconocidas y escrituras simultáneas en conflicto."""
    destinos = set()
    for op in ops:
        if op not in OPERACIONES:
            raise ValueError(f"Microoperación no soportada: {op}")
        _, escribe = OPERACIONES[op]
        conflicto = destinos.intersection(escribe)
        if conflicto:
            raise ValueError("Dos operaciones escriben " + ", ".join(sorted(conflicto)) +
                             " en el mismo ciclo. Separalas en líneas distintas.")
        destinos.update(escribe)


def ejecutar_ciclo(cpu: VonNeuman, ops: list[str]) -> None:
    """Valida conflictos antes de escribir; una línea equivale a un ciclo."""
    validar_ciclo(ops)
    if len(ops) == 1:
        getattr(cpu, OPERACIONES[ops[0]][0])()
        return
    resultados = []
    for op in ops:
        temporal = deepcopy(cpu)
        metodo, escribe = OPERACIONES[op]
        getattr(temporal, metodo)()
        resultados.append((op, escribe, temporal))
    for op, escribe, temporal in resultados:
        for registro in escribe:
            setattr(cpu, registro, getattr(temporal, registro).copy())
        if op == "GPR_TO_M":
            cpu.RAM.escribir(temporal.MAR.uint, temporal.M.uint)
    cpu._sync_ir_fields()
