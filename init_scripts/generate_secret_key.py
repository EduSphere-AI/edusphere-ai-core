#!/usr/bin/env python3
"""
Generate a secure secret key for JWT token signing.
Run this script and copy the output to your .env file as SECRET_KEY.
"""

import secrets

def generate_secret_key(length: int = 32) -> str:
    """Generate a secure random secret key."""
    return secrets.token_hex(length)

if __name__ == "__main__":
    secret_key = generate_secret_key()
    print("Generated SECRET_KEY:")
    print(secret_key)
    print("\nAdd this to your .env file:")
    print(f"SECRET_KEY={secret_key}")
