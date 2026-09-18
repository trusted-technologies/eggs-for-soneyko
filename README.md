# Eggs for Soneyko

The sole application-template source for [soneyko.ai](https://soneyko.ai).
Contains 1,076 normalized Pterodactyl Eggs, including Pelican variants and three
persistent Linux environments: Debian 13, Ubuntu 24.04 and Alpine 3.22.
Normal discovery shows 379 preferred applications and environments; alternative
upstream variants remain available through the variants filter.

## Catalog

- `eggs/`: standard `PTDL_v2` exports; usable by Pterodactyl-compatible panels.
- `catalog/index.json`: versioned manifest, categories, provenance, resources and SHA-256 checksums.
- `catalog/bundles/`: bounded import batches consumed by the Soneyko panel.
- `originals/`: unchanged upstream exports, including original Pelican formats.
- `catalog/sources.lock.json`: exact upstream commits used for this build.
- `catalog/import-report.json`: merged identical recipes and rejected malformed files.
- `licenses/`: original source repository licenses; upstream attribution is retained.
- `custom/`: Soneyko-owned source Eggs. Regenerate the catalog after editing.

Sources are explicitly listed in `sources.json`: official Pterodactyl game,
application and generic repositories; active Pelican repositories; and its archived
collection. Only identical executable definitions are merged. Different upstream
variants remain distinct. A catalog entry is **not** a claim that its application
has been smoke-tested, that every upstream download still works, or that a game
license/Steam account is unnecessary.

## Refresh and verify

Requires Python 3.11+ and Git. No third-party Python dependencies.

```sh
python tools/sync_catalog.py
python tools/sync_catalog.py --check
python -m unittest discover -s tests
```

`--offline` rebuilds from the existing `.cache/upstreams` checkouts. Review the
generated diff and import report before publishing. Upstream install scripts are
copied, never executed by the importer. Pelican rule arrays are normalized;
multiple startup commands become separate compatible Eggs. Runtime image tags
stay in the Egg; Soneyko resolves the selected runtime and installer to digests
when preparing each container and freezes its configuration.

The panel downloads only this repository at an immutable commit. It does not
follow an Egg's `update_url`, download definitions directly from upstream, or
accept user-supplied Eggs. Existing containers retain their saved configuration
when the catalog changes or a recipe disappears.

## Linux environments

`images/instance` builds an unprivileged PRoot userland. The guest filesystem,
installed packages and configuration live in `/home/container/.instance/rootfs`,
inside the normal Wings server volume. Root is emulated inside the guest; the
outer container uses the node-configured unprivileged UID, with a read-only image, dropped capabilities
and `no-new-privileges`. These are Linux userland environments, **not VMs**:
no dedicated kernel, systemd, nested Docker or additional host privileges.
Package operations requiring kernel features may not work.

The GitHub Actions image workflow builds amd64 variants and checks package
installation and persistence across container recreation under UIDs 1000 and 988
before publishing to
`ghcr.io/trusted-technologies/soneyko-instance`. Public repositories do not
automatically make new GHCR packages public: the package owner must allow public
pulls. The panel reports unavailable images instead of substituting another one.

Runtime images contain OS packages under their respective licenses. The root
license covers Soneyko code; copied upstream recipes retain their original
licenses and attribution in `licenses/` and each catalog entry.
PRoot is built from a pinned upstream commit; its corresponding source archive
is included at `/usr/share/doc/proot/source.tar.gz` in every image.
