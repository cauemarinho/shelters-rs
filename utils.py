import secrets


def generate_secret_key():
    return secrets.token_hex(16)  # Gera uma chave secreta de 32 caracteres hexadecimais (128 bits)