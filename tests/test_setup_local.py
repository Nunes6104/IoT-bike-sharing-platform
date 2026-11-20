import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

from infrastructure.setup_local import group_number, provision, run, san_entry, write_secret


class LocalSetupTests(unittest.TestCase):
    def test_group_requires_one_two_digit_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            for value in ("GROUP_NUMBER=7", "GROUP_NUMBER=xx", "GROUP_NUMBER=01\nGROUP_NUMBER=02"):
                with self.subTest(value=value):
                    path.write_text(value, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        group_number(path)
            path.write_text("GROUP_NUMBER=07\n", encoding="utf-8")
            self.assertEqual(group_number(path), "07")

    def test_certificate_names_reject_invalid_entries(self):
        self.assertEqual(san_entry("broker.example.com"), "DNS:broker.example.com")
        self.assertEqual(san_entry("127.0.0.1"), "IP:127.0.0.1")
        for value in ("", "host,IP:1.2.3.4", "-invalid", "example.com\nDNS:other"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                san_entry(value)

    def test_setup_refuses_to_overwrite_existing_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("infrastructure.setup_local.LOCAL", Path(directory)):
                with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                    provision("unused", "07", [])

    def test_password_data_uses_unix_newlines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "password"
            write_secret(path, "secret")
            self.assertEqual(path.read_bytes(), b"secret\n")
        result = run([sys.executable, "-c",
                      "import sys; sys.stdout.write(sys.stdin.buffer.read().hex())"],
                     stdin="one\ntwo\n")
        self.assertEqual(result, b"one\ntwo\n".hex())


if __name__ == "__main__":
    unittest.main()
