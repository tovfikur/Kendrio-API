from odoo import fields, models


class KendrioRpcLog(models.Model):
    _name = 'kendrio.rpc.log'
    _description = 'Kendrio RPC Log'
    _order = 'id desc'
    _rec_name = 'create_date'

    model = fields.Char(required=True, index=True, readonly=True)
    method = fields.Char(required=True, index=True, readonly=True)
    args_json = fields.Text(string='Args (JSON)', readonly=True)
    kwargs_json = fields.Text(string='Kwargs (JSON)', readonly=True)
    result_json = fields.Text(string='Result (JSON)', readonly=True)
    user_id = fields.Many2one('res.users', string='User', ondelete='set null', readonly=True)
    duration = fields.Float(string='Duration (s)', digits=(10, 4), readonly=True)
    error = fields.Text(string='Error', readonly=True)
    create_date = fields.Datetime(readonly=True)

    def action_clear_all_logs(self):
        self.sudo().search([]).unlink()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
