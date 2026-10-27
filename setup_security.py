"""Creates the security material for the local MQTT broker (NFR5).

- a local certificate authority (CA) and a TLS server certificate for
  'localhost' / 127.0.0.1, signed by the CA
- a password file with an Argon2 hash of the MQTT test credentials

Usage:  python setup_security.py      (requires the openssl command)
"""
import os
import subprocess

from pwdlib.hashers.argon2 import Argon2Hasher

import config


def run(*args):
    subprocess.run(args, check=True, cwd=config.CERT_DIR,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def create_certificates():
    with open(os.path.join(config.CERT_DIR, "san.cnf"), "w") as f:
        f.write("subjectAltName=DNS:localhost,IP:127.0.0.1\n")
    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "365",
        "-subj", "/CN=Inventory Simulation CA", "-keyout", "ca.key", "-out", "ca.crt")
    run("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=localhost",
        "-keyout", "server.key", "-out", "server.csr")
    run("openssl", "x509", "-req", "-in", "server.csr", "-CA", "ca.crt",
        "-CAkey", "ca.key", "-CAcreateserial", "-days", "365",
        "-extfile", "san.cnf", "-out", "server.crt")


def create_password_file():
    pwd_hash = Argon2Hasher().hash(config.MQTT_PASSWORD)
    with open(config.PASSWORD_FILE, "w") as f:
        f.write(f"{config.MQTT_USER}:{pwd_hash}\n")


if __name__ == "__main__":
    os.makedirs(config.CERT_DIR, exist_ok=True)
    create_certificates()
    create_password_file()
    print(f"Security material written to {config.CERT_DIR}")
