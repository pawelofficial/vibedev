"""Comprehensive pytest tests for Dog class"""

import pytest
from dog import Dog


class TestDogInitialization:
    """Test Dog class initialization and attributes."""

    def test_init_basic_attributes(self):
        """Test that __init__ correctly sets basic attributes."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        assert dog.name == "Rex"
        assert dog.age == 3
        assert dog.breed == "Labrador"

    def test_init_state_attributes(self):
        """Test that __init__ correctly initializes state attributes."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")
        assert dog.energy == 100
        assert dog.hunger == 0
        assert dog.happiness == 100
        assert dog.is_sleeping == False

    def test_init_with_different_breeds(self):
        """Test initialization with various breeds."""
        breeds = ["German Shepherd", "Poodle", "Bulldog", "Chihuahua"]
        for breed in breeds:
            dog = Dog(name="TestDog", age=2, breed=breed)
            assert dog.breed == breed

    def test_init_with_different_ages(self):
        """Test initialization with different ages."""
        for age in [1, 5, 10, 15]:
            dog = Dog(name="TestDog", age=age, breed="Mixed")
            assert dog.age == age

    def test_init_with_different_names(self):
        """Test initialization with different names."""
        names = ["Spot", "Fluffy", "Rex", "Max", "Bella"]
        for name in names:
            dog = Dog(name=name, age=3, breed="Mixed")
            assert dog.name == name


class TestBark:
    """Test the bark method."""

    def test_bark_default(self):
        """Test bark with default parameter."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.bark()
        assert result == "Woof! "

    def test_bark_multiple_times(self):
        """Test bark with multiple times parameter."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.bark(times=3)
        assert result == "Woof! Woof! Woof! "

    def test_bark_once(self):
        """Test bark with times=1."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.bark(times=1)
        assert result == "Woof! "

    def test_bark_many_times(self):
        """Test bark with large number."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.bark(times=5)
        assert result == "Woof! " * 5

    def test_bark_while_sleeping(self):
        """Test that bark returns Zzz when dog is sleeping."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.is_sleeping = True
        result = dog.bark()
        assert result == "Zzz..."

    def test_bark_returns_string(self):
        """Test that bark returns a string."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.bark()
        assert isinstance(result, str)


class TestEat:
    """Test the eat method."""

    def test_eat_default_amount(self):
        """Test eat with default amount."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.hunger = 30
        result = dog.eat()
        assert dog.hunger == 20
        assert "ate" in result

    def test_eat_reduces_hunger(self):
        """Test that eat reduces hunger."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.hunger = 50
        dog.eat(amount=20)
        assert dog.hunger == 30

    def test_eat_increases_energy(self):
        """Test that eat increases energy."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.energy = 50
        dog.eat(amount=10)
        assert dog.energy == 55

    def test_eat_hunger_cannot_go_negative(self):
        """Test that hunger doesn't go below 0."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.hunger = 5
        dog.eat(amount=20)
        assert dog.hunger == 0

    def test_eat_energy_cannot_exceed_100(self):
        """Test that energy doesn't exceed 100."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.energy = 98
        dog.eat(amount=50)
        assert dog.energy == 100

    def test_eat_while_sleeping(self):
        """Test that dog won't eat while sleeping."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.is_sleeping = True
        result = dog.eat()
        assert "sleeping" in result
        assert dog.hunger == 0  # Should not change

    def test_eat_returns_message(self):
        """Test that eat returns a descriptive message."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.eat(amount=15)
        assert isinstance(result, str)
        assert dog.name in result


class TestPlay:
    """Test the play method."""

    def test_play_default_duration(self):
        """Test play with default duration."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        initial_energy = dog.energy
        result = dog.play()
        assert dog.energy < initial_energy
        assert "played" in result

    def test_play_reduces_energy(self):
        """Test that play reduces energy."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.play(duration=20)
        assert dog.energy == 80

    def test_play_increases_hunger(self):
        """Test that play increases hunger."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.hunger = 10
        dog.play(duration=20)
        assert dog.hunger == 20  # 10 + 20//2

    def test_play_increases_happiness(self):
        """Test that play increases happiness."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.happiness = 85  # Start below max to ensure increase
        initial_happiness = dog.happiness
        dog.play(duration=10)
        assert dog.happiness > initial_happiness

    def test_play_while_sleeping(self):
        """Test that dog can't play while sleeping."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.is_sleeping = True
        result = dog.play()
        assert "sleeping" in result

    def test_play_when_too_tired(self):
        """Test that dog won't play when energy is too low."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.energy = 10
        result = dog.play(duration=5)
        assert "tired" in result

    def test_play_energy_cannot_go_negative(self):
        """Test that energy doesn't go below 0."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.energy = 5
        dog.play(duration=20)
        assert dog.energy >= 0

    def test_play_hunger_cannot_exceed_100(self):
        """Test that hunger doesn't exceed 100."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.hunger = 95
        dog.play(duration=30)
        assert dog.hunger <= 100

    def test_play_happiness_cannot_exceed_100(self):
        """Test that happiness doesn't exceed 100."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.happiness = 95
        dog.play(duration=5)
        assert dog.happiness <= 100

    def test_play_returns_message(self):
        """Test that play returns a message."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.play(duration=10)
        assert isinstance(result, str)
        assert dog.name in result


class TestSleep:
    """Test the sleep method."""

    def test_sleep_default_hours(self):
        """Test sleep with default hours."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.energy = 30
        dog.sleep()
        assert dog.energy > 30

    def test_sleep_increases_energy(self):
        """Test that sleep increases energy."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.energy = 20
        dog.sleep(hours=4)
        assert dog.energy == 60

    def test_sleep_increases_hunger(self):
        """Test that sleep increases hunger."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.hunger = 10
        dog.sleep(hours=2)
        assert dog.hunger == 12

    def test_sleep_is_sleeping_flag(self):
        """Test that is_sleeping flag is properly handled."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.sleep(hours=1)
        # After sleep completes, should no longer be sleeping
        assert dog.is_sleeping == False

    def test_sleep_energy_cannot_exceed_100(self):
        """Test that energy doesn't exceed 100 while sleeping."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.energy = 80
        dog.sleep(hours=5)
        assert dog.energy == 100

    def test_sleep_hunger_cannot_exceed_100(self):
        """Test that hunger doesn't exceed 100 while sleeping."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.hunger = 95
        dog.sleep(hours=10)
        assert dog.hunger == 100

    def test_sleep_returns_message(self):
        """Test that sleep returns a message."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.sleep(hours=4)
        assert isinstance(result, str)
        assert dog.name in result
        assert "slept" in result


class TestGetStatus:
    """Test the get_status method."""

    def test_get_status_returns_dict(self):
        """Test that get_status returns a dictionary."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        status = dog.get_status()
        assert isinstance(status, dict)

    def test_get_status_contains_all_attributes(self):
        """Test that status contains all required attributes."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        status = dog.get_status()
        required_keys = ["name", "age", "breed", "energy", "hunger", "happiness", "is_sleeping"]
        for key in required_keys:
            assert key in status

    def test_get_status_name(self):
        """Test that status contains correct name."""
        dog = Dog(name="Buddy", age=3, breed="Labrador")
        status = dog.get_status()
        assert status["name"] == "Buddy"

    def test_get_status_age(self):
        """Test that status contains correct age."""
        dog = Dog(name="Rex", age=5, breed="Labrador")
        status = dog.get_status()
        assert status["age"] == 5

    def test_get_status_breed(self):
        """Test that status contains correct breed."""
        dog = Dog(name="Rex", age=3, breed="Poodle")
        status = dog.get_status()
        assert status["breed"] == "Poodle"

    def test_get_status_energy(self):
        """Test that status contains current energy."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.energy = 50
        status = dog.get_status()
        assert status["energy"] == 50

    def test_get_status_hunger(self):
        """Test that status contains current hunger."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.hunger = 30
        status = dog.get_status()
        assert status["hunger"] == 30

    def test_get_status_happiness(self):
        """Test that status contains current happiness."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.happiness = 80
        status = dog.get_status()
        assert status["happiness"] == 80

    def test_get_status_is_sleeping(self):
        """Test that status contains is_sleeping flag."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.is_sleeping = True
        status = dog.get_status()
        assert status["is_sleeping"] == True

    def test_get_status_reflects_changes(self):
        """Test that status reflects recent changes."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        dog.energy = 75
        dog.hunger = 25
        dog.happiness = 90
        status = dog.get_status()
        assert status["energy"] == 75
        assert status["hunger"] == 25
        assert status["happiness"] == 90


class TestBiteMailman:
    """Test the bite_mailman method."""

    def test_bite_mailman_returns_string(self):
        """Test that bite_mailman returns a string."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.bite_mailman()
        assert isinstance(result, str)

    def test_bite_mailman_contains_dog_name(self):
        """Test that bite_mailman message contains dog's name."""
        dog = Dog(name="Buddy", age=3, breed="Labrador")
        result = dog.bite_mailman()
        assert "Buddy" in result

    def test_bite_mailman_contains_mailman(self):
        """Test that bite_mailman message mentions mailman."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.bite_mailman()
        assert "mailman" in result

    def test_bite_mailman_different_dogs(self):
        """Test bite_mailman with different dogs."""
        dogs = [
            Dog(name="Rex", age=3, breed="Labrador"),
            Dog(name="Spot", age=5, breed="Dalmatian"),
            Dog(name="Max", age=2, breed="German Shepherd"),
        ]
        for dog in dogs:
            result = dog.bite_mailman()
            assert dog.name in result
            assert isinstance(result, str)

    def test_bite_mailman_message_quality(self):
        """Test that bite_mailman returns a meaningful message."""
        dog = Dog(name="Rex", age=3, breed="Labrador")
        result = dog.bite_mailman()
        assert len(result) > 0
        assert "bit" in result or "Bit" in result


class TestIntegration:
    """Integration tests for Dog class."""

    def test_full_day_simulation(self):
        """Test a full day simulation."""
        dog = Dog(name="Rex", age=3, breed="Labrador")

        # Morning: wake up and eat
        dog.eat(amount=20)
        assert dog.hunger < 10

        # Afternoon: play
        dog.play(duration=15)
        assert dog.energy < 100
        assert dog.hunger > 0

        # Evening: rest
        dog.sleep(hours=8)
        assert dog.energy == 100

    def test_multiple_operations(self):
        """Test multiple operations in sequence."""
        dog = Dog(name="Buddy", age=5, breed="Golden Retriever")

        status1 = dog.get_status()
        assert status1["energy"] == 100

        dog.play(duration=10)
        dog.eat(amount=15)
        dog.bark(times=3)

        status2 = dog.get_status()
        assert status2["energy"] < status1["energy"]

    def test_state_persistence(self):
        """Test that state persists across operations."""
        dog = Dog(name="Spot", age=4, breed="Dalmatian")

        dog.hunger = 25
        dog.energy = 50
        dog.happiness = 75

        status = dog.get_status()
        assert status["hunger"] == 25
        assert status["energy"] == 50
        assert status["happiness"] == 75

        # Change values
        dog.hunger = 40
        status = dog.get_status()
        assert status["hunger"] == 40

    def test_edge_case_young_dog(self):
        """Test with a very young dog."""
        puppy = Dog(name="Puppy", age=1, breed="Labrador")
        assert puppy.age == 1
        assert puppy.bark() == "Woof! "

    def test_edge_case_old_dog(self):
        """Test with an old dog."""
        senior = Dog(name="Senior", age=15, breed="Poodle")
        assert senior.age == 15
        result = senior.get_status()
        assert result["age"] == 15


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
