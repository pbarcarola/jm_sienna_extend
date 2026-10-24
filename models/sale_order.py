# Copyright 2026 Sienna Beauty Store
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# PROPOSAL ONLY: not deployed. Integrate and test on the deployed Odoo 16 branch.
from urllib.parse import urlsplit

from odoo import models, tools


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _sienna_recovery_orders(self):
        """Limit this proposal to the expressly authorized production domain."""
        def belongs_to_sienna(order):
            domain = (order.website_id.domain or "").strip()
            if not domain:
                return False
            parsed = urlsplit(domain if "://" in domain else "https://" + domain)
            return (parsed.hostname or "").lower() in {
                "livesienna.com", "www.livesienna.com"
            }
        return self.filtered(belongs_to_sienna)

    def _sienna_recovery_with_consent(self):
        """Read consent only; never change subscriptions, orders or prices."""
        if not self:
            return self
        if not all(name in self.env for name in (
            "mailing.contact.subscription", "mail.blacklist"
        )):
            return self.browse()

        # Bind this XML ID to the EXISTING community list during reviewed setup.
        # In the inspected production database that list is currently ID 10.
        # Never create/import subscribers automatically. Missing mapping denies sending.
        community = self.env.ref(
            "jm_sienna_extend.sienna_community_list", raise_if_not_found=False
        )
        if not community or community._name != "mailing.list" or not community.active:
            return self.browse()

        normalized_by_order = {
            order.id: tools.email_normalize(order.partner_id.email or "")
            for order in self
        }
        addresses = sorted({email for email in normalized_by_order.values() if email})
        if not addresses:
            return self.browse()

        subscriptions = self.env["mailing.contact.subscription"].sudo()
        opted_in = subscriptions.search([
            ("list_id", "=", community.id),
            ("contact_id.email_normalized", "in", addresses),
            ("opt_out", "=", False),
        ])
        # Conservative, matching the existing welcome filter: any recorded opt-out
        # for the normalized address wins, including duplicate contact records.
        opted_out = subscriptions.search([
            ("contact_id.email_normalized", "in", addresses),
            ("opt_out", "=", True),
        ])
        denied = self.env["mail.blacklist"].sudo().search([
            ("email", "in", addresses), ("active", "=", True),
        ])
        allowed = set(opted_in.mapped("contact_id.email_normalized"))
        allowed.difference_update(opted_out.mapped("contact_id.email_normalized"))
        allowed.difference_update(denied.mapped("email"))
        return self.filtered(lambda order: normalized_by_order[order.id] in allowed)

    def _filter_can_send_abandoned_cart_mail(self):
        # Keep the deployed parent's purchase/payment checks and then restrict consent.
        candidates = super()._filter_can_send_abandoned_cart_mail()
        sienna = candidates._sienna_recovery_orders()
        other_sites = candidates - sienna
        sienna = sienna.filtered(lambda order: (
            order.state in ("draft", "sent")
            and order.is_abandoned_cart
            and not order.cart_recovery_email_sent
        ))
        return other_sites | sienna._sienna_recovery_with_consent()

    def _sienna_recovery_ready_at_send(self):
        """Recheck the native rules without rejecting the already-queued flag."""
        eligible = self.browse()
        for website in self.mapped("website_id"):
            orders = self.filtered(lambda order: order.website_id == website)
            native = super(SaleOrder, orders)._filter_can_send_abandoned_cart_mail()
            native = native.filtered(lambda order: (
                order.state == "draft" and order.is_abandoned_cart
            ))
            eligible |= native._sienna_recovery_with_consent()
        return eligible

    def _cart_recovery_email_send(self):
        # Protect direct automation calls as well as the standard selector.
        sienna = self._sienna_recovery_orders()
        other_sites = self - sienna
        allowed = sienna._sienna_recovery_ready_at_send().filtered(
            lambda order: not order.cart_recovery_email_sent
        )
        return super(SaleOrder, other_sites | allowed)._cart_recovery_email_send()
