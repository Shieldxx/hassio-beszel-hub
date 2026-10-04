# Beszel Hub

Lightweight self-hosted server monitoring hub — the central dashboard for [Beszel](https://beszel.dev).

Runs the official `henrygd/beszel` image as a native Home Assistant add-on. Data is persisted to the add-on's `/data` volume, so it survives restarts and add-on updates.

## Setup

1. Install and **Start** the add-on.
2. Open the **Web UI** (port `8090`) and create your admin account.
3. **Add System** for each machine you want to monitor, copy the public key, then install a Beszel **agent** on that machine pointing at this hub.

## Sidebar or port 8090

Everything works in the sidebar, including Beszel's admin pages (Users, Logs,
Backups). If a page ever shows 404 there — as the whole sidebar did before 1.2.2,
when a Beszel upgrade changed how it reports its base path — the direct port always
works: `http://<Home Assistant IP>:8090`. Prefer the IP to `homeassistant.local`,
which a browser may resolve to an IPv6 address that the port mapping does not answer.

## Backups

Uninstalling the add-on deletes its `/data` folder. Beszel's own backup carries
everything across: user menu → **Backups** (`/_/#/settings/backups`), create a backup and
download the ZIP; in a new installation, upload it there and restore. The ZIP holds the
systems, their history, the users and the hub's key, so agents reconnect by themselves.

## Notes

- Default web UI port: `8090`.
- The add-on builds locally from `henrygd/beszel:latest` on install.

## License

This add-on (Dockerfile, nginx configuration, start script) is MIT — see [LICENSE](LICENSE).
Beszel itself is © henrygd under the MIT License and is pulled as its official image at
build time; `icon.png` is Beszel's logo from [henrygd/beszel](https://github.com/henrygd/beszel).
