from odoo import api, fields, models


class KendrioRpcLogWizard(models.TransientModel):
    _name = 'kendrio.rpc.log.wizard'
    _description = 'Kendrio RPC Logging Settings'

    logging_enabled = fields.Boolean(
        string='Enable RPC Logging',
        default=lambda self: self._current_state(),
        help='When enabled, every call_kw request is recorded in the RPC Logs view.',
    )
    log_count = fields.Integer(
        string='Existing Log Entries',
        compute='_compute_log_count',
        readonly=True,
    )

    def _current_state(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'kendrio.rpc.logging.enabled', 'false'
        ) == 'true'

    @api.depends('logging_enabled')
    def _compute_log_count(self):
        count = self.env['kendrio.rpc.log'].sudo().search_count([])
        for rec in self:
            rec.log_count = count

    def action_apply(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'kendrio.rpc.logging.enabled',
            'true' if self.logging_enabled else 'false',
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Kendrio RPC Logging',
                'message': f'RPC logging {"enabled" if self.logging_enabled else "disabled"}.',
                'type': 'success',
                'sticky': False,
            },
        }

    def action_clear_logs(self):
        self.env['kendrio.rpc.log'].sudo().search([]).unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Kendrio RPC Logs',
                'message': 'All RPC log entries deleted.',
                'type': 'warning',
                'sticky': False,
            },
        }
