from dataclasses import dataclass

@dataclass
class ActiveListEntry:
    done: bool
    exception: bool
    logical_destination: int   # architectural reg (x0–x31)
    old_destination: int       # old physical reg
    pc: int

    # INTERNAL (not in JSON, but you NEED it)
    dest_pr: int               # new physical register

    def to_json(self):
        return {
            "Done": self.done,
            "Exception": self.exception,
            "LogicalDestination": self.logical_destination,
            "OldDestination": self.old_destination,
            "PC": self.pc
        }