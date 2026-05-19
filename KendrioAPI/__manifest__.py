{
    'name': 'Kendrio API Explorer',
    'version': '17.0.2.0.0',
    'category': 'Technical',
    'summary': 'Runtime introspection · OpenAPI · Postman · RPC recorder for Odoo 17',
    'description': """
Kendrio API Explorer
====================

A powerful zero-configuration introspection and documentation module for Odoo 17.

Automatically discovers and exposes every installed model, field, relation, view,
action, menu, HTTP route, ORM method, access rule, record rule, state machine, and
context/domain pattern — then generates live OpenAPI 3.0 specs and Postman
collections you can use instantly.

Key capabilities
----------------
* Static metadata scanner (models, fields, views, routes, ACL, menus, actions)
* View arch parser (fields, buttons, domains, notebook pages)
* State-machine detector (selection states, stage_id, statusbar, button transitions)
* Context/domain behaviour extractor
* Live RPC interceptor — record exact call_kw payloads and responses
* OpenAPI 3.0 generator with model schemas, JSON-RPC + XML-RPC docs
* Postman Collection V2.1 generator with auth script and per-model CRUD
* All endpoints admin-gated (base.group_system)
    """,
    'author': 'Odoo Command Center',
    'website': 'https://github.com/tovfikur',
    'support': 'tovfikur@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/explorer_views.xml',
        'views/rpc_log_views.xml',
        'views/menu.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
