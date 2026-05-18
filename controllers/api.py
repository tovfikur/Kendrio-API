import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

_SWAGGER_HTML = """\
<!DOCTYPE html>
<html>
<head>
  <title>Kendrio API Explorer</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui.css">
  <style>body { margin: 0; }</style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui-bundle.js"></script>
<script src="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui-standalone-preset.js"></script>
<script>
window.onload = () => {
  SwaggerUIBundle({
    url: '/kendrio/api/openapi.json',
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
    plugins: [SwaggerUIBundle.plugins.DownloadUrl],
    layout: 'StandaloneLayout',
    tryItOutEnabled: true,
    requestCredentials: 'include',
    filter: true,
    defaultModelsExpandDepth: 0,
    tagsSorter: 'alpha',
  });
};
</script>
</body>
</html>"""


def _require_admin():
    if not request.env.user.has_group('base.group_system'):
        return _err('Forbidden: Settings / Technical access required', 403)
    return None


def _json(data, status=200, filename=None):
    headers = [('Access-Control-Allow-Origin', '*')]
    if filename:
        headers.append(('Content-Disposition', f'attachment; filename="{filename}"'))
    return Response(
        json.dumps(data, default=str),
        status=status,
        content_type='application/json',
        headers=headers,
    )


def _err(msg, status=400):
    return _json({'error': msg}, status)


def _scanner():
    return request.env['kendrio.scanner']


class KendrioApiController(http.Controller):

    # ------------------------------------------------------------------ #
    #  Swagger UI                                                          #
    # ------------------------------------------------------------------ #

    @http.route('/kendrio/swagger', type='http', auth='user', methods=['GET'], csrf=False)
    def swagger_ui(self, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return Response(_SWAGGER_HTML, content_type='text/html')

    # ------------------------------------------------------------------ #
    #  OpenAPI spec + Postman collection                                   #
    # ------------------------------------------------------------------ #

    @http.route('/kendrio/api/openapi.json', type='http', auth='user', methods=['GET'], csrf=False)
    def openapi_spec(self, models=None, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        model_names = [m.strip() for m in models.split(',') if m.strip()] if models else None
        return _json(_scanner().generate_openapi(model_names=model_names))

    @http.route('/kendrio/api/postman.json', type='http', auth='user', methods=['GET'], csrf=False)
    def postman_collection(self, models=None, max_models='50', **_kw):
        guard = _require_admin()
        if guard:
            return guard
        model_names = [m.strip() for m in models.split(',') if m.strip()] if models else None
        try:
            max_m = int(max_models)
        except (TypeError, ValueError):
            max_m = 50
        collection = _scanner().generate_postman_collection(model_names=model_names, max_models=max_m)
        return _json(collection, filename='odoo_api.postman_collection.json')

    # ------------------------------------------------------------------ #
    #  Model endpoints                                                     #
    # ------------------------------------------------------------------ #

    @http.route('/kendrio/api/models', type='http', auth='user', methods=['GET'], csrf=False)
    def list_models(self, include_abstract='false', include_transient='true', **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().get_all_models(
            include_abstract=(include_abstract.lower() == 'true'),
            include_transient=(include_transient.lower() == 'true'),
        ))

    @http.route('/kendrio/api/models/<string:model_name>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_model(self, model_name, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        data = _scanner().get_model_detail(model_name)
        return _json(data) if data else _err(f'Model not found: {model_name}', 404)

    @http.route('/kendrio/api/models/<string:model_name>/fields', type='http', auth='user', methods=['GET'], csrf=False)
    def get_model_fields(self, model_name, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        if model_name not in request.env.registry.models:
            return _err(f'Model not found: {model_name}', 404)
        return _json(_scanner().get_model_fields(model_name))

    @http.route('/kendrio/api/models/<string:model_name>/methods', type='http', auth='user', methods=['GET'], csrf=False)
    def get_model_methods(self, model_name, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        if model_name not in request.env.registry.models:
            return _err(f'Model not found: {model_name}', 404)
        return _json(_scanner().get_model_methods(model_name))

    @http.route('/kendrio/api/models/<string:model_name>/views/<string:view_type>',
                type='http', auth='user', methods=['GET'], csrf=False)
    def get_model_view_detail(self, model_name, view_type='form', **_kw):
        guard = _require_admin()
        if guard:
            return guard
        # 'list' is a user-friendly alias; the DB type is 'tree'
        resolved = 'tree' if view_type == 'list' else view_type
        data = _scanner().get_model_view_detail(model_name, view_type=resolved)
        return _json(data) if data else _err(f'No {view_type} view for: {model_name}', 404)

    @http.route('/kendrio/api/models/<string:model_name>/rpc', type='http', auth='user', methods=['GET'], csrf=False)
    def get_model_rpc_example(self, model_name, method='search_read', **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().generate_rpc_example(model_name, method=method))

    @http.route('/kendrio/api/models/<string:model_name>/state-machine',
                type='http', auth='user', methods=['GET'], csrf=False)
    def get_state_machine(self, model_name, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        if model_name not in request.env.registry.models:
            return _err(f'Model not found: {model_name}', 404)
        return _json(_scanner().get_state_machine(model_name))

    @http.route('/kendrio/api/models/<string:model_name>/context',
                type='http', auth='user', methods=['GET'], csrf=False)
    def get_model_context(self, model_name, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        if model_name not in request.env.registry.models:
            return _err(f'Model not found: {model_name}', 404)
        return _json(_scanner().get_model_context_behavior(model_name))

    @http.route('/kendrio/api/models/<string:model_name>/actions',
                type='http', auth='user', methods=['GET'], csrf=False)
    def get_model_actions(self, model_name, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        if model_name not in request.env.registry.models:
            return _err(f'Model not found: {model_name}', 404)
        return _json(_scanner().get_all_actions(model_name=model_name))

    # ------------------------------------------------------------------ #
    #  Routes                                                              #
    # ------------------------------------------------------------------ #

    @http.route('/kendrio/api/routes', type='http', auth='user', methods=['GET'], csrf=False)
    def list_routes(self, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().get_routes())

    # ------------------------------------------------------------------ #
    #  Menus                                                               #
    # ------------------------------------------------------------------ #

    @http.route('/kendrio/api/menus', type='http', auth='user', methods=['GET'], csrf=False)
    def list_menus(self, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().get_menus())

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    @http.route('/kendrio/api/actions', type='http', auth='user', methods=['GET'], csrf=False)
    def list_actions(self, model=None, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().get_all_actions(model_name=model))

    @http.route('/kendrio/api/actions/window', type='http', auth='user', methods=['GET'], csrf=False)
    def list_window_actions(self, model=None, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().get_window_actions(model_name=model))

    # ------------------------------------------------------------------ #
    #  Security                                                            #
    # ------------------------------------------------------------------ #

    @http.route('/kendrio/api/acl', type='http', auth='user', methods=['GET'], csrf=False)
    def list_acl(self, model=None, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().get_acl(model_name=model))

    @http.route('/kendrio/api/acl/rules', type='http', auth='user', methods=['GET'], csrf=False)
    def list_record_rules(self, model=None, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().get_record_rules(model_name=model))

    # ------------------------------------------------------------------ #
    #  Modules / server actions                                            #
    # ------------------------------------------------------------------ #

    @http.route('/kendrio/api/modules', type='http', auth='user', methods=['GET'], csrf=False)
    def list_modules(self, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().get_modules())

    @http.route('/kendrio/api/server-actions', type='http', auth='user', methods=['GET'], csrf=False)
    def list_server_actions(self, model=None, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        return _json(_scanner().get_server_actions(model_name=model))

    # ------------------------------------------------------------------ #
    #  RPC logs                                                            #
    # ------------------------------------------------------------------ #

    @http.route('/kendrio/api/rpc-logs', type='http', auth='user', methods=['GET'], csrf=False)
    def list_rpc_logs(self, limit='100', **_kw):
        guard = _require_admin()
        if guard:
            return guard
        try:
            limit = min(int(limit), 1000)
        except (TypeError, ValueError):
            limit = 100
        logs = request.env['kendrio.rpc.log'].sudo().search_read(
            [],
            ['model', 'method', 'user_id', 'duration', 'error', 'create_date'],
            limit=limit, order='id desc',
        )
        return _json(logs)

    @http.route('/kendrio/api/rpc-logs/status', type='http', auth='user', methods=['GET'], csrf=False)
    def rpc_log_status(self, **_kw):
        guard = _require_admin()
        if guard:
            return guard
        enabled = request.env['ir.config_parameter'].sudo().get_param(
            'kendrio.rpc.logging.enabled', 'false'
        ) == 'true'
        count = request.env['kendrio.rpc.log'].sudo().search_count([])
        return _json({'logging_enabled': enabled, 'total_log_entries': count})

    @http.route('/kendrio/api/rpc-logs/toggle', type='json', auth='user', methods=['POST'], csrf=False)
    def toggle_rpc_logging(self, enabled=True, **_kw):
        if not request.env.user.has_group('base.group_system'):
            return {'error': 'Forbidden'}
        request.env['ir.config_parameter'].sudo().set_param(
            'kendrio.rpc.logging.enabled',
            'true' if enabled else 'false',
        )
        return {'enabled': bool(enabled), 'message': f'RPC logging {"enabled" if enabled else "disabled"}'}
