# Copyright 2026 Sienna Beauty Store
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models, tools


class MailMail(models.Model):
    _inherit = "mail.mail"

    sienna_is_recovery = fields.Boolean(copy=False)

    sienna_recovery_order_id = fields.Many2one(
        "sale.order", string="Sienna recovery order", copy=False,
        index=True, ondelete="set null",
    )

    def _sienna_recovery_recipient_matches(self):
        self.ensure_one()
        expected = tools.email_normalize(
            self.sienna_recovery_order_id.partner_id.email or ""
        )
        raw = tools.email_split(self.email_to or "")
        raw += tools.email_split(self.email_cc or "")
        raw += self.recipient_ids.mapped("email")
        actual = {tools.email_normalize(email or "") for email in raw}
        return bool(expected and actual == {expected})

    def _send(self, auto_commit=False, raise_exception=False, smtp_session=None):
        blocked = self.browse()
        for mail in self.filtered(lambda item: (
            item.state == "outgoing"
            and (item.sienna_is_recovery or item.sienna_recovery_order_id)
        )):
            order = mail.sienna_recovery_order_id
            # Flag remains true after native queue creation: do not test it here.
            if (not order or not order._sienna_recovery_orders()
                    or not order._sienna_recovery_ready_at_send()
                    or not mail._sienna_recovery_recipient_matches()):
                blocked |= mail
        if blocked:
            blocked.write({
                "state": "cancel",
                "failure_reason": "Sienna recovery: consent or eligibility no longer valid.",
            })
        remaining = self - blocked
        if not remaining:
            return True
        return super(MailMail, remaining)._send(
            auto_commit=auto_commit, raise_exception=raise_exception,
            smtp_session=smtp_session,
        )
