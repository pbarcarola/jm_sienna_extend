# Copyright 2026 Sienna Beauty Store
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# QA candidate: never activate against customers before integration validation.
from odoo import models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def send_mail(self, res_id, force_send=False, raise_exception=False,
                  email_values=None, email_layout_xmlid=False):
        self.ensure_one()
        if self.model == "sale.order":
            order = self.env["sale.order"].browse(res_id).exists()
            if order._sienna_recovery_orders():
                recovery = order._get_cart_recovery_template()
                if self == recovery:
                    if (order.cart_recovery_email_sent
                            or not order._sienna_recovery_ready_at_send()):
                        return False
                    email_values = dict(email_values or {})
                    email_values["sienna_is_recovery"] = True
                    email_values["sienna_recovery_order_id"] = order.id
        return super().send_mail(
            res_id, force_send=force_send, raise_exception=raise_exception,
            email_values=email_values, email_layout_xmlid=email_layout_xmlid,
        )
