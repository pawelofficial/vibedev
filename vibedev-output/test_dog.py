import pytest
from dog import Dog


class TestDogInit:
    """Test suite for Dog.__init__ method."""

    def test_init_creates_dog_with_name(self):
        """Test that __init__ correctly sets the name attribute."""
        dog = Dog("Buddy", "Golden Retriever")
        assert dog.name == "Buddy"

    def test_init_creates_dog_with_breed(self):
        """Test that __init__ correctly sets the breed attribute."""
        dog = Dog("Max", "Labrador")
        assert dog.breed == "Labrador"

    def test_init_creates_dog_with_both_attributes(self):
        """Test that __init__ correctly sets both name and breed attributes."""
        dog = Dog("Charlie", "Beagle")
        assert dog.name == "Charlie"
        assert dog.breed == "Beagle"

    def test_init_with_different_names(self):
        """Test that __init__ works with various name inputs."""
        names = ["Buddy", "Max", "Charlie", "Luna", "Bella"]
        for name in names:
            dog = Dog(name, "Mixed")
            assert dog.name == name

    def test_init_with_different_breeds(self):
        """Test that __init__ works with various breed inputs."""
        breeds = ["Labrador", "Poodle", "Bulldog", "Husky", "Dachshund"]
        for breed in breeds:
            dog = Dog("TestDog", breed)
            assert dog.breed == breed

    def test_init_with_empty_string_name(self):
        """Test that __init__ accepts empty string for name."""
        dog = Dog("", "Mixed")
        assert dog.name == ""

    def test_init_with_empty_string_breed(self):
        """Test that __init__ accepts empty string for breed."""
        dog = Dog("Buddy", "")
        assert dog.breed == ""

    def test_init_with_special_characters_in_name(self):
        """Test that __init__ handles special characters in name."""
        dog = Dog("Buddy-Max", "Mixed")
        assert dog.name == "Buddy-Max"

    def test_init_with_numbers_in_name(self):
        """Test that __init__ handles numbers in name."""
        dog = Dog("Dog123", "Mixed")
        assert dog.name == "Dog123"

    def test_init_with_long_name(self):
        """Test that __init__ handles long names."""
        long_name = "A" * 1000
        dog = Dog(long_name, "Mixed")
        assert dog.name == long_name

    def test_init_preserves_name_case(self):
        """Test that __init__ preserves the case of the name."""
        dog = Dog("BuDdY", "Mixed")
        assert dog.name == "BuDdY"

    def test_init_preserves_breed_case(self):
        """Test that __init__ preserves the case of the breed."""
        dog = Dog("Buddy", "GoLdEn ReTrIeVeR")
        assert dog.breed == "GoLdEn ReTrIeVeR"


class TestDogBark:
    """Test suite for Dog.bark method."""

    def test_bark_returns_string(self):
        """Test that bark returns a string."""
        dog = Dog("Buddy", "Golden Retriever")
        result = dog.bark()
        assert isinstance(result, str)

    def test_bark_returns_woof(self):
        """Test that bark returns 'Woof!'."""
        dog = Dog("Buddy", "Golden Retriever")
        assert dog.bark() == "Woof!"

    def test_bark_exact_string(self):
        """Test that bark returns the exact string 'Woof!'."""
        dog = Dog("Max", "Labrador")
        assert dog.bark() == "Woof!"

    def test_bark_multiple_calls_consistent(self):
        """Test that multiple calls to bark return the same value."""
        dog = Dog("Charlie", "Beagle")
        result1 = dog.bark()
        result2 = dog.bark()
        result3 = dog.bark()
        assert result1 == result2 == result3 == "Woof!"

    def test_bark_independent_of_name(self):
        """Test that bark output is independent of dog name."""
        dog1 = Dog("Buddy", "Golden Retriever")
        dog2 = Dog("Max", "Labrador")
        assert dog1.bark() == dog2.bark()

    def test_bark_independent_of_breed(self):
        """Test that bark output is independent of dog breed."""
        dog1 = Dog("Buddy", "Golden Retriever")
        dog2 = Dog("Buddy", "Labrador")
        assert dog1.bark() == dog2.bark()

    def test_bark_not_empty(self):
        """Test that bark does not return an empty string."""
        dog = Dog("Buddy", "Golden Retriever")
        assert dog.bark() != ""

    def test_bark_contains_woof(self):
        """Test that bark output contains 'Woof'."""
        dog = Dog("Buddy", "Golden Retriever")
        assert "Woof" in dog.bark()

    def test_bark_does_not_contain_meow(self):
        """Test that bark output does not contain 'meow'."""
        dog = Dog("Buddy", "Golden Retriever")
        assert "meow" not in dog.bark().lower()

    def test_bark_has_exclamation_mark(self):
        """Test that bark output contains an exclamation mark."""
        dog = Dog("Buddy", "Golden Retriever")
        assert "!" in dog.bark()


class TestDogIntegration:
    """Integration tests for Dog class."""

    def test_dog_has_all_attributes(self):
        """Test that a Dog instance has all expected attributes."""
        dog = Dog("Buddy", "Golden Retriever")
        assert hasattr(dog, "name")
        assert hasattr(dog, "breed")

    def test_dog_has_bark_method(self):
        """Test that a Dog instance has the bark method."""
        dog = Dog("Buddy", "Golden Retriever")
        assert hasattr(dog, "bark")
        assert callable(dog.bark)

    def test_create_multiple_dogs_independently(self):
        """Test creating multiple Dog instances independently."""
        dog1 = Dog("Buddy", "Golden Retriever")
        dog2 = Dog("Max", "Labrador")
        dog3 = Dog("Charlie", "Beagle")

        assert dog1.name == "Buddy"
        assert dog2.name == "Max"
        assert dog3.name == "Charlie"

        assert dog1.breed == "Golden Retriever"
        assert dog2.breed == "Labrador"
        assert dog3.breed == "Beagle"

    def test_dog_instances_are_independent(self):
        """Test that modifying one dog does not affect another."""
        dog1 = Dog("Buddy", "Golden Retriever")
        dog2 = Dog("Max", "Labrador")

        # Modify dog1
        dog1.name = "UpdatedBuddy"

        # Verify dog2 is unchanged
        assert dog2.name == "Max"

    def test_all_dogs_bark_the_same(self):
        """Test that all dogs have the same bark."""
        dogs = [
            Dog("Buddy", "Golden Retriever"),
            Dog("Max", "Labrador"),
            Dog("Charlie", "Beagle"),
        ]
        barks = [dog.bark() for dog in dogs]
        assert all(bark == "Woof!" for bark in barks)

    def test_dog_with_unicode_characters(self):
        """Test that Dog handles unicode characters in name and breed."""
        dog = Dog("Büddy", "Пудель")
        assert dog.name == "Büddy"
        assert dog.breed == "Пудель"
        assert dog.bark() == "Woof!"

    def test_dog_attributes_are_mutable(self):
        """Test that dog attributes can be modified after initialization."""
        dog = Dog("Buddy", "Golden Retriever")
        dog.name = "Max"
        dog.breed = "Labrador"
        assert dog.name == "Max"
        assert dog.breed == "Labrador"
