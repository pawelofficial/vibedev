"""A minimalistic Dog class with essential attributes and strict immutability."""


class Dog:
    """
    A minimalistic Dog class with only essential attributes (name and age) and strict immutability.

    No extraneous features or behavior methods. Designed for simplicity and clarity.
    """

    def __init__(self, name: str, age: int) -> None:
        """
        Initialize a Dog.

        Args:
            name: The dog's name. Must be a non-empty string.
            age: The dog's age in years. Must be a non-negative integer (≥ 0).

        Raises:
            ValueError: If name is not a non-empty string or age is not a non-negative integer.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        if not isinstance(age, int) or age < 0:
            raise ValueError("age must be a non-negative integer")

        self._name = name
        self._age = age

    @property
    def name(self) -> str:
        """The dog's name. Immutable after initialization."""
        return self._name

    @property
    def age(self) -> int:
        """The dog's age in years. Immutable after initialization."""
        return self._age

    def __str__(self) -> str:
        """Return human-readable string: 'Dog(name=<name>, age=<age>)'."""
        return f"Dog(name={self._name}, age={self._age})"

    def __repr__(self) -> str:
        """Return developer-friendly representation (identical to __str__)."""
        return self.__str__()
