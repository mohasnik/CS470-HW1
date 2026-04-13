from dataclasses import dataclass

@dataclass
class ActiveListEntry:
    done: bool
    exception: bool
    logicalDestination: int   
    oldDestination: int       
    pc: int
    dest_pr: int      

    def to_json(self):
        return {
            "Done": self.done,
            "Exception": self.exception,
            "LogicalDestination": self.logicalDestination,
            "OldDestination": self.oldDestination,
            "PC": self.pc
        }