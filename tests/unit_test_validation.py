import unittest

from src.utils.validation import (
    ValidationError,
    sanitize_for_shell,
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

    def test_sanitize_for_shell_backticks(self):
        """Test that sanitize_for_shell escapes backticks."""
        text = "Login with `standard_user`"
        result = sanitize_for_shell(text)
        self.assertEqual(result, "Login with \\`standard_user\\`")

    def test_sanitize_for_shell_dollar(self):
        """Test that sanitize_for_shell escapes dollar signs."""
        text = "Use $HOME variable"
        result = sanitize_for_shell(text)
        self.assertEqual(result, "Use \\$HOME variable")

    def test_sanitize_for_shell_semicolon(self):
        """Test that sanitize_for_shell escapes semicolons."""
        text = "Login; then logout"
        result = sanitize_for_shell(text)
        self.assertEqual(result, "Login\\; then logout")

    def test_sanitize_for_shell_pipe(self):
        """Test that sanitize_for_shell escapes pipes."""
        text = "cmd1 | cmd2"
        result = sanitize_for_shell(text)
        self.assertEqual(result, "cmd1 \\| cmd2")

    def test_sanitize_for_shell_ampersand(self):
        """Test that sanitize_for_shell escapes ampersands."""
        text = "cmd1 & cmd2"
        result = sanitize_for_shell(text)
        self.assertEqual(result, "cmd1 \\& cmd2")

    def test_sanitize_for_shell_empty(self):
        """Test that sanitize_for_shell handles empty input."""
        result = sanitize_for_shell("")
        self.assertEqual(result, "")

    def test_sanitize_for_shell_none(self):
        """Test that sanitize_for_shell handles None input."""
        result = sanitize_for_shell(None)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
