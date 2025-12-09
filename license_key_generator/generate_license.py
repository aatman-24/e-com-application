#!/usr/bin/env python3
import hashlib

SECRET_KEY = "aatman.code@gmail.com"  # SAME as in app


def calc_license_key(name: str, email: str) -> str:
    text = f"{name.strip()}|{email.strip()}|{SECRET_KEY}"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    short = digest[:24]
    blocks = [short[i : i + 4] for i in range(0, len(short), 4)]
    return "-".join(blocks)


if __name__ == "__main__":
    name = input("Customer name: ").strip()
    email = input("Customer email: ").strip()
    key = calc_license_key(name, email)
    print("\nGive this to customer:")
    print(f"Name  : {name}")
    print(f"Email : {email}")
    print(f"Key   : {key}")
