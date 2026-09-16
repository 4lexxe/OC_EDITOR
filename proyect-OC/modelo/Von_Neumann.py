from bitstring import BitArray

class Memoria:
    def __init__(self, size=256):
        """
        Inicializa la memoria RAM simulada.
        size: número de palabras de 12 bits.
        """
        self.size = size
        # Cada palabra es un BitArray de 12 bits inicializado en 0
        self.ram = [BitArray(uint=0, length=12) for _ in range(size)]

    def leer(self, direccion):
        """
        Devuelve el contenido de la dirección de memoria.
        """
        if 0 <= direccion < self.size:
            return self.ram[direccion].copy()
        else:
            raise IndexError("Dirección de memoria fuera de rango")

    def escribir(self, direccion, valor):
        """
        Escribe un valor de 12 bits en la dirección especificada.
        """
        if 0 <= direccion < self.size:
            # & 0xFFF asegura que el valor sea de 12 bits
            self.ram[direccion] = BitArray(uint=valor & 0xFFF, length=12)
        else:
            raise IndexError("Dirección de memoria fuera de rango, direccion invalida")

    def dump(self):
        """
        Devuelve toda la memoria en formato binario para inspección.
        """
        return [palabra.bin for palabra in self.ram]



class VonNeuman:
    def __init__(self):
        # Registros públicos (usar directamente cpu.ACC, cpu.F, ...)
        self.ACC = BitArray(uint=0, length=12)   # Acumulador (12 bits)
        self.F   = BitArray(uint=0, length=1)    # Flip-flop de rotación (Taub, cap. 9)
        self.GPR = BitArray(uint=0, length=12)   # Registro general (12 bits)
        self.M   = BitArray(uint=0, length=12)   # Registro de memoria (12 bits)
        self.MAR = BitArray(uint=0, length=8)   # Memory Address Register
        self.PC  = BitArray(uint=0, length=8)   # Program Counter
        self.OPR = BitArray(uint=0, length=4)   # registro de operación (apuntes / traza)
        self.GPR_AD = BitArray(uint=0, length=8)  # campo dirección (visualización)
        self.GPR_OP = BitArray(uint=0, length=4)  # campo operando (visualización)
        self.RAM = Memoria()                     # RAM: instancia de Memoria (array de BitArray)

    # Nota: quitadas las funciones get_/set_. Usar los atributos públicos: ACC, F, GPR, M, RAM
    # Formato IR (apuntes / Ejemplo 1): 12 bits = 4 bits código OP + 8 bits dirección AD.

    def _sync_ir_fields(self):
        """Actualiza GPR(OP) y GPR(AD) según el contenido actual de GPR."""
        w = self.GPR.uint & 0xFFF
        op_n = (w >> 8) & 0xF
        ad_n = w & 0xFF
        self.GPR_OP = BitArray(uint=op_n, length=4)
        self.GPR_AD = BitArray(uint=ad_n, length=8)

    def ROL_F_ACC(self):
        concatenacion = self.F + self.ACC
        concatenacion.rol(1)
        # concatenacion[0] es un bool -> convertir a BitArray de 1 bit
        self.F = BitArray([concatenacion[0]])
        self.ACC = concatenacion[1:]
    
    def ROR_F_ACC(self):
        concatenacion = self.F + self.ACC
        concatenacion.ror(1)
        self.F = BitArray([concatenacion[0]])
        self.ACC = concatenacion[1:]
    
    def NOT_ACC(self):
        self.ACC = ~self.ACC
    
    def NOT_F(self):
        self.F = ~self.F

    def INC_ACC(self):
        suma = (self.ACC.uint + 1) & 0xFFF
        self.ACC = BitArray(uint=suma, length=12)
    
    def INC_GPR(self):
        suma = (self.GPR.uint + 1) & 0xFFF
        self.GPR = BitArray(uint=suma, length=12)
        self._sync_ir_fields()

    def ACC_TO_GPR(self):
        self.GPR = self.ACC.copy()
        self._sync_ir_fields()

    def GPR_TO_ACC(self):
        self.ACC = self.GPR.copy()
    
    def SUM_ACC_GPR(self):
        # F solo cambia mediante rotaciones, borrado y complemento (Taub 9.1-1).
        suma = self.ACC.uint + self.GPR.uint
        
        self.ACC = BitArray(uint=suma & 0xFFF, length=12)

    def ZERO_TO_ACC(self):
        self.ACC = BitArray(uint=0, length=12)

    def ZERO_TO_F(self):
        self.F = BitArray(uint=0, length=1)

    def GPR_AD_TO_MAR(self):
        # Campo AD (8 bits bajos del IR / GPR) → MAR; lectura en M (Ejemplo 1 y ejercicios directos).
        ad = self.GPR.uint & 0xFF
        self.MAR = BitArray(uint=ad, length=8)
        self._sync_ir_fields()
        self.M = self.RAM.leer(ad)

    def GPR_TO_M(self):
        self.RAM.escribir(self.MAR.uint, self.GPR.uint)
        self.M = self.GPR.copy()
    
    def M_TO_GPR(self):
        self.GPR = self.M.copy()
        self._sync_ir_fields()

    def M_TO_ACC(self):
        self.ACC = self.M.copy()

    def PC_TO_MAR(self):
        # Solo captación de dirección y dato en M; GPR se carga en el siguiente paso (filmina Ej. 1).
        self.MAR = BitArray(uint=self.PC.uint & 0xFF, length=8)
        self.M = self.RAM.leer(self.MAR.uint)

    def INC_PC(self):
        val = (self.PC.uint + 1) & 0xFF
        self.PC = BitArray(uint=val, length=8)

    def GPR_OP_TO_OPR(self):
        op_n = (self.GPR.uint >> 8) & 0xF
        self.OPR = BitArray(uint=op_n, length=4)
        self._sync_ir_fields()
    

    

# PRUEBAS
"""
cpu = VonNeuman()

def inicializar_cpu(acc=12, f=1, gpr=3, m=0):
    cpu.ACC = BitArray(uint=acc & 0xFFF, length=12)
    cpu.F = BitArray(uint=f & 0x1, length=1)
    cpu.GPR = BitArray(uint=gpr & 0xFFF, length=12)
    cpu.M = BitArray(uint=m & 0xFFF, length=12)


def mostrar_estado(etiqueta):
    print(etiqueta)
    print("ACC:", cpu.ACC.bin)
    print("F  :", cpu.F.bin)
    print("GPR:", cpu.GPR.bin)
    print("M  :", cpu.M.bin)
    print()

mostrar_estado("Estado inicial:")

# Incrementar ACC
cpu.ACC_incrementar_a_ACC()
mostrar_estado("Después de ACC_incrementar_a_ACC():")

# NOT en ACC
cpu.NOT_ACC()
mostrar_estado("Después de NOT_ACC():")

# ROL con F
cpu.ROL_F_ACC()
mostrar_estado("Después de ROL_F_ACC():")

# ROR con F
cpu.ROR_F_ACC()
mostrar_estado("Después de ROR_F_ACC():")

# Copiar ACC a GPR
cpu.ACC_a_GPR()
mostrar_estado("Después de ACC_a_GPR():")

# Cambiar ACC y copiar desde GPR
cpu.ACC_incrementar_a_ACC()
cpu.GPR_a_ACC()
mostrar_estado("Después de GPR_a_ACC():")

"""