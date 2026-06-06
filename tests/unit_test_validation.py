import unittest

from src.utils.validation import (
    ValidationError,
    validate_description,
)


class TestValidation(unittest.TestCase):
    def test_valid_description(self):
        """Test that valid descriptions pass validation."""
        desc = "Login with standard_user and secret_sauce"
        result = validate_description(desc)
        self.assertEqual(result, desc)

    def test_description_with_backticks(self):
        """Test that descriptions with backticks are now accepted."""
        desc = "Login with `standard_user` and `secret_sauce`"
        result = validate_description(desc)
        self.assertEqual(result, desc)

    def test_description_with_code_reference(self):
        """Test that technical descriptions with code references work."""
        desc = "Test the `submit()` function with valid input"
        result = validate_description(desc)
        self.assertEqual(result, desc)

    def test_empty_description(self):
        """Test that empty descriptions are rejected."""
        with self.assertRaises(ValidationError) as context:
            validate_description("")
        self.assertIn("cannot be empty", str(context.exception))

    def test_description_too_long(self):
        """Test that descriptions exceeding max length are rejected."""
        desc = "a" * 501
        with self.assertRaises(ValidationError) as context:
            validate_description(desc)
        self.assertIn("too long", str(context.exception))

    def test_description_with_html_tags(self):
        """Test that descriptions with HTML tags are rejected."""
        desc = "Click <script>alert('xss')</script> button"
        with self.assertRaises(ValidationError) as context:
            validate_description(desc)
        self.assertIn("invalid characters", str(context.exception))

    def test_description_with_path_traversal(self):
        """Test that descriptions with path traversal are rejected."""
        desc = "Go to ../../etc/passwd"
        with self.assertRaises(ValidationError) as context:
            validate_description(desc)
        self.assertIn("invalid characters", str(context.exception))

    def test_description_with_semicolon(self):
        """Test that descriptions with semicolons are rejected."""
        desc = "Login; then logout"
        with self.assertRaises(ValidationError) as context:
            validate_description(desc)
        self.assertIn("invalid characters", str(context.exception))

    def test_description_with_pipe(self):
        """Test that descriptions with pipes are rejected."""
        desc = "Login | cat file"
        with self.assertRaises(ValidationError) as context:
            validate_description(desc)
        self.assertIn("invalid characters", str(context.exception))

    def test_description_with_dollar(self):
        """Test that descriptions with dollar signs are rejected."""
        desc = "Use $HOME variable"
        with self.assertRaises(ValidationError) as context:
            validate_description(desc)
        self.assertIn("invalid characters", str(context.exception))


if __name__ == "__main__":
    unittest.main()
