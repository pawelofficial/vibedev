import pytest
from dog import Dog


class TestDogInit:
    """Test the __init__ method and attribute initialization."""

    def test_init_with_all_parameters(self):
        """Test __init__ with name, breed, and age parameters."""
        dog = Dog(name="Buddy", breed="Golden Retriever", age=5)
        assert dog.name == "Buddy"
        assert dog.breed == "Golden Retriever"
        assert dog.age == 5

    def test_init_with_default_age(self):
        """Test __init__ with default age parameter (should be 0)."""
        dog = Dog(name="Max", breed="Labrador")
        assert dog.name == "Max"
        assert dog.breed == "Labrador"
        assert dog.age == 0

    def test_init_with_zero_age(self):
        """Test __init__ with explicitly set age of 0."""
        dog = Dog(name="Rex", breed="Bulldog", age=0)
        assert dog.age == 0

    def test_init_with_negative_age(self):
        """Test __init__ with negative age (no validation expected)."""
        dog = Dog(name="Spot", breed="Dalmatian", age=-5)
        assert dog.age == -5

    def test_init_name_attribute_type(self):
        """Test that name attribute is stored correctly."""
        dog = Dog(name="Fido", breed="Poodle", age=3)
        assert isinstance(dog.name, str)
        assert dog.name == "Fido"

    def test_init_breed_attribute_type(self):
        """Test that breed attribute is stored correctly."""
        dog = Dog(name="Lucy", breed="Beagle", age=2)
        assert isinstance(dog.breed, str)
        assert dog.breed == "Beagle"

    def test_init_age_attribute_type(self):
        """Test that age attribute is stored as int."""
        dog = Dog(name="Charlie", breed="Husky", age=4)
        assert isinstance(dog.age, int)
        assert dog.age == 4


class TestDogAttributes:
    """Test individual attributes can be accessed and modified."""

    def test_name_attribute_access(self):
        """Test accessing the name attribute."""
        dog = Dog(name="Daisy", breed="Schnauzer", age=1)
        assert dog.name == "Daisy"

    def test_breed_attribute_access(self):
        """Test accessing the breed attribute."""
        dog = Dog(name="Bruno", breed="Boxer", age=2)
        assert dog.breed == "Boxer"

    def test_age_attribute_access(self):
        """Test accessing the age attribute."""
        dog = Dog(name="Molly", breed="Collie", age=6)
        assert dog.age == 6

    def test_name_attribute_modification(self):
        """Test modifying the name attribute."""
        dog = Dog(name="Zoe", breed="Shiba Inu", age=1)
        dog.name = "Zoey"
        assert dog.name == "Zoey"

    def test_breed_attribute_modification(self):
        """Test modifying the breed attribute."""
        dog = Dog(name="Bailey", breed="German Shepherd", age=3)
        dog.breed = "Shepherd Mix"
        assert dog.breed == "Shepherd Mix"

    def test_age_attribute_modification(self):
        """Test modifying the age attribute."""
        dog = Dog(name="Rocky", breed="Rottweiler", age=2)
        dog.age = 5
        assert dog.age == 5


class TestDogRepr:
    """Test the __repr__ method."""

    def test_repr_format_with_all_parameters(self):
        """Test __repr__ returns correct format with all parameters."""
        dog = Dog(name="Buddy", breed="Golden Retriever", age=5)
        expected = "Dog(name='Buddy', breed='Golden Retriever', age=5)"
        assert repr(dog) == expected

    def test_repr_format_with_default_age(self):
        """Test __repr__ format when age is default (0)."""
        dog = Dog(name="Max", breed="Labrador")
        expected = "Dog(name='Max', breed='Labrador', age=0)"
        assert repr(dog) == expected

    def test_repr_with_special_characters_in_name(self):
        """Test __repr__ with special characters in name."""
        dog = Dog(name="O'Brien", breed="Poodle", age=2)
        expected = "Dog(name='O'Brien', breed='Poodle', age=2)"
        assert repr(dog) == expected

    def test_repr_with_spaces_in_breed(self):
        """Test __repr__ with spaces in breed name."""
        dog = Dog(name="Fido", breed="Golden Retriever", age=3)
        expected = "Dog(name='Fido', breed='Golden Retriever', age=3)"
        assert repr(dog) == expected

    def test_repr_string_contains_class_name(self):
        """Test that __repr__ output starts with 'Dog'."""
        dog = Dog(name="Lucy", breed="Beagle", age=1)
        assert repr(dog).startswith("Dog(")

    def test_repr_string_contains_name_key(self):
        """Test that __repr__ output contains 'name=' key."""
        dog = Dog(name="Charlie", breed="Husky", age=4)
        assert "name=" in repr(dog)

    def test_repr_string_contains_breed_key(self):
        """Test that __repr__ output contains 'breed=' key."""
        dog = Dog(name="Daisy", breed="Schnauzer", age=2)
        assert "breed=" in repr(dog)

    def test_repr_string_contains_age_key(self):
        """Test that __repr__ output contains 'age=' key."""
        dog = Dog(name="Bruno", breed="Boxer", age=5)
        assert "age=" in repr(dog)

    def test_repr_returns_string_type(self):
        """Test that __repr__ returns a string."""
        dog = Dog(name="Molly", breed="Collie", age=3)
        assert isinstance(repr(dog), str)

    def test_repr_after_modification(self):
        """Test __repr__ reflects modified attributes."""
        dog = Dog(name="Zoe", breed="Shiba Inu", age=1)
        dog.age = 2
        dog.name = "Zoey"
        expected = "Dog(name='Zoey', breed='Shiba Inu', age=2)"
        assert repr(dog) == expected


class TestDogBark:
    """Test the bark method."""

    def test_bark_returns_woof(self):
        """Test that bark returns 'Woof!'."""
        dog = Dog(name="Bailey", breed="German Shepherd", age=3)
        assert dog.bark() == "Woof!"

    def test_bark_return_type(self):
        """Test that bark returns a string."""
        dog = Dog(name="Rocky", breed="Rottweiler", age=2)
        result = dog.bark()
        assert isinstance(result, str)

    def test_bark_consistent_output(self):
        """Test that bark always returns the same string."""
        dog = Dog(name="Spike", breed="Pitbull", age=4)
        assert dog.bark() == "Woof!"
        assert dog.bark() == "Woof!"
        assert dog.bark() == "Woof!"

    def test_bark_multiple_dogs(self):
        """Test that different dogs all bark the same way."""
        dog1 = Dog(name="Buddy", breed="Golden Retriever", age=5)
        dog2 = Dog(name="Max", breed="Labrador", age=3)
        dog3 = Dog(name="Lucy", breed="Beagle", age=1)
        assert dog1.bark() == dog2.bark() == dog3.bark() == "Woof!"

    def test_bark_does_not_modify_age(self):
        """Test that barking does not modify the dog's age."""
        dog = Dog(name="Charlie", breed="Husky", age=4)
        initial_age = dog.age
        dog.bark()
        assert dog.age == initial_age

    def test_bark_does_not_modify_name(self):
        """Test that barking does not modify the dog's name."""
        dog = Dog(name="Daisy", breed="Schnauzer", age=2)
        initial_name = dog.name
        dog.bark()
        assert dog.name == initial_name

    def test_bark_does_not_modify_breed(self):
        """Test that barking does not modify the dog's breed."""
        dog = Dog(name="Bruno", breed="Boxer", age=5)
        initial_breed = dog.breed
        dog.bark()
        assert dog.breed == initial_breed

    def test_bark_exact_string(self):
        """Test exact string match for bark output."""
        dog = Dog(name="Molly", breed="Collie", age=3)
        assert dog.bark() == "Woof!"
        assert dog.bark() != "Woof"
        assert dog.bark() != "WOOF!"
        assert dog.bark() != "woof!"


class TestDogBirthday:
    """Test the birthday method."""

    def test_birthday_increments_age_by_default(self):
        """Test that birthday increments age by 1 by default."""
        dog = Dog(name="Zoe", breed="Shiba Inu", age=1)
        dog.birthday()
        assert dog.age == 2

    def test_birthday_increments_age_by_specified_years(self):
        """Test that birthday increments age by specified number of years."""
        dog = Dog(name="Bailey", breed="German Shepherd", age=3)
        dog.birthday(years=2)
        assert dog.age == 5

    def test_birthday_with_zero_years(self):
        """Test birthday with zero years (no change)."""
        dog = Dog(name="Rocky", breed="Rottweiler", age=2)
        dog.birthday(years=0)
        assert dog.age == 2

    def test_birthday_with_large_years(self):
        """Test birthday with large number of years."""
        dog = Dog(name="Spike", breed="Pitbull", age=1)
        dog.birthday(years=10)
        assert dog.age == 11

    def test_birthday_multiple_times(self):
        """Test calling birthday multiple times."""
        dog = Dog(name="Buddy", breed="Golden Retriever", age=5)
        dog.birthday()
        assert dog.age == 6
        dog.birthday()
        assert dog.age == 7
        dog.birthday()
        assert dog.age == 8

    def test_birthday_returns_none(self):
        """Test that birthday returns None."""
        dog = Dog(name="Max", breed="Labrador", age=3)
        result = dog.birthday()
        assert result is None

    def test_birthday_does_not_modify_name(self):
        """Test that birthday does not modify the dog's name."""
        dog = Dog(name="Lucy", breed="Beagle", age=1)
        initial_name = dog.name
        dog.birthday()
        assert dog.name == initial_name

    def test_birthday_does_not_modify_breed(self):
        """Test that birthday does not modify the dog's breed."""
        dog = Dog(name="Charlie", breed="Husky", age=4)
        initial_breed = dog.breed
        dog.birthday(years=2)
        assert dog.breed == initial_breed

    def test_birthday_with_starting_age_zero(self):
        """Test birthday on a dog with age 0."""
        dog = Dog(name="Daisy", breed="Schnauzer")
        assert dog.age == 0
        dog.birthday()
        assert dog.age == 1

    def test_birthday_with_negative_years(self):
        """Test birthday with negative years (should decrease age)."""
        dog = Dog(name="Bruno", breed="Boxer", age=5)
        dog.birthday(years=-2)
        assert dog.age == 3

    def test_birthday_accumulation(self):
        """Test accumulative effect of multiple birthday calls."""
        dog = Dog(name="Molly", breed="Collie", age=0)
        for _ in range(5):
            dog.birthday()
        assert dog.age == 5

    def test_birthday_with_specified_years_accumulation(self):
        """Test accumulative effect with specified years."""
        dog = Dog(name="Zoe", breed="Shiba Inu", age=1)
        dog.birthday(years=3)
        dog.birthday(years=2)
        assert dog.age == 6


class TestDogIntegration:
    """Integration tests combining multiple methods."""

    def test_dog_lifecycle(self):
        """Test a complete dog lifecycle."""
        # Create a dog
        dog = Dog(name="Buddy", breed="Golden Retriever", age=0)

        # Check initial state
        assert dog.name == "Buddy"
        assert dog.breed == "Golden Retriever"
        assert dog.age == 0

        # Dog has a birthday
        dog.birthday()
        assert dog.age == 1

        # Check repr after birthday
        assert "age=1" in repr(dog)

        # Dog barks
        assert dog.bark() == "Woof!"

        # Age increases
        assert dog.age == 1

    def test_repr_consistency_after_operations(self):
        """Test that repr is consistent after various operations."""
        dog = Dog(name="Max", breed="Labrador", age=2)
        repr1 = repr(dog)
        dog.bark()
        repr2 = repr(dog)
        assert repr1 == repr2

    def test_multiple_dogs_independence(self):
        """Test that multiple dogs don't affect each other."""
        dog1 = Dog(name="Buddy", breed="Golden Retriever", age=2)
        dog2 = Dog(name="Max", breed="Labrador", age=3)

        dog1.birthday()
        assert dog1.age == 3
        assert dog2.age == 3  # Should remain 3, not 4

        dog2.birthday(years=5)
        assert dog1.age == 3
        assert dog2.age == 8

    def test_dog_with_empty_string_name(self):
        """Test dog with empty string name."""
        dog = Dog(name="", breed="Mixed", age=1)
        assert dog.name == ""
        assert repr(dog) == "Dog(name='', breed='Mixed', age=1)"

    def test_dog_with_empty_string_breed(self):
        """Test dog with empty string breed."""
        dog = Dog(name="Buddy", breed="", age=1)
        assert dog.breed == ""
        assert repr(dog) == "Dog(name='Buddy', breed='', age=1)"

    def test_dog_with_unicode_name(self):
        """Test dog with unicode characters in name."""
        dog = Dog(name="Büddy", breed="Golden Retriever", age=2)
        assert dog.name == "Büddy"
        assert "Büddy" in repr(dog)

    def test_dog_with_unicode_breed(self):
        """Test dog with unicode characters in breed."""
        dog = Dog(name="Buddy", breed="Côte d'Ivoire Hound", age=2)
        assert dog.breed == "Côte d'Ivoire Hound"
        assert "Côte d'Ivoire Hound" in repr(dog)
