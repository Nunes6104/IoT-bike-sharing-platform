"""Provision disposable local-development credentials and certificates."""

import argparse
import ipaddress
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / ".local"


def group_number(env_file: Path) -> str:
    lines = env_file.read_text(encoding="utf-8-sig").splitlines()
    values = [line.partition("=")[2].strip() for line in lines
              if line.partition("=")[0].strip() == "GROUP_NUMBER"]
    if len(values) != 1 or not re.fullmatch(r"[0-9]{2}", values[0]):
        raise ValueError("Set GROUP_NUMBER to exactly two digits in .env")
    return values[0]


def san_entry(host: str) -> str:
    try:
        return f"IP:{ipaddress.ip_address(host)}"
    except ValueError:
        labels = host.split(".")
        if (len(host) > 253 or not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in labels
        )):
            raise ValueError(f"Invalid certificate hostname: {host}") from None
        return f"DNS:{host}"


def run(command: list[str], *, stdin: str | None = None) -> str:
    env = os.environ.copy()
    env["MSYS_NO_PATHCONV"] = "1"
    result = subprocess.run(
        command, input=stdin.encode("utf-8") if stdin is not None else None,
        capture_output=True, env=env,
    )
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed: {result.stderr.decode('utf-8', errors='replace').strip()}")
    return result.stdout.decode("utf-8").strip()


def write_secret(path: Path, value: str, *, mounted: bool = False) -> None:
    path.write_bytes((value + "\n").encode("utf-8"))
    path.chmod(0o644 if mounted else 0o600)


def find_openssl() -> str:
    executable = shutil.which("openssl")
    if executable:
        return executable
    git_openssl = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "mingw64" / "bin" / "openssl.exe"
    if git_openssl.is_file():
        return str(git_openssl)
    raise ValueError("OpenSSL is required; install it or add it to PATH")


def provision(openssl: str, group: str, hostnames: list[str]) -> None:
    entries = [san_entry(host) for host in hostnames]
    if LOCAL.exists():
        raise ValueError(".local already exists; refusing to overwrite credentials")
    LOCAL.mkdir(mode=0o700)
    certs = LOCAL / "certs"
    mqtt = LOCAL / "mosquitto"
    mysql = LOCAL / "mysql"
    dashboard = LOCAL / "dashboard"
    for directory in (certs, mqtt, mysql, dashboard):
        directory.mkdir(parents=True, mode=0o700)

    ca_key, ca_cert = certs / "ca.key", certs / "ca.crt"
    run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(ca_key), "-out", str(ca_cert), "-days", "365",
         "-subj", "/CN=Bike Sharing Development CA",
         "-addext", "basicConstraints=critical,CA:TRUE",
         "-addext", "keyUsage=critical,keyCertSign,cRLSign"])
    ca_key.chmod(0o600)
    for name in ("mosquitto", "database", "dashboard"):
        key, csr, cert = (certs / f"{name}.{suffix}" for suffix in ("key", "csr", "crt"))
        sans = ",".join(dict.fromkeys(["DNS:localhost", "IP:127.0.0.1", f"DNS:{name}", *entries]))
        run([openssl, "req", "-new", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(key), "-out", str(csr), "-subj", f"/CN={name}",
             "-addext", f"subjectAltName={sans}", "-addext", "extendedKeyUsage=serverAuth",
             "-addext", "basicConstraints=critical,CA:FALSE",
             "-addext", "keyUsage=critical,digitalSignature,keyEncipherment"])
        key.chmod(0o644)
        run([openssl, "x509", "-req", "-in", str(csr), "-CA", str(ca_cert),
             "-CAkey", str(ca_key), "-CAcreateserial", "-out", str(cert), "-days", "365",
             "-copy_extensions", "copy"])
        csr.unlink()

    mqtt_passwords = {user: secrets.token_urlsafe(32) for user in ("publisher", "processor", "health")}
    plaintext = "".join(f"{user}:{password}\n" for user, password in mqtt_passwords.items())
    hashes = run(["docker", "run", "--rm", "-i", "--entrypoint", "sh",
                  "eclipse-mosquitto:2", "-c",
                  "umask 077; cat > /tmp/passwords && mosquitto_passwd -U /tmp/passwords && cat /tmp/passwords"],
                 stdin=plaintext)
    write_secret(mqtt / "passwords", hashes, mounted=True)
    for user, password in mqtt_passwords.items():
        write_secret(mqtt / f"{user}.password", password, mounted=user == "health")
    topic = f"idc/fc{group}"
    (mqtt / "acl").write_bytes((
        f"user publisher\ntopic write {topic}/status/+\n"
        f"topic write {topic}/trips/started\ntopic write {topic}/trips/ended\n"
        f"user processor\ntopic read {topic}/status/+\n"
        f"topic read {topic}/trips/started\ntopic read {topic}/trips/ended\n"
        f"user health\ntopic write {topic}/health\n").encode("utf-8"))

    for name in ("db-root.password", "db-user.password"):
        write_secret(mysql / name, secrets.token_urlsafe(32), mounted=True)
    admin_password = secrets.token_urlsafe(32)
    admin_hash = run(
        ["docker", "run", "--rm", "-i", "--entrypoint", "node", "nodered/node-red:4.1.5",
         "-e", "let p='';process.stdin.setEncoding('utf8');process.stdin.on('data',x=>p+=x);"
               "process.stdin.on('end',()=>console.log(require('bcryptjs').hashSync(p,10)));"],
        stdin=admin_password,
    )
    write_secret(dashboard / "admin.password", admin_password)
    write_secret(dashboard / "admin.hash", admin_hash, mounted=True)
    write_secret(dashboard / "credential-secret", secrets.token_urlsafe(32), mounted=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hostname", action="append", default=[],
                        help="additional DNS name or IP address clients will use")
    args = parser.parse_args()
    try:
        group = group_number(ROOT / ".env")
        openssl = find_openssl()
        provision(openssl, group, args.hostname)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Local setup failed: {exc}", file=sys.stderr)
        return 1
    print("Local development credentials and certificates created in .local.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
