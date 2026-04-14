from __future__ import annotations

from dataclasses import dataclass


MASK64 = (1 << 64) - 1


@dataclass
class ExecOperation:
    opcode: str
    op0: int
    op1: int
    destPhysicalRegisterId : int


@dataclass
class ALUResult:
    value: int = 0
    exception: bool = False
    destPhysicalRegisterId: int | None = None

    def NOP() -> ALUResult:
        return ALUResult(value=None, exception=False, destPhysicalRegisterId=None)
    
    def isNop(self):
        return self.value is None and \
              self.exception == False and \
              self.destPhysicalRegisterId is None

    def __post_init__(self):
        if self.value is not None:
            self.value &= MASK64
    
    def __eq__(self, other):
        if isinstance(other, ALUResult):
            return self.value == other.value and \
              self.exception == other.exception and \
              self.destPhysicalRegisterId == other.destPhysicalRegisterId
        else:
            raise Exception("overloading fucntion does not support such comparision")



class ALU:
    """Minimal pipelined execution unit for the homework integer pipeline."""

    def __init__(self, numPipelineRegisters: int = 1):
        self.numPipelineRegisters = numPipelineRegisters
        self._pipelineRegisters = [ALUResult.NOP()] * self.numPipelineRegisters
        self._nextResult : ALUResult = None
        self._currentResult : ALUResult = None

    def propagate(self, operation: ExecOperation | None):
        self._nextResult = self._execute(operation)
        self._currentResult = self._pipelineRegisters[-1]

    def getResult(self) -> ALUResult:
        return self._currentResult

    def latch(self) -> ALUResult | None:
        completed_result = self._pipelineRegisters[-1]

        for idx in range(self.numPipelineRegisters - 1, 0, -1):
            self._pipelineRegisters[idx] = self._pipelineRegisters[idx - 1]

        self._pipelineRegisters[0] = self._nextResult
        self._nextResult = None

        return completed_result

    def _execute(self, operation: ExecOperation) -> ALUResult:
        if operation is None:
            return ALUResult.NOP()
        

        opcode = operation.opcode
        op0 = operation.op0
        op1 = operation.op1
        dest = operation.destPhysicalRegisterId


        if opcode == "add":
            return ALUResult(value=op0 + op1, exception=False, destPhysicalRegisterId=dest)

        if opcode == "sub":
            return ALUResult(value=op0 - op1, exception=False, destPhysicalRegisterId=dest)

        if opcode == "mulu":
            return ALUResult(value=op0 * op1, exception=False, destPhysicalRegisterId=dest)

        if opcode == "divu":
            if op1 == 0:
                return ALUResult(value=0, exception=True, destPhysicalRegisterId=dest)
            return ALUResult(value=op0 // op1, exception=False, destPhysicalRegisterId=dest)

        if opcode == "remu":
            if op1 == 0:
                return ALUResult(value=0, exception=True, destPhysicalRegisterId=dest)
            return ALUResult(value=op0 % op1, exception=False, destPhysicalRegisterId=dest)

        raise ValueError(f"Unsupported opcode: {opcode}")
