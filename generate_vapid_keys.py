"""
VAPID kalitlarini generatsiya qilish uchun skript.

Ishlatish:
    python generate_vapid_keys.py

Natijada chiqqan VAPID_PRIVATE_KEY_PEM va VAPID_PUBLIC_KEY qiymatlarini
settings.py fayliga qo'shing.
"""
from py_vapid import Vapid02
from cryptography.hazmat.primitives import serialization
import base64


def generate():
    v = Vapid02()
    v.generate_keys()

    # Private key - PEM formatida (settings.py ga to'g'ridan-to'g'ri qo'yiladi)
    private_pem = v.private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    # Public key - frontend uchun kerak bo'lgan "raw" uncompressed point,
    # URL-safe base64 formatida
    public_numbers = v.public_key.public_numbers()
    x = public_numbers.x.to_bytes(32, "big")
    y = public_numbers.y.to_bytes(32, "big")
    raw_public = b"\x04" + x + y
    public_b64 = base64.urlsafe_b64encode(raw_public).rstrip(b"=").decode("utf-8")

    print("\n" + "=" * 70)
    print("Quyidagilarni settings.py fayliga qo'shing:")
    print("=" * 70 + "\n")

    print('VAPID_PRIVATE_KEY_PEM = """' + private_pem.strip() + '"""\n')
    print(f'VAPID_PUBLIC_KEY = "{public_b64}"\n')
    print('VAPID_CLAIMS = {\n    "sub": "mailto:admin@sizning-domeningiz.uz"\n}')

    print("\n" + "=" * 70)


if __name__ == "__main__":
    generate()