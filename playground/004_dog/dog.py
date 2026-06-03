"""Dog class implementation"""


class Dog:
    """A simple Dog class with basic behaviors."""

    def __init__(self, name: str, age: int, breed: str):
        """
        Initialize a Dog.

        Args:
            name: The dog's name
            age: The dog's age in years
            breed: The dog's breed
        """
        self.name = name
        self.age = age
        self.breed = breed
        self.energy = 100
        self.hunger = 0
        self.happiness = 100
        self.is_sleeping = False

    def bark(self, times: int = 1) -> str:
        """
        Make the dog bark.

        Args:
            times: Number of times to bark

        Returns:
            A string representing the barking sound
        """
        if self.is_sleeping:
            return "Zzz..."
        return "Woof! " * times

    def eat(self, amount: int = 10) -> str:
        """
        Feed the dog.

        Args:
            amount: Amount of food to give (0-100)

        Returns:
            A message about eating
        """
        if self.is_sleeping:
            return "The dog is sleeping and won't eat."
        self.hunger = max(0, self.hunger - amount)
        self.energy = min(100, self.energy + 5)
        return f"{self.name} ate and reduced hunger to {self.hunger}"

    def play(self, duration: int = 10) -> str:
        """
        Play with the dog.

        Args:
            duration: Duration of play in minutes

        Returns:
            A message about playing
        """
        if self.is_sleeping:
            return "The dog is sleeping and can't play."
        if self.energy < 20:
            return "The dog is too tired to play."

        self.energy = max(0, self.energy - duration)
        self.hunger = min(100, self.hunger + duration // 2)
        self.happiness = min(100, self.happiness + 10)
        return f"{self.name} played for {duration} minutes and is happy!"

    def sleep(self, hours: int = 8) -> str:
        """
        Put the dog to sleep.

        Args:
            hours: Number of hours to sleep

        Returns:
            A message about sleeping
        """
        self.is_sleeping = True
        self.energy = min(100, self.energy + hours * 10)
        self.hunger = min(100, self.hunger + hours)

        result = f"{self.name} slept for {hours} hours"
        self.is_sleeping = False
        return result

    def get_status(self) -> dict:
        """
        Get the current status of the dog.

        Returns:
            A dictionary with the dog's current status
        """
        return {
            "name": self.name,
            "age": self.age,
            "breed": self.breed,
            "energy": self.energy,
            "hunger": self.hunger,
            "happiness": self.happiness,
            "is_sleeping": self.is_sleeping
        }

    def bite_mailman(self) -> str:
        """
        The dog bites the mailman.

        Returns:
            A message about biting the mailman
        """
        return f"{self.name} bit the mailman! Ouch!"
