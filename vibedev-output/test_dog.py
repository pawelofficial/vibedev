import pytest
from dog import Dog


class TestDogInitialization:
    """Tests for Dog class initialization."""

    def test_init_valid_inputs(self):
        """Test Dog initialization with valid inputs."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        assert dog.name == "Buddy"
        assert dog.age == 5
        assert dog.breed == "Golden Retriever"

    def test_init_different_names(self):
        """Test Dog initialization with different names."""
        names = ["Max", "Bella", "Charlie", "Daisy", "Rocky"]
        for name in names:
            dog = Dog(name=name, age=3, breed="Mixed")
            assert dog.name == name

    def test_init_various_ages(self):
        """Test Dog initialization with various ages."""
        ages = [0, 1, 5, 10, 15, 20]
        for age in ages:
            dog = Dog(name="TestDog", age=age, breed="Mixed")
            assert dog.age == age

    def test_init_various_breeds(self):
        """Test Dog initialization with various breeds."""
        breeds = ["Labrador", "German Shepherd", "Poodle", "Chihuahua", "Dalmation", "Mixed"]
        for breed in breeds:
            dog = Dog(name="TestDog", age=5, breed=breed)
            assert dog.breed == breed

    def test_init_stores_all_attributes(self):
        """Test that all attributes are stored correctly."""
        dog = Dog(name="Oscar", age=7, breed="Bulldog")
        assert hasattr(dog, "name")
        assert hasattr(dog, "age")
        assert hasattr(dog, "breed")

    def test_init_with_empty_name(self):
        """Test Dog initialization with empty name string."""
        dog = Dog(name="", age=3, breed="Poodle")
        assert dog.name == ""

    def test_init_with_zero_age(self):
        """Test Dog initialization with zero age."""
        dog = Dog(name="Puppy", age=0, breed="Labrador")
        assert dog.age == 0

    def test_init_with_long_breed_name(self):
        """Test Dog initialization with long breed name."""
        long_breed = "Tibetan Mastiff" * 5
        dog = Dog(name="TestDog", age=3, breed=long_breed)
        assert dog.breed == long_breed


class TestDogBark:
    """Tests for Dog.bark() method."""

    def test_bark_returns_string(self):
        """Test that bark() returns a string."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        result = dog.bark()
        assert isinstance(result, str)

    def test_bark_returns_woof(self):
        """Test that bark() returns 'Woof!'."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        assert dog.bark() == "Woof!"

    def test_bark_consistent_output(self):
        """Test that bark() returns the same output on multiple calls."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        first_bark = dog.bark()
        second_bark = dog.bark()
        assert first_bark == second_bark
        assert first_bark == "Woof!"

    def test_bark_multiple_dogs(self):
        """Test that different dogs produce the same bark."""
        dog1 = Dog(name="Buddy", age=5, breed="Golden Retriever")
        dog2 = Dog(name="Max", age=3, breed="Labrador")
        dog3 = Dog(name="Bella", age=7, breed="Poodle")

        assert dog1.bark() == "Woof!"
        assert dog2.bark() == "Woof!"
        assert dog3.bark() == "Woof!"

    def test_bark_independent_of_attributes(self):
        """Test that bark() output is independent of dog attributes."""
        dogs = [
            Dog(name="SmallDog", age=1, breed="Chihuahua"),
            Dog(name="LargeDog", age=10, breed="Great Dane"),
            Dog(name="OldDog", age=15, breed="Mixed"),
        ]
        for dog in dogs:
            assert dog.bark() == "Woof!"

    def test_bark_does_not_modify_state(self):
        """Test that bark() does not modify the dog's state."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        original_name = dog.name
        original_age = dog.age
        original_breed = dog.breed

        dog.bark()

        assert dog.name == original_name
        assert dog.age == original_age
        assert dog.breed == original_breed

    def test_bark_exact_string(self):
        """Test that bark() returns exactly 'Woof!' with no extra characters."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        assert dog.bark() == "Woof!"
        assert len(dog.bark()) == 5
        assert dog.bark().startswith("Woof")
        assert dog.bark().endswith("!")


class TestDogDescribe:
    """Tests for Dog.describe() method."""

    def test_describe_returns_string(self):
        """Test that describe() returns a string."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        result = dog.describe()
        assert isinstance(result, str)

    def test_describe_format(self):
        """Test that describe() returns the correct format."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        expected = "Buddy is a 5-year-old Golden Retriever"
        assert dog.describe() == expected

    def test_describe_includes_name(self):
        """Test that describe() includes the dog's name."""
        dog = Dog(name="Max", age=3, breed="Labrador")
        description = dog.describe()
        assert "Max" in description

    def test_describe_includes_age(self):
        """Test that describe() includes the dog's age."""
        dog = Dog(name="Max", age=3, breed="Labrador")
        description = dog.describe()
        assert "3" in description

    def test_describe_includes_breed(self):
        """Test that describe() includes the dog's breed."""
        dog = Dog(name="Max", age=3, breed="Labrador")
        description = dog.describe()
        assert "Labrador" in description

    def test_describe_various_dogs(self):
        """Test describe() with various dog configurations."""
        test_cases = [
            (Dog(name="Buddy", age=5, breed="Golden Retriever"),
             "Buddy is a 5-year-old Golden Retriever"),
            (Dog(name="Max", age=3, breed="Labrador"),
             "Max is a 3-year-old Labrador"),
            (Dog(name="Bella", age=7, breed="Poodle"),
             "Bella is a 7-year-old Poodle"),
            (Dog(name="Charlie", age=2, breed="Beagle"),
             "Charlie is a 2-year-old Beagle"),
        ]
        for dog, expected in test_cases:
            assert dog.describe() == expected

    def test_describe_consistent_output(self):
        """Test that describe() returns the same output on multiple calls."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        first_description = dog.describe()
        second_description = dog.describe()
        assert first_description == second_description

    def test_describe_does_not_modify_state(self):
        """Test that describe() does not modify the dog's state."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        original_name = dog.name
        original_age = dog.age
        original_breed = dog.breed

        dog.describe()

        assert dog.name == original_name
        assert dog.age == original_age
        assert dog.breed == original_breed

    def test_describe_with_zero_age(self):
        """Test describe() with age 0 (newborn puppy)."""
        dog = Dog(name="Puppy", age=0, breed="Labrador")
        expected = "Puppy is a 0-year-old Labrador"
        assert dog.describe() == expected

    def test_describe_with_large_age(self):
        """Test describe() with a large age."""
        dog = Dog(name="OldDog", age=25, breed="Chihuahua")
        expected = "OldDog is a 25-year-old Chihuahua"
        assert dog.describe() == expected

    def test_describe_with_special_characters_in_name(self):
        """Test describe() with special characters in name."""
        dog = Dog(name="Buddy-Max", age=5, breed="Golden Retriever")
        expected = "Buddy-Max is a 5-year-old Golden Retriever"
        assert dog.describe() == expected

    def test_describe_with_spaces_in_breed(self):
        """Test describe() with spaces in breed name."""
        dog = Dog(name="Rex", age=4, breed="German Shepherd")
        expected = "Rex is a 4-year-old German Shepherd"
        assert dog.describe() == expected

    def test_describe_structure(self):
        """Test the structure of describe() output."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        description = dog.describe()
        # Check the structure: "Name is a Age-year-old Breed"
        assert description.count(" is a ") == 1
        assert description.count("-year-old") == 1
        assert description.startswith("Buddy")
        assert description.endswith("Golden Retriever")


class TestDogIntegration:
    """Integration tests for Dog class."""

    def test_dog_complete_workflow(self):
        """Test a complete workflow using Dog methods."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")

        # Test all methods in sequence
        assert dog.bark() == "Woof!"
        assert dog.describe() == "Buddy is a 5-year-old Golden Retriever"
        assert dog.name == "Buddy"
        assert dog.age == 5
        assert dog.breed == "Golden Retriever"

    def test_multiple_dog_instances(self):
        """Test creating and using multiple dog instances."""
        dog1 = Dog(name="Buddy", age=5, breed="Golden Retriever")
        dog2 = Dog(name="Max", age=3, breed="Labrador")
        dog3 = Dog(name="Bella", age=7, breed="Poodle")

        descriptions = [dog1.describe(), dog2.describe(), dog3.describe()]
        barks = [dog1.bark(), dog2.bark(), dog3.bark()]

        # All should have unique descriptions
        assert len(set(descriptions)) == 3
        # All should have the same bark
        assert all(bark == "Woof!" for bark in barks)

    def test_dog_attributes_are_independent(self):
        """Test that dog instances don't share attributes."""
        dog1 = Dog(name="Buddy", age=5, breed="Golden Retriever")
        dog2 = Dog(name="Max", age=3, breed="Labrador")

        # Verify they have different attributes
        assert dog1.name != dog2.name
        assert dog1.age != dog2.age
        assert dog1.breed != dog2.breed

        # Verify methods work independently
        assert dog1.describe() != dog2.describe()
        assert dog1.bark() == dog2.bark()

    def test_dog_string_representation_via_describe(self):
        """Test that describe() provides a meaningful string representation."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        description = dog.describe()

        # Verify the description is human-readable and contains all info
        assert "Buddy" in description
        assert "5" in description
        assert "Golden Retriever" in description
        assert "is" in description.lower()
        assert "year" in description.lower()
