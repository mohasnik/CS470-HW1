
class Counter():
    """
        Generic Class for any counters required in the processor
    """
    def __init__(self, initValue : int, maxValue : int):
        self.__initValue = initValue
        self.__count = initValue
        self.__maxValue = maxValue
        self.__co = False
    
    def reset(self):
        self.__count = self.__initValue
        self.__co = False

    def propagate(self):
        self.__co = (self.__count == (self.__maxValue-1))

    def latch(self, countVal = 1, countUp : bool = True):
        if countUp:
            self.__count += countVal
            
            if self.__count >= self.__maxValue:
                self.__count = self.__count % self.__maxValue
        else:
            self.__count -= countVal
            # TODO: underflow condition if needed

    def isMax(self) -> bool:
        return self.__co
    

class ProgramCounter(Counter):
    """
        The main Program Counter (PC) of the processor
    """
    def __init__(self, maxValue):
        super().__init__(0, maxValue)
    
    def reset(self):
        return super().reset()

    def propagate(self):
        return super().propagate()
    
    def latch(self):
        # TODO: the counter may not do +4 all the time. 
        ## May need a variable countVal
        return super().latch(countVal = 4, countUp = True)
    
    # TODO : implement a reportState for each module 
    ## to take the values for dumping states
    def reportState():
        pass