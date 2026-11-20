# Infrastructure

This directory contains setup scripts and local development configuration for generating TLS certificates, MQTT credentials, and initializing the Docker Compose environment.

## Purpose

The infrastructure module automates one-time setup tasks that prepare the Docker Compose stack for first use:
1. Generate a self-signed Certificate Authority (CA)
2. Create TLS certificates for the Mosquitto broker
3. Generate username/password credentials for MQTT publisher and subscriber
4. Create topic Access Control Lists (ACLs) for Mosquitto
5. Persist all credentials and certificates in `.local/` directory (excluded from git)

## Contents

### Setup scripts

- **`setup_local.py`** — Main setup orchestrator (Milestone 2)
  - Generates CA certificate and key
  - Creates Mosquitto server certificate (CN=mosquitto, valid for 365 days)
  - Generates bcrypt-hashed passwords for `publisher` and `subscriber` users
  - Creates Mosquitto ACL file with topic permissions
  - Validates group number (two-digit integer) and certificate CN
  - Implements overwrite protection: refuses to regenerate existing `.local/` directory
  - Logs output to stderr; exits with code 0 (success) or 2 (validation error)

## Usage

### First-time setup

```powershell
# Generate certificates and credentials with group number 10
python infrastructure/setup_local.py --group-number 10

# Output files:
# .local/certs/ca.crt                 (CA certificate, public)
# .local/certs/ca.key                 (CA private key, keep secret)
# .local/certs/server.crt             (Mosquitto server certificate, public)
# .local/certs/server.key             (Mosquitto server private key, keep secret)
# .local/mosquitto/passwd             (Hashed MQTT user credentials)
# .local/mosquitto/acl                (Topic access control rules)
# .local/group_number.txt             (Recorded group number for reference)
# .local/users.txt                    (Plaintext passwords for reference only)
```

### Environment setup

After running `setup_local.py`, update `.env`:

```powershell
# Copy template
cp .env.example .env

# Edit .env to add credentials from .local/users.txt
# Example output from setup_local.py:
#   publisher password: ... (copy to PUBLISHER_PASSWORD in .env)
#   subscriber password: ... (copy to SUBSCRIBER_PASSWORD in .env)
```

### Docker Compose integration

The `docker-compose.yml` references credentials and certificates from `.local/`:

```yaml
services:
  mosquitto:
    volumes:
      - ./.local/mosquitto/passwd:/mosquitto/config/passwd
      - ./.local/mosquitto/acl:/mosquitto/config/acl
      - ./.local/certs:/mosquitto/config/certs
    environment:
      - MOSQUITTO_PORT=8883
      - MOSQUITTO_GROUP_NUMBER=${MQTT_GROUP_NUMBER}

  processor:
    environment:
      - MQTT_CA_CERT=.local/certs/ca.crt
      - MQTT_USERNAME=subscriber
      - MQTT_PASSWORD=${SUBSCRIBER_PASSWORD}

  publisher:
    environment:
      - MQTT_CA_CERT=.local/certs/ca.crt
      - MQTT_USERNAME=publisher
      - MQTT_PASSWORD=${PUBLISHER_PASSWORD}
```

## Generated artifacts

### Certificates (.local/certs/)

- **`ca.crt`** — CA certificate (self-signed, 365 days validity)
  - Shared with clients for TLS verification
  - Public; safe to distribute
  - Format: PEM

- **`ca.key`** — CA private key
  - **Never commit to git**
  - Used only to sign server certificate
  - Keep secret; protect with file permissions (chmod 600)

- **`server.crt`** — Mosquitto server certificate (signed by CA)
  - Certificate authority: Local CA (self-signed)
  - Common Name (CN): `mosquitto`
  - Valid for: 365 days from generation date
  - Public; shared with clients
  - Format: PEM

- **`server.key`** — Mosquitto server private key
  - **Never commit to git**
  - Used by Mosquitto to serve TLS connections
  - Keep secret; protect with file permissions (chmod 600)

### Credentials (.local/mosquitto/)

- **`passwd`** — Hashed MQTT user credentials (Mosquitto format)
  - Format: `username:bcrypt_hash`
  - Two users: `publisher` and `subscriber`
  - Hashes are bcrypt with salt; safe to store in git if needed (but typically .gitignored)
  - **Never commit plaintext passwords**

- **`acl`** — Topic Access Control List
  - Defines read/write permissions per user and topic
  - Publisher can write to `idc/fcXX/status/`, `idc/fcXX/trips/started`, `idc/fcXX/trips/ended`
  - Subscriber can read all `idc/fcXX/#` topics
  - `XX` is the actual group number (from `--group-number` flag)
  - Format: Mosquitto ACL file format

### Reference files (.local/)

- **`users.txt`** — Plaintext passwords for reference during setup
  - Contains: `publisher password: ...`, `subscriber password: ...`
  - **Keep this file secret; do not commit to git**
  - Stored in `.local/` which is excluded from git

- **`group_number.txt`** — Recorded group number
  - Contains the two-digit group number used in this setup
  - Reference for rebuilding topic ACLs or verifying configuration

## Validation and error handling

### Group number validation

- Must be a two-digit integer (10–99)
- Used in MQTT topic prefix: `idc/fc<XX>/`
- Example: `--group-number 10` → topics `idc/fc10/status/JC115`

Invalid group numbers:
```powershell
python infrastructure/setup_local.py --group-number 5      # Error: single digit
python infrastructure/setup_local.py --group-number 100    # Error: three digits
python infrastructure/setup_local.py --group-number ABC    # Error: not an integer
```

### Certificate CN validation

- Server certificate CN is set to `mosquitto` (Mosquitto hostname in Docker Compose)
- Clients validate that certificate CN matches the hostname they are connecting to
- In Docker: hostname is `mosquitto` (service name)
- On localhost: certificate CN is typically `localhost` or the actual hostname

### Overwrite protection

Setup refuses to regenerate if `.local/` already exists:

```powershell
python infrastructure/setup_local.py --group-number 10

# If .local/ exists:
# Error: .local directory already exists. Remove .local/ and try again if you want to regenerate.
# Exit code: 2
```

To regenerate:
```powershell
Remove-Item -Recurse -Force .local
python infrastructure/setup_local.py --group-number 10
```

## Security best practices

1. **Never commit `.local/` to git**
   - Already excluded in `.gitignore`
   - Contains secrets (private keys, passwords)
   - Regenerate on each deployment

2. **Protect private key files** (outside Docker)
   ```bash
   chmod 600 .local/certs/*.key
   chmod 600 .local/mosquitto/passwd
   ```

3. **Use strong passwords**
   - Generated by setup_local.py with 16-character random strings
   - Never hardcode passwords in source code

4. **Rotate credentials periodically**
   - Regenerate `.local/` for different environments (dev/staging/prod)
   - Keep separate credentials per deployment
   - Change passwords when developers leave the team

5. **Validate certificates in production**
   - Self-signed CA is acceptable for development
   - Production should use certificates from a trusted CA
   - Implement certificate pinning or chain validation

## Troubleshooting

### "AttributeError: 'str' object has no attribute 'encode'"

Ensure Python file uses UTF-8 encoding:
```python
# -*- coding: utf-8 -*-
```

### "File exists" or "Permission denied"

Check file permissions on `.local/` directory:
```powershell
ls -la .local/
# Should be readable/writable by current user
```

### Certificate verification fails in client

Ensure CA certificate path matches and certificate chain is valid:
```bash
openssl verify -CAfile .local/certs/ca.crt .local/certs/server.crt
```

### Mosquitto won't start with certificate errors

Verify certificate paths in `mosquitto/mosquitto.conf`:
```bash
grep -E "certfile|keyfile|cafile" mosquitto/mosquitto.conf
# Should reference /mosquitto/config/certs/
```

## Related files

- `docker-compose.yml` — Service definitions that reference `.local/` artifacts
- `mosquitto/mosquitto.conf` — Broker configuration that loads certificates
- `mosquitto/README.md` — Detailed TLS and credential notes
- `.gitignore` — Excludes `.local/` from git
- `.env.example` — Template for environment variables
- Root `README.md` — Platform overview and setup instructions
