

import json
from instruction import Instruction
from activeList import ActiveListEntry
from dataclasses import dataclass, field
from alu import ALU, ExecOperation, ALUResult
from collections import deque
from copy import deepcopy


@dataclass
class IQEntry:
    pc: int
    opcode: str
    destPhysRegId: int

    op0_Ready: bool
    op0_physRegId: int | None
    op0_value: int | None

    op1_Ready: bool
    op1_physRegId: int | None
    op1_value: int | None


@dataclass
class DIREntry:
    pc : int
    instruction : Instruction

class ProcessorState:
    def __init__(
        self,
        numLogicalRegisters: int = 32,
        numPhysicalRegisters: int = 64,
        numALUs: int = 4,
        pc: int = 0x0,
    ):
        self.numLogicalRegisters = numLogicalRegisters
        self.numPhysicalRegisters = numPhysicalRegisters
        self.numALUs = numALUs

        self.pc = pc
        self.physicalRegFile = [0] * self.numPhysicalRegisters
        self.DIR : list[DIREntry | None] = [None] * 4

        self.exceptionFlag = False
        self.exceptionPC = 0

        self.regMapTable = list(range(self.numLogicalRegisters))
        self.freeList = list(range(self.numLogicalRegisters, self.numPhysicalRegisters))
        self.busyBitTable = [False] * self.numPhysicalRegisters
        self.activeList : list[ActiveListEntry] = []
        self.integerQueue : list[IQEntry] = []

        self.execUnitInputs : list[ExecOperation] = [None] * self.numALUs
        self.execUnitResults : list[ALUResult] = [None] * self.numALUs



class CPU:
    def __init__(
        self,
        numALUs: int = 4,
        numLogicalRegisters: int = 32,
        numPhysicalRegisters: int = 64,
    ):
        
        self.__numLogicalRegs = numLogicalRegisters
        self.__numPhysicalRegs = numPhysicalRegisters
        self.__numALUs = numALUs

        self.__instructionMemory = []
        self.currentState : ProcessorState = ProcessorState(
            numLogicalRegisters=self.__numLogicalRegs,
            numPhysicalRegisters=self.__numPhysicalRegs,
            numALUs=self.__numALUs,
        )
        self.nextState : ProcessorState = deepcopy(self.currentState)
        self.execUnits = [ALU() for _ in range(numALUs)]
        self.__stateLog : list[dict] = []

    def parseInstructions(self, filePath):
        self.__instructionMemory = Instruction.from_json(filePath)
    
    def reset(self):
        self.currentState = ProcessorState(self.__numLogicalRegs, self.__numPhysicalRegs, self.__numALUs)
        self.nextState = deepcopy(self.currentState)

        


    def noInstructionsLeft(self):
        return len(self.__instructionMemory) <= self.currentState.pc
    

    ## REMOVE AFTER DEBUGGING:
    def watchInstMem(self):
        return self.__instructionMemory

    def dumpStateIntoLog(self, outputPath: str | None = None):
        decoded_entries = [entry for entry in self.currentState.DIR if entry is not None]
        decoded_pcs = [entry.pc for entry in decoded_entries]

        snapshot = {
            "ActiveList": [entry.to_json() for entry in self.currentState.activeList],
            "BusyBitTable": deepcopy(self.currentState.busyBitTable),
            "DecodedPCs": decoded_pcs,
            "Exception": self.currentState.exceptionFlag,
            "ExceptionPC": self.currentState.exceptionPC,
            "FreeList": deepcopy(self.currentState.freeList),
            "IntegerQueue": [
                {
                    "DestRegister": entry.destPhysRegId,
                    "OpAIsReady": entry.op0_Ready,
                    "OpARegTag": 0 if entry.op0_Ready or entry.op0_physRegId is None else entry.op0_physRegId,
                    "OpAValue": 0 if entry.op0_value is None else entry.op0_value,
                    "OpBIsReady": entry.op1_Ready,
                    "OpBRegTag": 0 if entry.op1_Ready or entry.op1_physRegId is None else entry.op1_physRegId,
                    "OpBValue": 0 if entry.op1_value is None else entry.op1_value,
                    "OpCode": entry.opcode,
                    "PC": entry.pc,
                }
                for entry in self.currentState.integerQueue
            ],
            "PC": self.currentState.pc,
            "PhysicalRegisterFile": [
                0 if value is None else value
                for value in self.currentState.physicalRegFile
            ],
            "RegisterMapTable": deepcopy(self.currentState.regMapTable),
        }

        self.__stateLog.append(snapshot)

        if outputPath is not None:
            with open(outputPath, "w") as f:
                json.dump(self.__stateLog, f, indent=2)

        return snapshot

    def activeListIsEmpty(self):
        return len(self.currentState.activeList) == 0
    

    def __propagateCommitStage(self):
        if not self.currentState.activeList:
            return

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
        # self.nextState.integerQueue = deepcopy(self.currentState.integerQueue)

        issued_indices = []
        alu_idx = 0

        for iq_idx, entry in enumerate(self.currentState.integerQueue):
            if alu_idx >= self.currentState.numALUs:
                break

            if not (entry.op0_Ready and entry.op1_Ready):
                continue

            self.nextState.execUnitInputs[alu_idx] = ExecOperation(
                opcode=entry.opcode,
                op0=entry.op0_value,
                op1=entry.op1_value,
                destPhysicalRegisterId=entry.destPhysRegId,
            )

            issued_indices.append(iq_idx)
            alu_idx += 1

        for iq_idx in reversed(issued_indices):
            self.nextState.integerQueue.pop(iq_idx)

    def __propagateRenameDispatch(self):
        valid_dir_entries: list[DIREntry] = [entry for entry in self.currentState.DIR if entry is not None]

        if not valid_dir_entries:
            return

        for dir_entry in valid_dir_entries:
            if not self.nextState.freeList:
                # TODO : check if this is corrcet
                break

            instruction = dir_entry.instruction

            src_a_tag = self.nextState.regMapTable[instruction.src_a]
            src_a_ready = not self.nextState.busyBitTable[src_a_tag]
            src_a_value = self.nextState.physicalRegFile[src_a_tag]
            # if src_a_value is None:
            #     src_a_value = 0

            if instruction.isImmediate():
                src_b_tag = 0
                src_b_ready = True
                src_b_value = instruction.imm
            else:
                src_b_tag = self.nextState.regMapTable[instruction.src_b]
                src_b_ready = not self.nextState.busyBitTable[src_b_tag]
                src_b_value = self.nextState.physicalRegFile[src_b_tag]
                if src_b_value is None:
                    src_b_value = 0

            old_dest = self.nextState.regMapTable[instruction.dest]
            new_dest = self.nextState.freeList.pop(0)

            self.nextState.regMapTable[instruction.dest] = new_dest
            self.nextState.busyBitTable[new_dest] = True

            self.nextState.activeList.append(
                ActiveListEntry(
                    done=False,
                    exception=False,
                    logicalDestination=instruction.dest,
                    oldDestination=old_dest,
                    pc=dir_entry.pc,
                    dest_pr=new_dest,
                )
            )

            self.nextState.integerQueue.append(
                IQEntry(
                    pc=dir_entry.pc,
                    opcode=instruction.opcode,
                    destPhysRegId=new_dest,
                    op0_Ready=src_a_ready,
                    op0_physRegId=src_a_tag,
                    op0_value=src_a_value,
                    op1_Ready=src_b_ready,
                    op1_physRegId=src_b_tag,
                    op1_value=src_b_value,
                )
            )

    def __propagateExecutionUnits(self):
        for i, alu in enumerate(self.execUnits):
            alu.propagate(self.currentState.execUnitInputs[i])


    def __updateActiveList(self, result : ALUResult):
        for entry in self.nextState.activeList:
            if entry.dest_pr == result.destPhysicalRegisterId:
                entry.done = True
                entry.exception = result.exception
                break

    def __latchExecutionUnits(self):
        for i, alu in enumerate(self.execUnits):
            result = alu.latch()
            
            if result.isNop():
                continue

            ## Write back:
            # TODO: check that updating current state does not temper with the fucntionality!
            # Assumption 1 : we need somethoing that works like half clock for write and read in the second half clock
            # Assumption 2 : WB is also with positive edge! (NOT CURRENT CASE)
            # self.currentState.physicalRegFile[result.destPhysicalRegisterId] = result.value
            self.nextState.physicalRegFile[result.destPhysicalRegisterId] = result.value
            self.currentState.physicalRegFile[result.destPhysicalRegisterId] = result.value
            
            self.nextState.busyBitTable[result.destPhysicalRegisterId] = False
            self.currentState.busyBitTable[result.destPhysicalRegisterId] = False

            self.__updateActiveList(result)




    def __propagateFetchDecode(self):
        """
            Combinational functionality of Fetch and Decode stage.
            Updates the DIR register inputs, and also PC
        """
        pc = self.currentState.pc
        instMemSize = len(self.__instructionMemory)
        self.nextState.DIR = []

        i = 0
        while i < 4:
            if pc + i >= instMemSize:
                break
            else:
                self.nextState.DIR.append(DIREntry(pc + i, self.__instructionMemory[pc + i]))
            i +=1
        
        self.nextState.pc += i  ## Propagate PC here


    def __latchPC(self):
        self.currentState.pc = deepcopy(self.nextState.pc)


    def __latchFetchDecode(self):
        self.currentState.DIR = deepcopy(self.nextState.DIR)

    def __latchRenameDispatch(self):
        self.currentState.activeList = deepcopy(self.nextState.activeList)
        self.currentState.regMapTable = deepcopy(self.nextState.regMapTable)
        self.currentState.freeList = deepcopy(self.nextState.freeList)
        self.currentState.physicalRegFile = deepcopy(self.nextState.physicalRegFile)
        self.currentState.busyBitTable = deepcopy(self.nextState.busyBitTable)
        self.currentState.exceptionPC = deepcopy(self.nextState.exceptionPC)
        self.currentState.exceptionFlag = deepcopy(self.nextState.exceptionFlag)

    def __latchIQ(self):
        self.currentState.integerQueue = deepcopy(self.nextState.integerQueue)

    def __latchIssue(self):
        self.currentState.execUnitInputs = deepcopy(self.nextState.execUnitInputs)

    def propagate(self):
        self.nextState = deepcopy(self.currentState)

        self.__propagateCommitStage()
        self.__propagateExecutionUnits()
        self.__propagateIssue()
        self.__propagateRenameDispatch()
        self.__propagateFetchDecode()

    def latch(self):

        ## 5
        self.__latchExecutionUnits()
        ## 3 :
        self.__latchIssue()

        ## 2 :
        self.__latchIQ()
        self.__latchRenameDispatch()

        ## 1 :
        self.__latchFetchDecode()

        ## 0 :
        self.__latchPC()

        
def main():
    inputFile = "given_tests/01/input.json"
    cpu = CPU(numALUs=4, numPhysicalRegisters=64, numLogicalRegisters=32)
    maxCycles = 6


    cpu.reset()
    cpu.parseInstructions(inputFile)
    cpu.dumpStateIntoLog("output.json")


    cycle = 0
    while not (cpu.noInstructionsLeft()): ## WHY activeLists is empty ?
        if cycle == maxCycles : 
            break

        cpu.propagate()

        #posedge clock here
        cpu.latch()

        cpu.dumpStateIntoLog("output.json")
        cycle += 1



if __name__ == "__main__":
    main() 
