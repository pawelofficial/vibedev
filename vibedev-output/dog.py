class Dog:
    """Simple Dog class representing a dog with name, age, and breed."""

    def __init__(self, name: str, age: int, breed: str) -> None:
        """Initialize a Dog instance with name, age, and breed.

        Args:
            name: The dog's name
            age: The dog's age in years
            breed: The dog's breed
        """
        self.name = name
        self.age = age
        self.breed = breed

    def bark(self) -> str:
        """Return a bark sound.

        Returns:
            A bark sound string
        """
        return "Woof!"

    def describe(self) -> str:
        """Return a description string of the dog.

        Returns:
            A description of the dog's name, age, and breed
        """
        return f"{self.name} is a {self.age}-year-old {self.breed}"
