"""
Kendrio API Scanner — Layer 1 (static metadata) + Layer 3 (OpenAPI/Postman generators).

Covers:
  models · fields · relations · views (arch parser) · actions (all types) · menus ·
  routes/controllers · ORM methods · onchange chains · access rules · record rules ·
  state machines · context/domain behavior · required payloads · example RPC calls
"""
import inspect
import json
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

_FIELD_TO_JSON = {
    'char':      {'type': 'string'},
    'text':      {'type': 'string'},
    'html':      {'type': 'string', 'format': 'html'},
    'integer':   {'type': 'integer'},
    'float':     {'type': 'number', 'format': 'float'},
    'monetary':  {'type': 'number', 'format': 'float'},
    'boolean':   {'type': 'boolean'},
    'date':      {'type': 'string', 'format': 'date'},
    'datetime':  {'type': 'string', 'format': 'date-time'},
    'binary':    {'type': 'string', 'format': 'byte'},
    'image':     {'type': 'string', 'format': 'byte'},
    'selection': {'type': 'string'},
    'many2one':  {'type': 'integer', 'x-odoo-type': 'many2one'},
    'one2many':  {'type': 'array', 'items': {'type': 'integer'}, 'x-odoo-type': 'one2many'},
    'many2many': {'type': 'array', 'items': {'type': 'integer'}, 'x-odoo-type': 'many2many'},
    'reference': {'type': 'string'},
}

_COMMON_ORM_METHODS = ['search_read', 'create', 'write', 'unlink', 'read', 'search', 'default_get', 'onchange']


class KendrioScanner(models.TransientModel):
    _name = 'kendrio.scanner'
    _description = 'Kendrio API Scanner'

    # ================================================================== #
    #  LAYER 1 — STATIC METADATA SCANNERS                                 #
    # ================================================================== #

    # ------------------------------------------------------------------ #
    #  1.1 Model scanner                                                   #
    # ------------------------------------------------------------------ #

    @api.model
    def get_all_models(self, include_abstract=False, include_transient=True):
        result = []
        for model_name, model_class in sorted(self.env.registry.models.items()):
            if not include_abstract and getattr(model_class, '_abstract', False):
                continue
            if not include_transient and getattr(model_class, '_transient', False):
                continue
            result.append({
                'name': model_name,
                'description': getattr(model_class, '_description', '') or '',
                'table': getattr(model_class, '_table', '') or '',
                'transient': bool(getattr(model_class, '_transient', False)),
                'abstract': bool(getattr(model_class, '_abstract', False)),
                'field_count': len(model_class._fields),
                'rec_name': getattr(model_class, '_rec_name', 'name') or 'name',
                'order': getattr(model_class, '_order', 'id') or 'id',
            })
        return result

    @api.model
    def get_model_detail(self, model_name):
        if model_name not in self.env.registry.models:
            return None
        try:
            model = self.env[model_name]
        except Exception:
            return None
        model_class = type(model)
        inherit = model_class._inherit
        if isinstance(inherit, str):
            inherit = [inherit] if inherit else []
        return {
            'name': model_name,
            'description': model_class._description or '',
            'table': model_class._table or '',
            'transient': model_class._transient,
            'abstract': model_class._abstract,
            'inherit': list(inherit) if inherit else [],
            'inherits': dict(model_class._inherits) if model_class._inherits else {},
            'rec_name': model_class._rec_name or 'name',
            'order': model_class._order or 'id',
            'sql_constraints': [list(c) for c in getattr(model_class, '_sql_constraints', [])],
            'fields': self.get_model_fields(model_name),
            'methods': self.get_model_methods(model_name),
            'onchange': self.get_onchange_methods(model_name),
            'access_rules': self.get_acl(model_name=model_name),
            'record_rules': self.get_record_rules(model_name=model_name),
            'views': self.get_model_views(model_name),
            'state_machine': self.get_state_machine(model_name),
        }

    # ------------------------------------------------------------------ #
    #  1.2 Field scanner                                                   #
    # ------------------------------------------------------------------ #

    @api.model
    def get_model_fields(self, model_name):
        if model_name not in self.env.registry.models:
            return []
        try:
            model = self.env[model_name]
        except Exception:
            return []
        return [self._field_info(f) for f in sorted(model._fields.values(), key=lambda f: f.name)]

    def _field_info(self, field):
        info = {
            'name': field.name,
            'type': field.type,
            'string': field.string or field.name,
            'required': bool(field.required),
            'readonly': bool(field.readonly),
            'store': bool(field.store),
            'help': field.help or '',
            'groups': field.groups or '',
            'tracking': bool(getattr(field, 'tracking', False)),
            'index': bool(getattr(field, 'index', False)),
        }
        compute = getattr(field, 'compute', None)
        if compute:
            info['compute'] = compute
            info['compute_sudo'] = bool(getattr(field, 'compute_sudo', False))
            try:
                fn = getattr(field, compute, None)
                deps = getattr(fn, '_depends', None)
                if deps:
                    info['depends'] = list(deps)
            except Exception:
                pass
        related = getattr(field, 'related', None)
        if related:
            info['related'] = '.'.join(related) if isinstance(related, (tuple, list)) else str(related)
        if field.type in ('many2one', 'one2many', 'many2many'):
            info['comodel'] = getattr(field, 'comodel_name', '') or ''
        if field.type == 'one2many':
            info['inverse_name'] = getattr(field, 'inverse_name', '') or ''
        if field.type == 'many2many':
            info['relation_table'] = getattr(field, 'relation', '') or ''
        if field.type == 'selection':
            try:
                sel = field.selection
                info['selection'] = list(sel) if not callable(sel) else []
                info['selection_dynamic'] = callable(sel)
            except Exception:
                info['selection'] = []
                info['selection_dynamic'] = False
        return info

    # ------------------------------------------------------------------ #
    #  1.3 Method / onchange scanner                                       #
    # ------------------------------------------------------------------ #

    @api.model
    def get_model_methods(self, model_name):
        """Public custom methods on the model — excludes BaseModel ORM noise."""
        if model_name not in self.env.registry.models:
            return []
        try:
            from odoo.models import BaseModel as _Base
            model_class = self.env.registry.models[model_name]
            base_names = frozenset(n for n in dir(_Base) if callable(getattr(_Base, n, None)))
        except Exception as exc:
            _logger.warning("Kendrio method scan error for %s: %s", model_name, exc)
            return []

        compute_methods = {f.compute for f in model_class._fields.values() if f.compute}
        result = []

        for name in sorted(dir(model_class)):
            if name.startswith('_') or name in base_names or name in compute_methods:
                continue
            attr = getattr(model_class, name, None)
            if not callable(attr):
                continue
            func = getattr(attr, '__func__', attr)
            info = {
                'name': name,
                'is_action': name.startswith('action_'),
                'is_onchange': bool(getattr(func, '_onchange', None)),
                'is_constrains': bool(getattr(func, '_constrains', None)),
                'module': getattr(func, '__module__', '') or '',
            }
            if info['is_onchange']:
                info['onchange_triggers'] = list(getattr(func, '_onchange', []))
            if info['is_constrains']:
                info['constrains_fields'] = list(getattr(func, '_constrains', []))
            doc = inspect.getdoc(func)
            if doc:
                info['doc'] = doc[:300]
            try:
                sig = inspect.signature(func)
                params = [p for p in sig.parameters if p != 'self']
                if params:
                    info['params'] = params
            except (ValueError, TypeError):
                pass
            result.append(info)

        return sorted(result, key=lambda m: (not m['is_action'], not m['is_onchange'], m['name']))

    @api.model
    def get_onchange_methods(self, model_name):
        """Return {field_name: [method_name, …]} for all @api.onchange-decorated methods."""
        if model_name not in self.env.registry.models:
            return {}
        model_class = self.env.registry.models[model_name]
        mapping = {}
        for name in dir(model_class):
            if name.startswith('_'):
                continue
            func = getattr(model_class, name, None)
            if not callable(func):
                continue
            fn = getattr(func, '__func__', func)
            triggers = getattr(fn, '_onchange', None)
            if not triggers:
                continue
            for field_name in triggers:
                mapping.setdefault(field_name, []).append(name)
        return mapping

    # ------------------------------------------------------------------ #
    #  1.4 Route / controller scanner                                      #
    # ------------------------------------------------------------------ #

    @api.model
    def get_routes(self):
        from odoo.http import root
        routes = []
        try:
            router = root.get_db_router(self.env.cr.dbname)
            for rule in router.map._rules:
                endpoint = rule.endpoint
                routing = getattr(endpoint, 'routing', {})
                methods = rule.methods or set()
                routes.append({
                    'url': rule.rule,
                    'methods': sorted(methods - {'HEAD', 'OPTIONS'}),
                    'auth': routing.get('auth', 'user'),
                    'type': routing.get('type', 'http'),
                    'cors': routing.get('cors') or '',
                    'csrf': routing.get('csrf', True),
                    'website': routing.get('website', False),
                    'module': getattr(endpoint, '__module__', '') or '',
                    'endpoint': getattr(endpoint, '__qualname__', '') or str(endpoint),
                })
        except Exception as exc:
            _logger.warning("Kendrio route scan error: %s", exc)
        return sorted(routes, key=lambda r: r['url'])

    # ------------------------------------------------------------------ #
    #  1.5 Security scanner                                                #
    # ------------------------------------------------------------------ #

    @api.model
    def get_acl(self, model_name=None):
        domain = [('active', '=', True)]
        if model_name:
            domain.append(('model_id.model', '=', model_name))
        return self.env['ir.model.access'].sudo().search_read(
            domain,
            ['name', 'model_id', 'group_id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink'],
            limit=500,
        )

    @api.model
    def get_record_rules(self, model_name=None):
        domain = [('active', '=', True)]
        if model_name:
            domain.append(('model_id.model', '=', model_name))
        return self.env['ir.rule'].sudo().search_read(
            domain,
            ['name', 'model_id', 'groups', 'domain_force', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink'],
            limit=500,
        )

    # ------------------------------------------------------------------ #
    #  1.6 View scanner + arch parser                                      #
    # ------------------------------------------------------------------ #

    @api.model
    def get_model_views(self, model_name):
        return self.env['ir.ui.view'].sudo().search_read(
            [('model', '=', model_name), ('active', '=', True)],
            ['name', 'type', 'mode', 'priority'],
            limit=50,
            order='priority asc',
        )

    @api.model
    def get_model_view_detail(self, model_name, view_type='form'):
        """Parse the primary view arch — fields, buttons, domains, notebook pages."""
        from lxml import etree

        # 'list' is the UI alias; ir.ui.view stores it as 'tree'
        if view_type == 'list':
            view_type = 'tree'

        # Try canonical base view first, then fall back to any view of that type
        view = self.env['ir.ui.view'].sudo().search(
            [('model', '=', model_name), ('type', '=', view_type),
             ('active', '=', True), ('mode', '=', 'base')],
            limit=1, order='priority asc',
        )
        if not view:
            view = self.env['ir.ui.view'].sudo().search(
                [('model', '=', model_name), ('type', '=', view_type), ('active', '=', True)],
                limit=1, order='priority asc',
            )
        if not view:
            return None

        result = {
            'id': view.id,
            'name': view.name,
            'type': view_type,
            'mode': view.mode,
            'priority': view.priority,
            'fields': [],
            'buttons': [],
            'filters': [],
            'notebooks': [],
        }

        try:
            arch = etree.fromstring((view.arch_db or '').encode())
            for el in arch.iter('field'):
                fname = el.get('name')
                if not fname:
                    continue
                entry = {'name': fname}
                for attr in ('widget', 'invisible', 'required', 'readonly',
                             'domain', 'context', 'string', 'on_change'):
                    val = el.get(attr)
                    if val:
                        entry[attr] = val
                result['fields'].append(entry)

            for el in arch.iter('button'):
                entry = {'name': el.get('name', ''), 'type': el.get('type', ''),
                         'string': el.get('string', '')}
                for attr in ('confirm', 'states', 'attrs', 'invisible', 'class'):
                    val = el.get(attr)
                    if val:
                        entry[attr] = val
                result['buttons'].append(entry)

            for el in arch.iter('filter'):
                domain = el.get('domain', '')
                if domain:
                    result['filters'].append({
                        'string': el.get('string', ''),
                        'domain': domain,
                        'context': el.get('context', ''),
                    })

            for el in arch.iter('page'):
                result['notebooks'].append({'string': el.get('string', '')})

        except Exception as exc:
            result['parse_error'] = str(exc)

        return result

    # ------------------------------------------------------------------ #
    #  1.7 Action scanner (all types)                                     #
    # ------------------------------------------------------------------ #

    @api.model
    def get_window_actions(self, model_name=None):
        """Return ir.actions.act_window records, optionally filtered by model."""
        domain = []
        if model_name:
            domain = [('res_model', '=', model_name)]
        return self.env['ir.actions.act_window'].sudo().search_read(
            domain,
            ['name', 'res_model', 'view_mode', 'domain', 'context', 'target',
             'binding_model_id', 'groups_id', 'src_model', 'view_id'],
            limit=500,
        )

    @api.model
    def get_server_actions(self, model_name=None):
        domain = []
        if model_name:
            domain = [('model_id.model', '=', model_name)]
        return self.env['ir.actions.server'].sudo().search_read(
            domain,
            ['name', 'model_id', 'state', 'binding_model_id', 'binding_type'],
            limit=500,
        )

    @api.model
    def get_all_actions(self, model_name=None):
        """Return every action type in one call, grouped by type."""
        result = {
            'act_window': self.get_window_actions(model_name=model_name),
            'server': self.get_server_actions(model_name=model_name),
        }
        if not model_name:
            try:
                result['client'] = self.env['ir.actions.client'].sudo().search_read(
                    [], ['name', 'tag', 'params_store'], limit=200,
                )
            except Exception:
                result['client'] = []
            try:
                result['act_url'] = self.env['ir.actions.act_url'].sudo().search_read(
                    [], ['name', 'url', 'target'], limit=200,
                )
            except Exception:
                result['act_url'] = []
        return result

    # ------------------------------------------------------------------ #
    #  1.8 Menu scanner                                                    #
    # ------------------------------------------------------------------ #

    @api.model
    def get_menus(self):
        """Return the full ir.ui.menu tree as a flat list with parent_id references."""
        menus = self.env['ir.ui.menu'].sudo().search_read(
            [('active', '=', True)],
            ['name', 'parent_id', 'complete_name', 'action', 'sequence', 'web_icon'],
            order='complete_name',
        )
        # Annotate with child count
        parent_counts = {}
        for m in menus:
            pid = m['parent_id'][0] if m['parent_id'] else None
            if pid:
                parent_counts[pid] = parent_counts.get(pid, 0) + 1
        for m in menus:
            m['child_count'] = parent_counts.get(m['id'], 0)
        return menus

    # ------------------------------------------------------------------ #
    #  1.9 State-machine / workflow scanner                                #
    # ------------------------------------------------------------------ #

    @api.model
    def get_state_machine(self, model_name):
        """
        Detect state machines in a model:
          • Selection fields with tracking=True or named 'state'/'status'/'kanban_state'
          • stage_id Many2one fields pointing to stage/type models
          • statusbar widgets + state-dependent buttons from form views
        """
        if model_name not in self.env.registry.models:
            return None
        try:
            model = self.env[model_name]
        except Exception:
            return None

        _state_names = frozenset({'state', 'status', 'kanban_state', 'state_id'})
        state_fields = {}
        stage_fields = {}

        for fname, field in model._fields.items():
            if field.type == 'selection':
                is_state = fname in _state_names or bool(getattr(field, 'tracking', False))
                if is_state:
                    try:
                        sel = field.selection
                        state_fields[fname] = {
                            'string': field.string or fname,
                            'states': list(sel) if not callable(sel) else [],
                            'tracking': bool(getattr(field, 'tracking', False)),
                            'readonly': bool(field.readonly),
                        }
                    except Exception:
                        pass
            elif field.type == 'many2one':
                if fname in ('stage_id', 'stage') or (
                    getattr(field, 'comodel_name', '') or ''
                ).endswith(('.stage', '.type', '.stage.type')):
                    comodel = getattr(field, 'comodel_name', '') or ''
                    entry = {'string': field.string or fname, 'comodel': comodel}
                    if comodel:
                        try:
                            stages = self.env[comodel].sudo().search_read(
                                [], ['name', 'sequence'], limit=20, order='sequence',
                            )
                            entry['stages'] = stages
                        except Exception:
                            pass
                    stage_fields[fname] = entry

        if not state_fields and not stage_fields:
            return {'model': model_name, 'has_state_machine': False}

        # Parse form views to find statusbar widgets and state-dependent buttons
        from lxml import etree
        transitions = []
        statusbar_widgets = []

        views = self.env['ir.ui.view'].sudo().search(
            [('model', '=', model_name), ('type', '=', 'form'), ('active', '=', True)],
            limit=5, order='priority asc',
        )
        for view in views:
            try:
                arch = etree.fromstring((view.arch_db or '').encode())

                for el in arch.iter('field'):
                    if el.get('widget') in ('statusbar', 'priority'):
                        fname = el.get('name', '')
                        if fname:
                            statusbar_widgets.append({
                                'field': fname,
                                'widget': el.get('widget'),
                                'statusbar_visible': el.get('statusbar_visible', ''),
                                'clickable': el.get('clickable', 'false'),
                            })

                for el in arch.iter('button'):
                    btn_name = el.get('name', '')
                    btn_states = el.get('states', '')
                    invisible = el.get('invisible', '') or el.get('attrs', '')
                    if btn_name:
                        transitions.append({
                            'method': btn_name,
                            'label': el.get('string', ''),
                            'type': el.get('type', ''),
                            'visible_in_states': [s.strip() for s in btn_states.split(',') if s.strip()],
                            'invisible_expr': invisible,
                            'confirm': el.get('confirm', ''),
                        })
            except Exception:
                pass

        return {
            'model': model_name,
            'has_state_machine': True,
            'state_fields': state_fields,
            'stage_fields': stage_fields,
            'statusbar_widgets': statusbar_widgets,
            'transitions': transitions,
        }

    # ------------------------------------------------------------------ #
    #  1.10 Context / domain behavior scanner                              #
    # ------------------------------------------------------------------ #

    @api.model
    def get_model_context_behavior(self, model_name):
        """
        Extract context defaults and domain patterns from:
          • ir.actions.act_window contexts and domains
          • record rules (ir.rule) domain_force
          • view arch — per-field domain= and context= attributes
        """
        result = {
            'model': model_name,
            'window_action_contexts': [],
            'window_action_domains': [],
            'record_rule_domains': [],
            'field_domains': [],
            'field_contexts': [],
        }

        # Window actions
        for action in self.env['ir.actions.act_window'].sudo().search(
            [('res_model', '=', model_name)], limit=20
        ):
            if action.context and action.context not in ('{}', 'False', ''):
                result['window_action_contexts'].append({
                    'action': action.name,
                    'context': action.context,
                })
            if action.domain and action.domain not in ('[]', 'False', ''):
                result['window_action_domains'].append({
                    'action': action.name,
                    'domain': action.domain,
                })

        # Record rules
        for rule in self.env['ir.rule'].sudo().search(
            [('model_id.model', '=', model_name), ('active', '=', True)], limit=20
        ):
            if rule.domain_force:
                result['record_rule_domains'].append({
                    'rule': rule.name,
                    'domain': rule.domain_force,
                    'groups': [g.name for g in rule.groups],
                })

        # View field attrs
        from lxml import etree
        views = self.env['ir.ui.view'].sudo().search(
            [('model', '=', model_name), ('active', '=', True)],
            limit=10, order='priority asc',
        )
        seen = set()
        for view in views:
            try:
                arch = etree.fromstring((view.arch_db or '').encode())
                for el in arch.iter('field'):
                    fname = el.get('name', '')
                    domain = el.get('domain', '')
                    context = el.get('context', '')
                    key = (fname, view.id)
                    if key not in seen and (domain or context):
                        seen.add(key)
                        if domain:
                            result['field_domains'].append({'field': fname, 'domain': domain, 'view': view.name})
                        if context:
                            result['field_contexts'].append({'field': fname, 'context': context, 'view': view.name})
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------ #
    #  1.11 Modules                                                        #
    # ------------------------------------------------------------------ #

    @api.model
    def get_modules(self):
        return self.env['ir.module.module'].sudo().search_read(
            [('state', '=', 'installed')],
            ['name', 'shortdesc', 'author', 'version', 'category_id'],
            order='name',
        )

    # ================================================================== #
    #  LAYER 2 — RPC EXAMPLE GENERATOR                                    #
    # ================================================================== #

    @api.model
    def generate_rpc_example(self, model_name, method='search_read'):
        base = {
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'model': model_name, 'method': method, 'args': [], 'kwargs': {}},
        }
        if method == 'search_read':
            base['params']['args'] = [[]]
            base['params']['kwargs'] = {
                'fields': self._sample_fields(model_name),
                'limit': 10, 'offset': 0, 'order': 'id desc',
            }
        elif method == 'create':
            base['params']['args'] = [self._sample_create_vals(model_name)]
        elif method == 'write':
            base['params']['args'] = [[1], {}]
        elif method == 'unlink':
            base['params']['args'] = [[1]]
        elif method == 'read':
            base['params']['args'] = [[1]]
            base['params']['kwargs'] = {'fields': self._sample_fields(model_name)}
        elif method == 'search':
            base['params']['args'] = [[]]
            base['params']['kwargs'] = {'limit': 10}
        elif method == 'default_get':
            base['params']['args'] = [self._sample_fields(model_name)]
        elif method == 'onchange':
            sample_field = (self._sample_fields(model_name, max_fields=1) or ['name'])[0]
            base['params']['args'] = [[], [sample_field], {sample_field: None}]
        return base

    def _sample_fields(self, model_name, max_fields=6):
        try:
            model = self.env[model_name]
            stored = [
                f.name for f in model._fields.values()
                if f.store and not f.compute and not f.related
                and f.type not in ('binary', 'html', 'image', 'one2many', 'many2many')
            ]
            return sorted(stored)[:max_fields] or ['id']
        except Exception:
            return ['id', 'name']

    def _sample_create_vals(self, model_name):
        vals = {}
        try:
            model = self.env[model_name]
            for fname, field in model._fields.items():
                if not (field.required and not field.compute and not field.related and fname != 'id'):
                    continue
                if field.type == 'char':
                    vals[fname] = f'Example {field.string or fname}'
                elif field.type in ('integer', 'float', 'monetary'):
                    vals[fname] = 0
                elif field.type == 'boolean':
                    vals[fname] = False
                elif field.type == 'many2one':
                    vals[fname] = 1
                elif field.type == 'selection':
                    try:
                        sel = field.selection
                        if sel and not callable(sel):
                            vals[fname] = sel[0][0]
                    except Exception:
                        pass
        except Exception:
            pass
        return vals

    # ================================================================== #
    #  LAYER 3 — POSTMAN COLLECTION V2.1 GENERATOR                        #
    # ================================================================== #

    @api.model
    def generate_postman_collection(self, model_names=None, max_models=50):
        from odoo.http import request as http_req
        base_url = 'http://localhost:8069'
        try:
            base_url = http_req.httprequest.host_url.rstrip('/')
        except Exception:
            pass

        if model_names is None:
            model_names = [
                m['name'] for m in self.get_all_models(include_abstract=False, include_transient=False)
            ][:max_models]

        def _rpc(name, model, method, args, kwargs, description=''):
            body = {
                'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                'params': {'model': model, 'method': method, 'args': args, 'kwargs': kwargs},
            }
            return {
                'name': name,
                'request': {
                    'method': 'POST',
                    'header': [
                        {'key': 'Content-Type', 'value': 'application/json'},
                        {'key': 'Cookie', 'value': 'session_id={{session_id}}'},
                    ],
                    'url': {
                        'raw': '{{base_url}}/web/dataset/call_kw',
                        'host': ['{{base_url}}'],
                        'path': ['web', 'dataset', 'call_kw'],
                    },
                    'body': {
                        'mode': 'raw',
                        'raw': json.dumps(body, indent=2),
                        'options': {'raw': {'language': 'json'}},
                    },
                    'description': description,
                },
            }

        def _get(name, path, description=''):
            return {
                'name': name,
                'request': {
                    'method': 'GET',
                    'header': [{'key': 'Cookie', 'value': 'session_id={{session_id}}'}],
                    'url': {
                        'raw': f'{{{{base_url}}}}{path}',
                        'host': ['{{base_url}}'],
                        'path': path.lstrip('/').split('/'),
                    },
                    'description': description,
                },
            }

        items = []

        # ── Auth ──────────────────────────────────────────────────────
        auth_body = {
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {'db': '{{db_name}}', 'login': '{{username}}', 'password': '{{password}}'},
        }
        items.append({
            'name': '00 — Auth',
            'item': [{
                'name': 'Authenticate (capture session_id)',
                'event': [{'listen': 'test', 'script': {'type': 'text/javascript', 'exec': [
                    "var c = pm.cookies.toObject();",
                    "if (c.session_id) pm.collectionVariables.set('session_id', c.session_id);",
                ]}}],
                'request': {
                    'method': 'POST',
                    'header': [{'key': 'Content-Type', 'value': 'application/json'}],
                    'url': {'raw': '{{base_url}}/web/session/authenticate',
                            'host': ['{{base_url}}'], 'path': ['web', 'session', 'authenticate']},
                    'body': {'mode': 'raw', 'raw': json.dumps(auth_body, indent=2),
                             'options': {'raw': {'language': 'json'}}},
                    'description': 'Returns session_id cookie. Test script auto-saves it.',
                },
            }],
        })

        # ── Kendrio metadata ──────────────────────────────────────────
        items.append({
            'name': '01 — Kendrio Metadata',
            'item': [
                _get('List models', '/kendrio/api/models'),
                _get('List routes', '/kendrio/api/routes'),
                _get('List menus', '/kendrio/api/menus'),
                _get('List all actions', '/kendrio/api/actions'),
                _get('List ACL', '/kendrio/api/acl'),
                _get('List record rules', '/kendrio/api/acl/rules'),
                _get('List installed modules', '/kendrio/api/modules'),
                _get('OpenAPI spec', '/kendrio/api/openapi.json'),
                _get('RPC log status', '/kendrio/api/rpc-logs/status'),
            ],
        })

        # ── Per-model ─────────────────────────────────────────────────
        for model_name in model_names:
            sample_fields = self._sample_fields(model_name)
            sample_vals = self._sample_create_vals(model_name)

            model_items = [
                _rpc('search_read', model_name, 'search_read',
                     [[]], {'fields': sample_fields, 'limit': 10, 'order': 'id desc'},
                     'Fetch records. Adjust domain and fields as needed.'),
                _rpc('default_get', model_name, 'default_get',
                     [sample_fields], {},
                     'Get default values for a new record.'),
                _rpc('create', model_name, 'create',
                     [sample_vals], {},
                     'Create a new record. Required fields pre-filled.'),
                _rpc('write', model_name, 'write',
                     [[1], {}], {},
                     'Update records by ID list. Replace [1] with real IDs.'),
                _rpc('unlink', model_name, 'unlink',
                     [[1]], {},
                     'Delete records by ID list. Irreversible.'),
            ]

            # Onchange examples
            try:
                for fname, method_names in self.get_onchange_methods(model_name).items():
                    for mname in method_names[:2]:
                        model_items.append(
                            _rpc(f'onchange/{fname}', model_name, 'onchange',
                                 [[], [fname], {fname: None}], {},
                                 f'Trigger onchange for field "{fname}".'),
                        )
            except Exception:
                pass

            # State machine examples
            try:
                sm = self.get_state_machine(model_name)
                if sm and sm.get('has_state_machine'):
                    for t in (sm.get('transitions') or [])[:3]:
                        method = t.get('method', '')
                        if method and t.get('type') == 'object':
                            model_items.append(
                                _rpc(f'action/{method}', model_name, method,
                                     [[1]], {},
                                     f'Button action: {t.get("label", method)}'),
                            )
            except Exception:
                pass

            items.append({'name': model_name, 'item': model_items})

        return {
            'info': {
                'name': 'Odoo Runtime API',
                'description': f'Auto-generated by Kendrio API Explorer — {base_url}',
                'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
            },
            'item': items,
            'variable': [
                {'key': 'base_url', 'value': base_url, 'type': 'string'},
                {'key': 'db_name', 'value': '', 'type': 'string'},
                {'key': 'username', 'value': 'admin', 'type': 'string'},
                {'key': 'password', 'value': 'admin', 'type': 'string'},
                {'key': 'session_id', 'value': '', 'type': 'string'},
            ],
        }

    # ================================================================== #
    #  LAYER 3 — OPENAPI 3.0 GENERATOR                                    #
    # ================================================================== #

    @api.model
    def generate_openapi(self, model_names=None):
        from odoo.http import request as http_req
        base_url = ''
        try:
            base_url = http_req.httprequest.host_url.rstrip('/')
        except Exception:
            pass

        if model_names is None:
            model_names = [
                m['name'] for m in self.get_all_models(include_abstract=False, include_transient=False)
            ]

        schemas = {}
        tags = []

        for model_name in model_names[:200]:
            try:
                model = self.env[model_name]
            except Exception:
                continue

            description = type(model)._description or model_name
            tags.append({'name': model_name, 'description': description})

            properties = {}
            required_fields = []
            for fname, field in sorted(model._fields.items()):
                json_type = dict(_FIELD_TO_JSON.get(field.type, {'type': 'string'}))
                json_type['title'] = field.string or fname
                if field.help:
                    json_type['description'] = field.help
                if field.type == 'selection':
                    try:
                        sel = field.selection
                        if sel and not callable(sel):
                            json_type['enum'] = [s[0] for s in sel]
                    except Exception:
                        pass
                if field.type in ('many2one', 'one2many', 'many2many'):
                    json_type['x-odoo-comodel'] = getattr(field, 'comodel_name', '') or ''
                properties[fname] = json_type
                if field.required and not field.compute and not field.related and fname != 'id':
                    required_fields.append(fname)

            schemas[model_name.replace('.', '_')] = {
                'type': 'object',
                'title': description,
                'description': f'Odoo model: {model_name}',
                'properties': properties,
                **(({'required': required_fields}) if required_fields else {}),
            }

        schemas.update(self._openapi_base_schemas())

        return {
            'openapi': '3.0.3',
            'info': {
                'title': 'Odoo Runtime API',
                'version': '17.0',
                'description': self._openapi_description(base_url),
            },
            'servers': [{'url': base_url or 'http://localhost:8069', 'description': 'Odoo instance'}],
            'tags': [
                {'name': '_auth', 'description': 'Authentication'},
                {'name': '_jsonrpc', 'description': 'Odoo JSON-RPC 2.0 gateway'},
                {'name': '_xmlrpc', 'description': 'Odoo XML-RPC (legacy)'},
                {'name': '_meta', 'description': 'Kendrio metadata endpoints'},
            ] + tags,
            'paths': self._openapi_paths(),
            'components': {
                'schemas': schemas,
                'securitySchemes': {
                    'sessionCookie': {
                        'type': 'apiKey',
                        'in': 'cookie',
                        'name': 'session_id',
                        'description': 'Obtain via POST /web/session/authenticate.',
                    },
                    'apiKeyHeader': {
                        'type': 'apiKey',
                        'in': 'header',
                        'name': 'X-Odoo-Session',
                        'description': 'Alternative to cookie — pass the session_id as a header.',
                    },
                },
            },
            'security': [{'sessionCookie': []}],
        }

    def _openapi_description(self, base_url):
        return (
            '## Odoo Runtime API\n\n'
            'Auto-generated from Odoo runtime metadata by **Kendrio API Explorer**.\n\n'
            '### Authentication\n'
            'Obtain a `session_id` cookie via `POST /web/session/authenticate`, then send it as a '
            'cookie on every subsequent request.\n\n'
            '### JSON-RPC 2.0 (modern — Odoo 17)\n'
            'All ORM and custom model operations go through `POST /web/dataset/call_kw`.\n\n'
            '### XML-RPC (legacy — all versions)\n'
            '- `POST /xmlrpc/2/common` — `version()`, `authenticate(db, login, password, {})`\n'
            '- `POST /xmlrpc/2/object` — `execute_kw(db, uid, password, model, method, args, kwargs)`\n\n'
            '**Example (Python xmlrpc.client):**\n'
            '```python\n'
            'import xmlrpc.client\n'
            'common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")\n'
            'uid = common.authenticate(db, username, password, {})\n'
            'models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")\n'
            'partners = models.execute_kw(db, uid, password,\n'
            '    "res.partner", "search_read", [[]], {"fields": ["name","email"],"limit":10})\n'
            '```\n'
        )

    def _openapi_base_schemas(self):
        return {
            '_JsonRpcRequest': {
                'type': 'object',
                'required': ['jsonrpc', 'method', 'params'],
                'properties': {
                    'jsonrpc': {'type': 'string', 'enum': ['2.0']},
                    'method': {'type': 'string', 'enum': ['call']},
                    'id': {'type': 'integer'},
                    'params': {
                        'type': 'object',
                        'required': ['model', 'method', 'args', 'kwargs'],
                        'properties': {
                            'model': {'type': 'string', 'description': 'Odoo model technical name'},
                            'method': {'type': 'string', 'description': 'ORM or custom method name'},
                            'args': {'type': 'array'},
                            'kwargs': {'type': 'object'},
                        },
                    },
                },
            },
            '_JsonRpcResponse': {
                'type': 'object',
                'properties': {
                    'jsonrpc': {'type': 'string'},
                    'id': {'type': 'integer'},
                    'result': {'description': 'Return value — shape depends on the method'},
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'integer'},
                            'message': {'type': 'string'},
                            'data': {'type': 'object'},
                        },
                    },
                },
            },
        }

    def _openapi_paths(self):
        return {
            # ── Auth ──────────────────────────────────────────────────
            '/web/session/authenticate': {
                'post': {
                    'tags': ['_auth'], 'summary': 'Create session — returns session_id cookie',
                    'operationId': 'authenticate', 'security': [],
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/_JsonRpcRequest'},
                                'example': {
                                    'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                                    'params': {'db': 'my_db', 'login': 'admin', 'password': 'admin'},
                                },
                            }
                        },
                    },
                    'responses': {'200': {'description': 'Session created — session_id set as cookie'}},
                }
            },
            # ── JSON-RPC gateway ──────────────────────────────────────
            '/web/dataset/call_kw': {
                'post': {
                    'tags': ['_jsonrpc'],
                    'summary': 'JSON-RPC 2.0 — universal ORM gateway',
                    'operationId': 'callKw',
                    'description': (
                        'All ORM operations (search_read, create, write, unlink, …) and custom model '
                        'methods are invoked through this single endpoint.\n\n'
                        'For `onchange` pass: `args = [record_ids, changed_field_names, values_dict]`\n'
                        'For `default_get` pass: `args = [field_name_list]`'
                    ),
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/_JsonRpcRequest'},
                                'examples': {
                                    'search_read': {'summary': 'search_read', 'value': {
                                        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                                        'params': {'model': 'res.partner', 'method': 'search_read',
                                                   'args': [[]], 'kwargs': {'fields': ['name', 'email'], 'limit': 10}},
                                    }},
                                    'create': {'summary': 'create', 'value': {
                                        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                                        'params': {'model': 'res.partner', 'method': 'create',
                                                   'args': [{'name': 'New Partner', 'email': 'new@example.com'}], 'kwargs': {}},
                                    }},
                                    'write': {'summary': 'write', 'value': {
                                        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                                        'params': {'model': 'res.partner', 'method': 'write',
                                                   'args': [[42], {'phone': '+1 555 0100'}], 'kwargs': {}},
                                    }},
                                    'unlink': {'summary': 'unlink', 'value': {
                                        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                                        'params': {'model': 'res.partner', 'method': 'unlink',
                                                   'args': [[42]], 'kwargs': {}},
                                    }},
                                    'default_get': {'summary': 'default_get', 'value': {
                                        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                                        'params': {'model': 'res.partner', 'method': 'default_get',
                                                   'args': [['name', 'type', 'country_id']], 'kwargs': {}},
                                    }},
                                    'onchange': {'summary': 'onchange', 'value': {
                                        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                                        'params': {'model': 'sale.order', 'method': 'onchange',
                                                   'args': [[], ['partner_id'], {'partner_id': 1}], 'kwargs': {}},
                                    }},
                                },
                            }
                        },
                    },
                    'responses': {
                        '200': {
                            'description': 'JSON-RPC 2.0 response envelope',
                            'content': {'application/json': {'schema': {'$ref': '#/components/schemas/_JsonRpcResponse'}}},
                        }
                    },
                }
            },
            # ── XML-RPC (documented, not callable from Swagger) ───────
            '/xmlrpc/2/common': {
                'post': {
                    'tags': ['_xmlrpc'],
                    'summary': 'XML-RPC common — version() and authenticate()',
                    'operationId': 'xmlrpcCommon',
                    'description': (
                        'XML-RPC endpoint for `version()` and `authenticate(db, login, password, {})`.\n\n'
                        'Returns the `uid` needed by `/xmlrpc/2/object`.\n\n'
                        '> **Note:** Swagger UI cannot send XML-RPC calls. Use a dedicated XML-RPC client.'
                    ),
                    'requestBody': {'content': {'text/xml': {'schema': {'type': 'string'}}}},
                    'responses': {'200': {'description': 'XML-RPC response', 'content': {'text/xml': {'schema': {'type': 'string'}}}}},
                }
            },
            '/xmlrpc/2/object': {
                'post': {
                    'tags': ['_xmlrpc'],
                    'summary': 'XML-RPC object — execute_kw(db, uid, password, model, method, args, kwargs)',
                    'operationId': 'xmlrpcObject',
                    'description': (
                        'XML-RPC endpoint for all ORM operations via `execute_kw`.\n\n'
                        '```python\n'
                        'models.execute_kw(db, uid, password,\n'
                        '    "res.partner", "search_read",\n'
                        '    [[["is_company","=",True]]],\n'
                        '    {"fields":["name","email"],"limit":5})\n'
                        '```'
                    ),
                    'requestBody': {'content': {'text/xml': {'schema': {'type': 'string'}}}},
                    'responses': {'200': {'description': 'XML-RPC response', 'content': {'text/xml': {'schema': {'type': 'string'}}}}},
                }
            },
            # ── Kendrio metadata ──────────────────────────────────────
            '/kendrio/api/models': {
                'get': {
                    'tags': ['_meta'], 'summary': 'List all registered models',
                    'operationId': 'listModels',
                    'parameters': [
                        {'name': 'include_abstract', 'in': 'query', 'schema': {'type': 'boolean', 'default': False}},
                        {'name': 'include_transient', 'in': 'query', 'schema': {'type': 'boolean', 'default': True}},
                    ],
                    'responses': {'200': {'description': 'Array of model metadata'}},
                }
            },
            '/kendrio/api/models/{model_name}': {
                'get': {
                    'tags': ['_meta'], 'summary': 'Full model detail — fields, methods, views, ACL, state machine',
                    'operationId': 'getModel',
                    'parameters': [{'name': 'model_name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}, 'example': 'sale.order'}],
                    'responses': {'200': {'description': 'Model detail'}, '404': {'description': 'Not found'}},
                }
            },
            '/kendrio/api/models/{model_name}/fields': {
                'get': {'tags': ['_meta'], 'summary': 'Fields of a model', 'operationId': 'getModelFields',
                        'parameters': [{'name': 'model_name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                        'responses': {'200': {'description': 'Array of field descriptors'}}},
            },
            '/kendrio/api/models/{model_name}/methods': {
                'get': {'tags': ['_meta'], 'summary': 'Public custom methods', 'operationId': 'getModelMethods',
                        'parameters': [{'name': 'model_name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                        'responses': {'200': {'description': 'Array of method descriptors'}}},
            },
            '/kendrio/api/models/{model_name}/views/{view_type}': {
                'get': {'tags': ['_meta'], 'summary': 'Parsed view arch — fields, buttons, domains',
                        'operationId': 'getModelViewDetail',
                        'parameters': [
                            {'name': 'model_name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}},
                            {'name': 'view_type', 'in': 'path', 'required': True,
                             'schema': {'type': 'string', 'enum': ['form', 'tree', 'search', 'kanban']}},
                        ],
                        'responses': {'200': {'description': 'Parsed view structure'}, '404': {'description': 'No view found'}}},
            },
            '/kendrio/api/models/{model_name}/rpc': {
                'get': {'tags': ['_meta'], 'summary': 'Generated JSON-RPC example for model+method',
                        'operationId': 'getModelRpcExample',
                        'parameters': [
                            {'name': 'model_name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}},
                            {'name': 'method', 'in': 'query',
                             'schema': {'type': 'string', 'default': 'search_read', 'enum': _COMMON_ORM_METHODS}},
                        ],
                        'responses': {'200': {'description': 'Ready-to-use JSON-RPC request body'}}},
            },
            '/kendrio/api/models/{model_name}/state-machine': {
                'get': {'tags': ['_meta'], 'summary': 'State machine — selection states, stage fields, button transitions',
                        'operationId': 'getStateMachine',
                        'parameters': [{'name': 'model_name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                        'responses': {'200': {'description': 'State machine info or {has_state_machine: false}'}}},
            },
            '/kendrio/api/models/{model_name}/context': {
                'get': {'tags': ['_meta'], 'summary': 'Context/domain behavior — action contexts, record rule domains, field domains',
                        'operationId': 'getModelContextBehavior',
                        'parameters': [{'name': 'model_name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                        'responses': {'200': {'description': 'Context and domain patterns'}}},
            },
            '/kendrio/api/models/{model_name}/actions': {
                'get': {'tags': ['_meta'], 'summary': 'Actions bound to this model (window + server)',
                        'operationId': 'getModelActions',
                        'parameters': [{'name': 'model_name', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                        'responses': {'200': {'description': 'act_window and server actions'}}},
            },
            '/kendrio/api/routes': {
                'get': {'tags': ['_meta'], 'summary': 'All registered HTTP routes', 'operationId': 'listRoutes',
                        'responses': {'200': {'description': 'Array of route definitions'}}},
            },
            '/kendrio/api/menus': {
                'get': {'tags': ['_meta'], 'summary': 'Full ir.ui.menu tree (flat list with parent_id)',
                        'operationId': 'listMenus',
                        'responses': {'200': {'description': 'Array of menu entries'}}},
            },
            '/kendrio/api/actions': {
                'get': {'tags': ['_meta'], 'summary': 'All actions — act_window, server, client, url',
                        'operationId': 'listActions',
                        'parameters': [{'name': 'model', 'in': 'query', 'schema': {'type': 'string'}}],
                        'responses': {'200': {'description': 'Actions grouped by type'}}},
            },
            '/kendrio/api/acl': {
                'get': {'tags': ['_meta'], 'summary': 'Access control rules (ir.model.access)',
                        'operationId': 'listAcl',
                        'parameters': [{'name': 'model', 'in': 'query', 'schema': {'type': 'string'}}],
                        'responses': {'200': {'description': 'Array of ACL entries'}}},
            },
            '/kendrio/api/acl/rules': {
                'get': {'tags': ['_meta'], 'summary': 'Record rules (ir.rule)',
                        'operationId': 'listRecordRules',
                        'parameters': [{'name': 'model', 'in': 'query', 'schema': {'type': 'string'}}],
                        'responses': {'200': {'description': 'Array of record rules'}}},
            },
            '/kendrio/api/modules': {
                'get': {'tags': ['_meta'], 'summary': 'Installed modules', 'operationId': 'listModules',
                        'responses': {'200': {'description': 'Array of module metadata'}}},
            },
            '/kendrio/api/openapi.json': {
                'get': {'tags': ['_meta'], 'summary': 'This OpenAPI spec',
                        'operationId': 'getOpenApiSpec',
                        'parameters': [{'name': 'models', 'in': 'query',
                                        'description': 'Comma-separated model names (default: all, max 200)',
                                        'schema': {'type': 'string'}}],
                        'responses': {'200': {'description': 'OpenAPI 3.0.3 specification'}}},
            },
            '/kendrio/api/postman.json': {
                'get': {'tags': ['_meta'], 'summary': 'Postman Collection V2.1 download',
                        'operationId': 'getPostmanCollection',
                        'parameters': [
                            {'name': 'models', 'in': 'query', 'schema': {'type': 'string'}},
                            {'name': 'max_models', 'in': 'query', 'schema': {'type': 'integer', 'default': 50}},
                        ],
                        'responses': {'200': {'description': 'Postman Collection JSON'}}},
            },
            '/kendrio/api/rpc-logs': {
                'get': {'tags': ['_meta'], 'summary': 'Recent RPC log entries', 'operationId': 'listRpcLogs',
                        'parameters': [{'name': 'limit', 'in': 'query', 'schema': {'type': 'integer', 'default': 100}}],
                        'responses': {'200': {'description': 'Array of log records'}}},
            },
        }
