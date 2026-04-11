import json
from hw.common.instruction import Instruction
from module import Module
from abc import abstractmethod



class Memory(Module):
    """
        Byte addressable memory. Aligned r/w only possible for now
    """

    class UnAlignedMemoryAccess(Exception):
        def __init__(self, *args):
            super().__init__(*args)
    
        
    def __init__(self, numReadPorts, numWritePorts, size : int, BWidth : int = 4):

        self.__numReadPorts = numReadPorts
        self.__numWritePorts = numWritePorts

        #interface : 
        self.raddr = [0] * self.__numReadPorts
        self._rdata = [None] * self.__numReadPorts
        self.ren = [False] * self.__numReadPorts

        self.waddr = [0] * self.__numWritePorts
        self.wen = [False] * self.__numWritePorts
        self.wdata = [None] * self.__numWritePorts
        
        # arguments:
        self._size = size  ## number of cells
        self._BWidth = BWidth ## Width of each cell of memory (in Bytes)

        self._mem = [None] * self._size
    
    def readData(self):
        return self._rdata
      
    def totalSize(self):
        """
            Returns the total memory size in Bytes
        """
        return self._size * self._BWidth

    def _read(self, address : int):
        if address % self._BWidth !=0:
            raise Memory.UnAlignedMemoryAccess(
                f"address {address} is an unaligned access.")
        else:
            return self._mem[address // self._BWidth]
    
    def _write(self, value, address : int):
        if address % self._BWidth !=0:
            raise Memory.UnAlignedMemoryAccess(
                f"address {address} is an unaligned access.")
        elif value.BWidth() != self._BWidth:
            raise Exception(f"The value is {value.BWidth()} while each cell has {self._BWidth} width")

        else:
            self._mem[address // self._BWidth] = value

    def propagate(self, **kwargs):
        for i in range(self.__numReadPorts):
            if self.ren[i]:
                self._rdata[i] = self._read(self.raddr[i])

    def latch(self, **kwargs):
        for i in range(self.__numWritePorts):
            if self.wen[i]:
                # assuming write is done on negedge, 
                # so it is available for the next clock cycle
                self._write(self.wdata[i], self.waddr[i]) 




class InstructionMemory(Memory):
    def __init__(self, readDelay, writeDelay, size, BWidth = 4):
        super().__init__(readDelay, writeDelay, size, BWidth)

    def laodJson(self, path: str) -> int:
        with open(path) as f:
            lines = json.load(f)

        for i, line in enumerate(lines):
            inst = Instruction.from_string(line)
            self.write(i, inst)
        return len(lines)
    
    def propagate(**kwargs):
        




class RegisterFile(Memory):
    def __init__(self, size, data_t = int):
        super().__init__(0, size, data_t)
    
    