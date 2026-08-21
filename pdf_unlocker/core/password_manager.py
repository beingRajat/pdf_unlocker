"""Password manager for secure credential storage.

This module handles secure password storage and retrieval using the
system keyring (Windows Credential Locker, macOS Keychain, Linux Secret Service).
"""

import json
from typing import List, Optional
import keyring
from keyring.errors import KeyringError


class PasswordManager:
    """Manages secure password storage using system keyring.

    Stores passwords as JSON array in the system's credential manager.
    Gracefully handles scenarios where keyring is unavailable.
    """

    SERVICE_NAME = "PDFUnlocker"
    USERNAME = "default_user"  # Keyring requires a username

    @staticmethod
    def is_available() -> bool:
        """Check if keyring backend is available.

        Returns:
            True if keyring is available, False otherwise.
        """
        try:
            backend = keyring.get_keyring()
            # Check if it's not the fail keyring
            return not isinstance(backend, keyring.backends.fail.Keyring)
        except Exception:
            return False

    @staticmethod
    def save_passwords(passwords: List[str]) -> bool:
        """Save passwords to system keyring.

        Args:
            passwords: List of passwords to store.

        Returns:
            True if successful, False otherwise.
        """
        if not PasswordManager.is_available():
            return False

        try:
            # Store as JSON array
            password_json = json.dumps(passwords)
            keyring.set_password(
                PasswordManager.SERVICE_NAME,
                PasswordManager.USERNAME,
                password_json
            )
            return True
        except KeyringError as e:
            print(f"Error saving passwords: {e}")
            return False

    @staticmethod
    def load_passwords() -> Optional[List[str]]:
        """Load passwords from system keyring.

        Returns:
            List of passwords, or None if not found or error occurred.
        """
        if not PasswordManager.is_available():
            return None

        try:
            password_json = keyring.get_password(
                PasswordManager.SERVICE_NAME,
                PasswordManager.USERNAME
            )

            if password_json:
                return json.loads(password_json)
            return None
        except (KeyringError, json.JSONDecodeError) as e:
            print(f"Error loading passwords: {e}")
            return None

    @staticmethod
    def clear_passwords() -> bool:
        """Clear stored passwords from keyring.

        Returns:
            True if successful, False otherwise.
        """
        if not PasswordManager.is_available():
            return False

        try:
            keyring.delete_password(
                PasswordManager.SERVICE_NAME,
                PasswordManager.USERNAME
            )
            return True
        except KeyringError as e:
            print(f"Error clearing passwords: {e}")
            return False
