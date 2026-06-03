class Dog:
    """A minimalistic Dog class representing a dog with essential attributes and behaviors."""

    def __init__(self, name: str, breed: str):
        """Initialize dog with name and breed."""
        self.name = name
        self.breed = breed

    def bark(self) -> str:
        """Return a bark sound."""
        return "Woof!"
