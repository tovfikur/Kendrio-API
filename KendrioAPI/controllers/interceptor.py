"""
Layer 2 — Runtime RPC interceptor.

Subclasses Odoo's DataSet controller to log every call_kw request.
Logging is OFF by default; toggle via:
  API Explorer → RPC Logs → Settings (wizard)
  POST /kendrio/api/rpc-logs/toggle  {"enabled": true}
  ir.config_parameter  key: kendrio.rpc.logging.enabled  value: true

Log entries are written in a SEPARATE cursor so they survive transaction
rollbacks (e.g. a failed create still produces a log entry with the error).
"""
import json
import logging
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.web.controllers.dataset import DataSet as _BaseDataSet
except ImportError:
    try:
        from odoo.addons.web.controllers.main import DataSet as _BaseDataSet
    except ImportError:
        _BaseDataSet = None


if _BaseDataSet is not None:

    class KendrioDataSet(_BaseDataSet):
        """Logging wrapper around Odoo's DataSet.call_kw."""

        @http.route()
        def call_kw(self, model, method, args, kwargs, path=None):
            enabled = request.env['ir.config_parameter'].sudo().get_param(
                'kendrio.rpc.logging.enabled', 'false'
            )
            if enabled != 'true':
                return super().call_kw(model, method, args, kwargs, path=path)

            start = time.monotonic()
            error_msg = ''
            result = None
            try:
                result = super().call_kw(model, method, args, kwargs, path=path)
                return result
            except Exception as exc:
                error_msg = str(exc)[:500]
                raise
            finally:
                _write_log(
                    registry=request.env.registry,
                    uid=request.env.uid,
                    model=model,
                    method=method,
                    args=args,
                    kwargs=kwargs,
                    result=result,
                    duration=time.monotonic() - start,
                    error=error_msg,
                )

else:
    _logger.warning(
        "Kendrio: could not import DataSet controller — RPC interception unavailable. "
        "Ensure the 'web' module is installed."
    )


def _write_log(registry, uid, model, method, args, kwargs, result, duration, error):
    """
    Write a log entry using a fresh cursor so it commits independently of the
    main request transaction (important when the main tx is rolled back).
    """
    try:
        with registry.cursor() as new_cr:
            # request.env(cr=…) re-uses the same env/context but on the new cursor
            env = request.env(cr=new_cr)
            env['kendrio.rpc.log'].sudo().create({
                'model': model or '',
                'method': method or '',
                'args_json': _clip_json(args, 4096),
                'kwargs_json': _clip_json(kwargs, 4096),
                'result_json': _clip_json(result, 2048) if result is not None else '',
                'user_id': uid,
                'duration': duration,
                'error': error,
            })
    except Exception as exc:
        _logger.debug("Kendrio: RPC log write failed: %s", exc)


def _clip_json(obj, max_len):
    try:
        raw = json.dumps(obj, default=str)
        return raw[:max_len] if len(raw) > max_len else raw
    except Exception:
        return ''
