# Ansible collections

Each `ansible/collections/<dir>/` directory is a standard Ansible collection — any directory with a `galaxy.yml`:

```
ansible/collections/<dir>/
├── galaxy.yml           required — namespace, name, version (description shows in the catalog)
├── roles/               collection roles
├── plugins/             modules, filters, lookups
└── README.md
```

The collection's identity is `<namespace>.<name>` from `galaxy.yml`, not the directory name. Blueprints
reference collection roles with the 3-part FQCN (`namespace.collection.role`) and must list the collection
under `collections:` in their `requirements.yml` unless it is vendored here.
