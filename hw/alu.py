from dataclasses import dataclass


MASK64 = (1 << 64) - 1


@dataclass
class ExecOperation:
    opcode: str
    op0: int
    op1: int


@dataclass
class ALUResult:
    value: int = 0
    exception: bool = False

    def NOP() -> ALUResult:
        return ALUResult(value=None, exception=False)
    
    def isNop(self):
        return self.value is None and self.exception == False

    def __post_init__(self):
        if self.value is not None:
            self.value &= MASK64



class ALU:
    """Minimal pipelined execution unit for the homework integer pipeline."""

    def __init__(self, numPipelineRegisters: int = 1):
        self.numPipelineRegisters = numPipelineRegisters
        self._pipelineRegisters = [None] * self.numPipelineRegisters
        self._nextResult = None

    def propagate(self, operation: ExecOperation | None):
        self._nextResult = self._execute(operation)

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

        if opcode == "add":
            return ALUResult(op0 + op1, False)

        if opcode == "sub":
            return ALUResult(op0 - op1, False)

        if opcode == "mulu":
            return ALUResult(op0 * op1, False)

        if opcode == "divu":
            if op1 == 0:
                return ALUResult(0, True)
            return ALUResult(op0 // op1, False)

        if opcode == "remu":
            if op1 == 0:
                return ALUResult(0, True)
            return ALUResult(op0 % op1, False)

        raise ValueError(f"Unsupported opcode: {opcode}")
