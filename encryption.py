#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Módulo de criptografia para licenças CSCollect.

Fornece funções para criptografar/descriptografar campos sensíveis
em arquivos de licença (.key).
"""

import base64
import hashlib
from cryptography.fernet import Fernet
from typing import Optional

# Chave mestre derivada do MASTER_KEY usado para assinatura de tokens
# Usamos SHA-256 de uma frase-chave para derivar uma chave Fernet válida (32 bytes)
ENCRYPTION_SEED = b"CSCollect-License-Encryption-Seed-2026"

def _derive_encryption_key() -> bytes:
    """Deriva uma chave Fernet válida a partir da seed.
    
    Fernet requer uma chave codificada em base64url com exatamente 32 bytes de dados aleatórios.
    Usamos SHA-256 da seed e codificamos em base64url.
    """
    # SHA-256 produz 32 bytes
    key_material = hashlib.sha256(ENCRYPTION_SEED).digest()
    # Fernet espera base64url de 44 caracteres (32 bytes + overhead)
    # Codificamos em base64url
    key = base64.urlsafe_b64encode(key_material)
    return key


_CIPHER = Fernet(_derive_encryption_key())


def encrypt_field(value: Optional[str]) -> Optional[str]:
    """Criptografa um campo sensível para armazenamento seguro.
    
    Args:
        value: Valor a ser criptografado (string) ou None
        
    Returns:
        String criptografada em base64 ou None se input for None/vazio
    """
    if not value:
        return None
    
    # Codifica para bytes (UTF-8)
    plaintext = value.encode('utf-8')
    
    # Criptografa com Fernet (inclui timestamp e HMAC)
    ciphertext = _CIPHER.encrypt(plaintext)
    
    # Retorna como string base64 para armazenamento em JSON
    return ciphertext.decode('ascii')


def decrypt_field(encrypted: Optional[str]) -> Optional[str]:
    """Descriptografa um campo criptografado.
    
    Args:
        encrypted: String criptografada (base64) ou None
        
    Returns:
        Valor original descriptografado ou None se input for None/vazio
        
    Raises:
        cryptography.fernet.InvalidToken: Se a chave ou dados forem inválidos
    """
    if not encrypted:
        return None
    
    try:
        # Converte de string ASCII para bytes
        ciphertext = encrypted.encode('ascii')
        
        # Descriptografa com Fernet
        plaintext = _CIPHER.decrypt(ciphertext)
        
        # Decodifica de UTF-8
        return plaintext.decode('utf-8')
    except Exception as e:
        raise ValueError(f"Erro ao descriptografar campo: {e}")


def is_encrypted(value: Optional[str]) -> bool:
    """Verifica se um valor parece ser criptografado (formato Fernet).
    
    Fernet tokens começam com 'gAAAAAB' em base64url.
    """
    if not value:
        return False
    return value.startswith('gAAAAAB')
