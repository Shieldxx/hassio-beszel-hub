# Beszel Hub — Home Assistant add-on (development)

This is the development repository of the **Beszel Hub** add-on. **Install it from
[Shieldxx/ha-addons](https://github.com/Shieldxx/ha-addons)**, the one repository for
all Shieldxx add-ons — not from here.

The add-on itself is in [`beszel_hub/`](beszel_hub); see its [README](beszel_hub/README.md).

> `repository.yaml` is still here only so installs made from this repository keep
> working until they have moved to `ha-addons`. It goes after that.

## Releasing

1. Change what you need in `beszel_hub/`, bump `version` in `beszel_hub/config.yaml`
   and add a section for it at the top of `beszel_hub/CHANGELOG.md` — Home Assistant
   shows it next to the update.
2. Commit. Only a commit is ever published.
3. Preview, then publish:

       python scripts/publish_addon.py --dry-run
       python scripts/publish_addon.py

The script copies an allowlist of files (`scripts/publish.json`) from the last commit
into `ha-addons/beszel_hub/`, scans them for credentials and personal email addresses,
refuses an unchanged version or a missing changelog section, and commits under the
noreply identity. `scripts/publish_addon.py` is byte-identical in every add-on's
development repository — change one copy, carry it to the others, compare sha256.

## License

MIT — see [beszel_hub/LICENSE](beszel_hub/LICENSE). Beszel itself is © henrygd, MIT.
