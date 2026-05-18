<div align="center">

<img src="KendrioAPI/static/description/icon.svg" width="96" height="96" alt="Kendrio API Explorer Logo"/>

# Kendrio API Explorer — 17.0

**Zero-configuration introspection, live OpenAPI docs, Postman export, and RPC recording for Odoo 17**

[![Odoo 17](https://img.shields.io/badge/Odoo-17.0-875A7B?style=flat-square&logo=odoo&logoColor=white)](https://www.odoo.com)
[![Python 3.10](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-4B8BBE?style=flat-square)](KendrioAPI/__manifest__.py)
[![Version](https://img.shields.io/badge/Version-17.0.2.0.0-22C55E?style=flat-square)](KendrioAPI/__manifest__.py)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-85EA2D?style=flat-square&logo=swagger&logoColor=black)](https://swagger.io)

</div>

---

## Branch Structure

| Branch | Structure | Purpose |
|--------|-----------|---------|
| [`main`](https://github.com/tovfikur/Kendrio-API/tree/main) | Files at repository root | Development & GitHub browsing |
| [`17.0`](https://github.com/tovfikur/Kendrio-API/tree/17.0) | Files inside `KendrioAPI/` subfolder | **Odoo app store** (required format) |

> The Odoo app store scanner requires every module to be in its own named subfolder at the root of the repository. This branch satisfies that requirement.

---

## Repository Layout (this branch)

```
KendrioAPI/               ← add the parent of this folder to --addons-path
├── __manifest__.py
├── __init__.py
├── controllers/
│   ├── api.py            ← 20+ REST endpoints
│   └── interceptor.py    ← live RPC recorder
├── models/
│   ├── scanner.py        ← introspection engine + OpenAPI/Postman generators
│   ├── rpc_log.py
│   └── rpc_log_wizard.py
├── security/
│   └── ir.model.access.csv
├── static/description/
│   ├── icon.svg
│   ├── banner.svg
│   └── index.html
└── views/
    ├── explorer_views.xml
    ├── rpc_log_views.xml
    └── menu.xml
```

---

## Installation

```bash
# Clone this branch
git clone -b 17.0 https://github.com/tovfikur/Kendrio-API.git

# The cloned folder already contains KendrioAPI/ — point Odoo at it:
# odoo-bin --addons-path=/path/to/Kendrio-API,...

# Then in Odoo: Apps → Update App List → search "Kendrio" → Install
```

---

For the full documentation, feature list, REST API reference, and usage examples see the **[`main` branch README](https://github.com/tovfikur/Kendrio-API/tree/main)**.
