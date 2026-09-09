"""What rapyer objects can do, so call sites ask about the capability and not the class."""

import abc
from abc import ABC


class ParentLinked(ABC):
    """
    A value that lives inside a parent document and is wired back to it.
    """

    # The segment carries its own separator: ".name" for a key, "[3]" for a list index.
    @abc.abstractmethod
    def link_to_parent(self, parent: "ParentLinked", path_segment: str):
        """
        Wire this value to its parent at the given path segment.
        """
