from abc import ABC, abstractmethod

class Module(ABC):
    @abstractmethod
    def propagate(self, **kwargs):
        pass

    @abstractmethod
    def latch(self, **kwargs):
        pass