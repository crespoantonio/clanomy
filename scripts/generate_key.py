from cryptography.fernet import Fernet

def main():
    """
    Generates a valid 32-byte URL-safe base64-encoded Fernet key.
    Use this for your ENCRYPTION_KEY in .env.
    """
    key = Fernet.generate_key().decode()
    print("\nGenerated Fernet Encryption Key:")
    print("-" * 50)
    print(key)
    print("-" * 50)
    print("Copy the key above into your .env file as ENCRYPTION_KEY.\n")

if __name__ == "__main__":
    main()
