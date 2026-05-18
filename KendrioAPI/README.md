<div align="center">

<img src="static/description/icon.svg" width="96" height="96" alt="Kendrio API Explorer Logo"/>

# Kendrio API Explorer

**Zero-configuration introspection, live OpenAPI docs, Postman export, and RPC recording for Odoo 17**

[![Odoo 17](https://img.shields.io/badge/Odoo-17.0-875A7B?style=flat-square&logo=odoo&logoColor=white)](https://www.odoo.com)
[![Python 3.10](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-4B8BBE?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Version-17.0.2.0.0-22C55E?style=flat-square)](__manifest__.py)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-85EA2D?style=flat-square&logo=swagger&logoColor=black)](https://swagger.io)

</div>

---

## Overview

Kendrio API Explorer automatically discovers and exposes every installed Odoo model, field, relation, view, action, menu, HTTP route, ORM method, access rule, record rule, state machine, and context/domain pattern — then generates live OpenAPI 3.0 specs and Postman collections you can use instantly.

Stop writing API documentation by hand. Install the module and every model in your Odoo instance is already documented with real schema definitions, example payloads, authentication scripts, and a try-it-out Swagger UI.

---

## Features

| Category | What it does |
|---|---|
| **Model scanner** | Every installed model: fields, types, relations, ORM methods, required/readonly/tracking flags |
| **OpenAPI 3.0** | Live spec with JSON-RPC & XML-RPC docs, model schemas, CRUD examples, filterable by model |
| **Postman V2.1** | Ready-to-import collection with session auth pre-request script and per-model CRUD requests |
| **Swagger UI** | Embedded at `/kendrio/swagger` — browse and try every endpoint in the browser |
| **RPC Interceptor** | Records real `call_kw` payloads & responses with timing; isolated cursor survives rollbacks |
| **State machine** | Detects selection states, stage_id fields, statusbar widgets, and state-gated buttons |
| **View parser** | Parses form/tree/kanban/search view arch — fields, buttons, domains, notebook pages |
| **ACL & rules** | Lists `ir.model.access` and `ir.rule` per model, with group and domain info |
| **Route scanner** | Enumerates all Werkzeug routes with methods and auth requirements |
| **Menu tree** | Full UI menu hierarchy with linked actions |
| **Context/domain** | Extracts context keys and domain patterns from field defs, view arch, and action defaults |

---

## Quick Start

### 1. Install

```bash
# Copy module to your Odoo addons path
cp -r KendrioAPI /path/to/odoo/custom_addons/

# Restart Odoo
systemctl restart odoo   # or however you manage your instance

# In Odoo: Apps → Update App List → search "Kendrio" → Install
```

### 2. Open Swagger UI

Navigate to **API Explorer → Swagger UI** in the top menu, or visit:

```
https://your-odoo.example.com/kendrio/swagger
```

> **Note:** All endpoints require the **Settings / Technical** permission (`base.group_system`). Only Odoo Administrators can access the API Explorer.

### 3. Download OpenAPI spec

```bash
curl -b "session_id=YOUR_SESSION" \
     "https://your-odoo.example.com/kendrio/api/openapi.json" \
     -o odoo_openapi.json
```

Filter to specific models:

```bash
curl -b "session_id=YOUR_SESSION" \
     "https://your-odoo.example.com/kendrio/api/openapi.json?models=sale.order,account.move"
```

### 4. Download Postman Collection

```bash
curl -b "session_id=YOUR_SESSION" \
     "https://your-odoo.example.com/kendrio/api/postman.json" \
     -o odoo.postman_collection.json
```

Import the file in Postman. The collection includes a pre-request script that authenticates with your Odoo credentials automatically.

### 5. Enable RPC Recording

Go to **API Explorer → RPC Logs → Settings**, toggle **Recording** on, then click **Apply**.

Every `call_kw` request from the Odoo web client will be logged with full args, kwargs, result, timing, and error information. Disable when not actively debugging — high-traffic instances generate many entries quickly.

---

## REST API Reference

All endpoints are `GET` and require an active Odoo admin session (`auth='user'` + `base.group_system`).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/kendrio/swagger` | Swagger UI (HTML) |
| `GET` | `/kendrio/api/openapi.json` | Full OpenAPI 3.0 spec |
| `GET` | `/kendrio/api/postman.json` | Postman Collection V2.1 download |
| `GET` | `/kendrio/api/models` | List all installed models |
| `GET` | `/kendrio/api/models/{name}` | Model detail (fields, methods, relations) |
| `GET` | `/kendrio/api/models/{name}/fields` | All field definitions |
| `GET` | `/kendrio/api/models/{name}/methods` | ORM & custom method signatures |
| `GET` | `/kendrio/api/models/{name}/views/{type}` | Parsed view arch (`form`, `tree`, `kanban`, `search`) |
| `GET` | `/kendrio/api/models/{name}/rpc` | RPC example payload (`?method=search_read`) |
| `GET` | `/kendrio/api/models/{name}/state-machine` | State machine definition |
| `GET` | `/kendrio/api/models/{name}/context` | Context keys and domain patterns |
| `GET` | `/kendrio/api/models/{name}/actions` | All actions bound to the model |
| `GET` | `/kendrio/api/routes` | All HTTP routes from the routing map |
| `GET` | `/kendrio/api/menus` | UI menu tree |
| `GET` | `/kendrio/api/actions` | All actions |
| `GET` | `/kendrio/api/actions/window` | Window actions (`ir.actions.act_window`) |
| `GET` | `/kendrio/api/acl` | Model access rules (`ir.model.access`) |
| `GET` | `/kendrio/api/acl/rules` | Record rules (`ir.rule`) with domains |
| `GET` | `/kendrio/api/modules` | Installed modules |
| `GET` | `/kendrio/api/server-actions` | Server actions (`ir.actions.server`) |
| `GET` | `/kendrio/api/rpc-logs` | Recent RPC log entries (`?limit=100`) |
| `GET` | `/kendrio/api/rpc-logs/status` | RPC logging status + entry count |
| `POST` | `/kendrio/api/rpc-logs/toggle` | Enable/disable RPC recording |

---

## Using with Python

```python
import requests

session = requests.Session()

# Authenticate
session.post("https://odoo.example.com/web/session/authenticate", json={
    "jsonrpc": "2.0", "method": "call",
    "params": {"db": "mydb", "login": "admin", "password": "admin"}
})

# Get sale.order full schema
model = session.get("https://odoo.example.com/kendrio/api/models/sale.order").json()
print(model["fields"])        # all field definitions
print(model["methods"])       # ORM methods
print(model["state_machine"]) # workflow states

# Get state machine for sale.order
sm = session.get("https://odoo.example.com/kendrio/api/models/sale.order/state-machine").json()

# Download filtered OpenAPI spec
spec = session.get("https://odoo.example.com/kendrio/api/openapi.json",
                   params={"models": "sale.order,purchase.order,account.move"}).json()
```

---

## Architecture

```
KendrioAPI/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── scanner.py          ← core: introspection engine + OpenAPI/Postman generators
│   ├── rpc_log.py          ← kendrio.rpc.log model (audit records)
│   └── rpc_log_wizard.py   ← TransientModel for enable/disable toggle
├── controllers/
│   ├── api.py              ← 20+ REST endpoints
│   └── interceptor.py      ← call_kw interceptor (DataSet subclass, isolated cursor)
├── views/
│   ├── explorer_views.xml  ← ir.ui.view actions for metadata browsing
│   ├── rpc_log_views.xml   ← RPC log list/form/search + wizard
│   └── menu.xml            ← full menu tree under "API Explorer"
├── security/
│   └── ir.model.access.csv ← all three models gated to base.group_system
└── static/description/
    ├── icon.svg / icon.png
    ├── banner.svg / banner.png
    └── index.html          ← Odoo app store description page
```

---

## Branch Structure

| Branch | Content | Purpose |
|--------|---------|---------|
| `main` | Module files at repo root | Development, GitHub browsing |
| `17.0` | Module files inside `KendrioAPI/` subfolder | Odoo app store packaging |

---

## Requirements

- **Odoo** 17.0 Community or Enterprise
- **Python** 3.10+
- **Dependencies**: `base`, `web` — no extra pip packages required
- **Access**: Odoo Administrator (`base.group_system`)

---

## License

[LGPL-3](LICENSE) © 2024 Kendrio — [tovfikur@gmail.com](mailto:tovfikur@gmail.com)
