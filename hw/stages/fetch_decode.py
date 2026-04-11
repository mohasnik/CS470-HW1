from hw.common.memory import Memory
from hw.common.instruction import Instruction


class FetchDecodeStage():
    def __init__(self, instMemSize : int):
        self.__instMem = Memory(0, instMemSize, Instruction)
        