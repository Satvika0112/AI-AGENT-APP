"""
base.py - the small shared contract every agent follows.
"""


class Agent:
    name = "agent"

    def run(self, *args, **kwargs) -> dict:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"