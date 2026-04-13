

from instruction import Instruction
from activeList import ActiveListEntry
from dataclasses import dataclass, field
from alu import ALU, ExecOperation
from collections import deque
from copy import deepcopy


@dataclass
class IQEntry:
    pc: int
    opcode: str
    dest_register: int
    op_a_is_ready: bool
    op_a_reg_tag: int | None
    op_a_value: int | None
    op_b_is_ready: bool
    op_b_reg_tag: int | None
    op_b_value: int | None


class ProcessorState:
    def __init__(
        self,
        numLogicalRegisters: int = 32,
        numPhysicalRegisters: int = 64,
        numALUs: int = 4,
        pc: int = 0,
    ):
        self.numLogicalRegisters = numLogicalRegisters
        self.numPhysicalRegisters = numPhysicalRegisters
        self.numALUs = numALUs

        self.pc = pc
        self.physicalRegFile = [None] * self.numPhysicalRegisters
        self.DIR = [None] * 4

        self.exceptionFlag = False
        self.exceptionPC = 0

        self.regMapTable = list(range(self.numLogicalRegisters))
        self.freeList = list(range(self.numLogicalRegisters, self.numPhysicalRegisters))
        self.busyBitTable = [False] * self.numPhysicalRegisters
        self.activeList : list[ActiveListEntry] = []
        self.integerQueue : list[IQEntry] = []

        self.execUnitInputs = [None] * self.numALUs
        self.execUnitResults = [None] * self.numALUs



class CPU:
    def __init__(
        self,
        numALUs: int = 4,
        numLogicalRegisters: int = 32,
        numPhysicalRegisters: int = 64,
    ):
        self.__instructionMemory = []
        self.currentState : ProcessorState = ProcessorState(
            numLogicalRegisters=numLogicalRegisters,
            numPhysicalRegisters=numPhysicalRegisters,
            numALUs=numALUs,
        )
        self.nextState : ProcessorState = deepcopy(self.currentState)
        self.__execUnits = [ALU() for _ in range(numALUs)]

    def parseInstructions(self, filePath):
        self.__instructionMemory = Instruction.from_json(filePath)
    
    def reset(self):
        pass

    def noInstructionsLeft(self):
        return len(self.__instructionMemory) <= self.currentState.pc
    

    def activeListIsEmpty(self):
        return len(self.currentState.activeList) == 0
    

    def __propagateCommitStage(self):
        head = self.currentState.activeList[0]
        if head.done:
            if head.exception == True:
                self.nextState.exceptionFlag = True
                self.nextState.exceptionPC = head.pc
                ## TODO : may require additional steps here
            else:
                # self.nextState.freeList = deepcopy(self.currentState.freeList)
                self.nextState.freeList.append(head.oldDestination)

                # removing the head for next state
                # self.nextState.activeList = deepcopy(self.currentState.activeList)
                self.nextState.activeList.pop(0)

    def __propagateIssue(self):
        self.nextState.execUnitInputs = [None] * self.currentState.numALUs
        self.nextState.integerQueue = deepcopy(self.currentState.integerQueue)

        issued_indices = []
        alu_idx = 0

        for iq_idx, entry in enumerate(self.currentState.integerQueue):
            if alu_idx >= self.currentState.numALUs:
                break

            if not (entry.op_a_is_ready and entry.op_b_is_ready):
                continue

            self.nextState.execUnitInputs[alu_idx] = ExecOperation(
                opcode=entry.opcode,
                op0=entry.op_a_value,
                op1=entry.op_b_value,
            )
            issued_indices.append(iq_idx)
            alu_idx += 1

        for iq_idx in reversed(issued_indices):
            self.nextState.integerQueue.pop(iq_idx)

    def __propagateExecutionUnits(self):
        for i, alu in enumerate(self.__execUnits):
            alu.propagate(self.currentState.execUnitInputs[i])


    def __latchExecutionUnits(self):
        for i, alu in enumerate(self.__execUnits):
            self.nextState.execUnitResults[i] = alu.latch()
        


    def __propagateFetchDecode(self):
        pc = self.currentState.pc
        instMemSize = len(self.__instructionMemory)

        for i in range(4):
            if pc + i > instMemSize:
                break
            else:
                self.nextState.DIR[i] = self.__instructionMemory[pc + i]
    
    def __latchPC(self):
        self.currentState.pc = self.nextState.pc


    def __latchFetchDecode(self):
        self.currentState.DIR = self.nextState.DIR


    def propagate(self):
        self.__propagateCommitStage()
        self.__propagateExecutionUnits()
        self.__propagateIssue()
        
        pass

    def latch(self):
        # commit stage ?

        # ALUs
        self.__latchExecutionUnits()
        self.__latchFetchDecode()
        self.__latchPC()
        
        # self.currentState = deepcopy(self.nextState)
        
        

        
