#!/usr/bin/env python3
import hmac
import hashlib

APP_ID = "SHIPPING_FEE_OPTIMIZER"       # make unique per app
SECRET_KEY = "aatman.code@gmail.com" 


def calc_expected_license(email: str, machine_id: str) -> str:
    email_norm = email.strip().lower()
    machine_norm = machine_id.strip().upper()
    raw = f"{APP_ID}|{email_norm}|{machine_norm}"

    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256
    ).hexdigest().upper()

    short = digest[:24]
    return "-".join(short[i:i+4] for i in range(0, len(short), 4))


if __name__ == "__main__":
    email = input("Customer email: ").strip()
    machine_id = input("Machine Code from customer: ").strip()
    key = calc_expected_license(email, machine_id)

    print("\nSend this to the customer:")
    print(f"Email       : {email}")
    print(f"Machine Code: {machine_id}")
    print(f"License Key : {key}")
