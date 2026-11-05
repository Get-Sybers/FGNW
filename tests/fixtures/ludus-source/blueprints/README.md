# Blueprints

Each `blueprints/<id>/` directory is one blueprint: a named, versioned range config plus its dependencies.

```
blueprints/<id>/
├── blueprint.yml       display metadata (required)
├── range-config.yml    the Ludus range config (required)
├── requirements.yml    galaxy roles, collections, subscription roles (required when the config references any)
├── README.md           what the lab is, VM table, credentials, attack paths
└── thumbnail.png       optional, referenced by thumbnail_path
```

Installed blueprints are addressed as `<sourceID>/<id>` (`ludus blueprint apply <sourceID>/example`).

## Rules CI enforces

These mirror what the Ludus server checks when a source is added or synced
(`ludus-api/source_schema.go`, `source_walker.go`, `yaml_validate.go`) and the
Bad Sector Labs contribution rules:

- `blueprint.yml`: `id` matches the directory path and the Ludus id regex, `name` and `version` (semver) are set, `config` is a relative path that exists, `manifest_version` is 1.
- `range-config.yml` validates against the Ludus range-config JSON schema vendored in `ludus-reference/`.
- Every `vm_name` uses `{{ range_id }}`; VM names, hostnames, and `vlan`/`ip_last_octet` pairs are unique; Windows NetBIOS names (first 15 characters) are unique per domain.
- Every role referenced under `roles:` (including `depends_on`) is declared in `requirements.yml` or vendored under `ansible/roles/` (collections under `ansible/collections/` for 3-part FQCNs).
- Every `template:` is shipped by this source, is a Ludus builtin, or ships in the auto-registered Bad Sector Labs source (extra names can be allow-listed in `.ludus-lint.yml`).
- No `router:` block and no hard-coded `10.x.y.z` addresses (use `{{ range_second_octet }}`) — warnings.

See the [Ludus blueprint docs](https://docs.ludus.cloud/docs/using-ludus/blueprints) for the file formats.
