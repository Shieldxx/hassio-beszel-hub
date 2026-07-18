# Beszel Hub

Lightweight self-hosted server monitoring hub — the central dashboard for [Beszel](https://beszel.dev).

Runs the official `henrygd/beszel` image as a native Home Assistant add-on. Data is persisted to the add-on's `/data` volume, so it survives restarts and add-on updates.

## Setup

1. Install and **Start** the add-on.
2. Open the **Web UI** (port `8090`) and create your admin account.
3. **Add System** for each machine you want to monitor, copy the public key, then install a Beszel **agent** on that machine pointing at this hub.

## Notes

- Default web UI port: `8090`.
- The add-on builds locally from `henrygd/beszel:latest` on install.
