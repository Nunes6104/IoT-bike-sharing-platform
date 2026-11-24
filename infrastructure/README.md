# Infrastructure

`setup_local.py` provisions local-only credentials and development TLS certificates required by the Compose stack.

## Setup

1. Copy `.env.example` to `.env` and set `GROUP_NUMBER` to the assigned two-digit value.
2. Ensure OpenSSL and Docker are available; the script uses Docker to generate Mosquitto and Node-RED password hashes.
3. Run `python infrastructure\setup_local.py` from the repository root.

The script creates `.local/` with CA and service certificates, database and MQTT passwords, broker ACL/password files, a dashboard admin password/hash, and an analytics API token. Certificates cover the Compose service hostnames and localhost; use `--hostname` when clients will connect using an additional DNS name or IP. The script refuses to overwrite an existing `.local/` directory.

Keep `.local/` private and untracked. Do not publish or commit private keys, plaintext passwords, hashes, or service tokens. To replace credentials, follow a deliberate rotation procedure rather than deleting local files while services are using them.

See the root [README](../README.md) for starting Compose and accessing the dashboard.
