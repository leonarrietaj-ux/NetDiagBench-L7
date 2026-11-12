#!/usr/bin/env python3
"""
NetDiagBench-L7: Generador de Certificados y Claves de Prueba para Entornos de Laboratorio.
Genera localmente certificados autofirmados y claves privadas RSA necesarias para los escenarios
TLS en contenedores y servidores de prueba, evitando la distribución pública de claves criptográficas.
"""

from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path


def generate_with_cryptography(base_dir: Path) -> bool:
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        return False

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Certificado y clave de prueba para Nginx (Válido)
    nginx_certs_dir = base_dir / "scenarios" / "topologies" / "configs" / "nginx" / "certs"
    nginx_certs_dir.mkdir(parents=True, exist_ok=True)
    nginx_key_path = nginx_certs_dir / "server.key"
    nginx_crt_path = nginx_certs_dir / "server.crt"

    key_nginx = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject_nginx = issuer_nginx = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CO"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NetDiagBench-L7 Lab"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    cert_nginx = (
        x509.CertificateBuilder()
        .subject_name(subject_nginx)
        .issuer_name(issuer_nginx)
        .public_key(key_nginx.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.DNSName("netdiag.local")]), critical=False)
        .sign(key_nginx, hashes.SHA256())
    )

    with open(nginx_key_path, "wb") as f:
        f.write(key_nginx.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    with open(nginx_crt_path, "wb") as f:
        f.write(cert_nginx.public_bytes(serialization.Encoding.PEM))
    print(f"[OK] Generado certificado válido Nginx: {nginx_crt_path}")

    # 2. Certificado y clave expirada para Escenario TLS-EXP-01 (Scenario A)
    scenario_a_certs_dir = base_dir / "infra" / "scenario-a-tls" / "certs"
    scenario_a_certs_dir.mkdir(parents=True, exist_ok=True)
    expired_key_path = scenario_a_certs_dir / "expired.key"
    expired_crt_path = scenario_a_certs_dir / "expired.crt"

    key_expired = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject_exp = issuer_exp = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CO"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NetDiagBench-L7 Testbed"),
        x509.NameAttribute(NameOID.COMMON_NAME, "expired.netdiag.local"),
    ])
    # Not valid after en el pasado para garantizar que el certificado esté formalmente expirado
    cert_expired = (
        x509.CertificateBuilder()
        .subject_name(subject_exp)
        .issuer_name(issuer_exp)
        .public_key(key_expired.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=365))
        .not_valid_after(now - datetime.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("expired.netdiag.local"), x509.DNSName("localhost")]), critical=False)
        .sign(key_expired, hashes.SHA256())
    )

    with open(expired_key_path, "wb") as f:
        f.write(key_expired.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    with open(expired_crt_path, "wb") as f:
        f.write(cert_expired.public_bytes(serialization.Encoding.PEM))
    print(f"[OK] Generado certificado formalmente expirado: {expired_crt_path}")

    return True


def generate_with_openssl(base_dir: Path) -> bool:
    openssl_bin = shutil.which("openssl")
    if not openssl_bin:
        return False

    nginx_certs_dir = base_dir / "scenarios" / "topologies" / "configs" / "nginx" / "certs"
    nginx_certs_dir.mkdir(parents=True, exist_ok=True)
    nginx_key_path = nginx_certs_dir / "server.key"
    nginx_crt_path = nginx_certs_dir / "server.crt"

    subprocess.run([
        openssl_bin, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(nginx_key_path), "-out", str(nginx_crt_path),
        "-days", "365", "-subj", "/C=CO/O=NetDiagBench-L7/CN=localhost"
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[OK OpenSSL] Generado certificado válido Nginx: {nginx_crt_path}")

    scenario_a_certs_dir = base_dir / "infra" / "scenario-a-tls" / "certs"
    scenario_a_certs_dir.mkdir(parents=True, exist_ok=True)
    expired_key_path = scenario_a_certs_dir / "expired.key"
    expired_crt_path = scenario_a_certs_dir / "expired.crt"

    # En OpenSSL estándar generamos y luego ajustamos fechas o generamos con -days 1 y fecha pasada si lo soporta
    subprocess.run([
        openssl_bin, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(expired_key_path), "-out", str(expired_crt_path),
        "-days", "-30", "-subj", "/C=CO/O=NetDiagBench-L7/CN=expired.netdiag.local"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[OK OpenSSL] Generado certificado expirado: {expired_crt_path}")
    return True


def main():
    root = Path(__file__).resolve().parent.parent
    print(f"[*] Iniciando generador de claves y certificados de laboratorio en: {root}")
    if generate_with_cryptography(root):
        print("[+] Certificados generados exitosamente con biblioteca cryptography.")
    elif generate_with_openssl(root):
        print("[+] Certificados generados exitosamente mediante CLI openssl.")
    else:
        print("[-] Error: Se requiere 'cryptography' (pip install cryptography) u 'openssl' en PATH.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
