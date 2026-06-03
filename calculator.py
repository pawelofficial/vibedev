"""Core calculator logic with arithmetic operations."""


class Calculator:
    """Encapsulates arithmetic operations.

    Supports add, subtract, multiply, and divide operations on two float operands.
    Validates operation names and raises ValueError for invalid operations or
    division by zero.
    """

    def calculate(self, num1: float, num2: float, operation: str) -> float:
        """Perform an arithmetic operation on two operands.

        Args:
            num1: First operand as a float
            num2: Second operand as a float
            operation: Operation name ('add', 'subtract', 'multiply', 'divide')
                      Case-insensitive

        Returns:
            float: The result of the arithmetic operation

        Raises:
            ValueError: If operation is not recognized or if dividing by zero
        """
        operation_lower = operation.lower()

        if operation_lower == 'add':
            return num1 + num2
        elif operation_lower == 'subtract':
            return num1 - num2
        elif operation_lower == 'multiply':
            return num1 * num2
        elif operation_lower == 'divide':
            if num2 == 0:
                raise ValueError('Cannot divide by zero')
            return num1 / num2
        else:
            raise ValueError(f'Invalid operation: {operation}')
