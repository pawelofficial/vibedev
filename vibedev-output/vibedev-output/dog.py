class Dog:
    """A minimalistic Dog class with essential attributes and basic behavioral methods."""

    def __init__(self, name: str, breed: str, age: int = 0) -> None:
        """Initialize a Dog with name, breed, and optional age (default 0)."""
        self.name = name
        self.breed = breed
        self.age = age

    def __repr__(self) -> str:
        """Return string representation in format: Dog(name='<name>', breed='<breed>', age=<age>)."""
        return f"Dog(name='{self.name}', breed='{self.breed}', age={self.age})"

    def bark(self) -> str:
        """Return the dog's bark sound."""
        return "Woof!"

    def birthday(self, years: int = 1) -> None:
        """Increment the dog's age by the specified number of years (default 1)."""
        self.age += years
