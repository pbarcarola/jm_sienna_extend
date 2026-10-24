# Copyright 2026 Sienna Beauty Store
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.addons.mail.models.mail_mail import MailMail as NativeMail


@tagged("post_install", "-at_install")
class TestSiennaRecoveryConsent(TransactionCase):
    """Only fictional .invalid addresses; SMTP replaced for every send test."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = cls.env["website"].create({
            "name": "QA Sienna consent", "domain": "https://www.livesienna.com",
            "company_id": cls.env.company.id, "cart_abandoned_delay": 1,
        })
        cls.community = cls.env["mailing.list"].create({"name": "QA community"})
        cls.mapping = cls.env["ir.model.data"].create({
            "module": "jm_sienna_extend", "name": "sienna_community_list",
            "model": "mailing.list", "res_id": cls.community.id,
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "QA recovery", "email": "sienna-recovery@example.invalid",
        })
        cls.product = cls.env["product.product"].create({
            "name": "QA recovery service", "type": "service", "list_price": 100,
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id, "website_id": cls.site.id,
            "date_order": fields.Datetime.now() - timedelta(hours=3),
            "order_line": [(0, 0, {
                "product_id": cls.product.id, "product_uom_qty": 1,
                "price_unit": 100,
            })],
        })
        cls.contact = cls.env["mailing.contact"].create({
            "name": "QA subscriber", "email": cls.partner.email,
        })
        cls.subscription = cls.env["mailing.contact.subscription"].create({
            "contact_id": cls.contact.id, "list_id": cls.community.id,
            "opt_out": False,
        })
        cls.template = cls.env["mail.template"].create({
            "name": "QA recovery", "model_id": cls.env.ref("sale.model_sale_order").id,
            "subject": "QA only", "email_from": "qa@example.invalid",
            "email_to": "{{ object.partner_id.email }}",
            "body_html": "<p>QA only</p>", "auto_delete": False,
        })
        cls.site.cart_recovery_mail_template_id = cls.template

    def _queued(self):
        mail_id = self.template.send_mail(self.order.id)
        self.assertTrue(mail_id)
        return self.env["mail.mail"].browse(mail_id)

    def _assert_blocked_at_send(self, mail):
        with patch.object(NativeMail, "_send", return_value=True) as smtp:
            mail._send()
            smtp.assert_not_called()
        self.assertEqual(mail.state, "cancel")

    def test_opt_in_and_native_sent_flag(self):
        self.assertEqual(self.order._filter_can_send_abandoned_cart_mail(), self.order)
        mail = self._queued()
        self.order.cart_recovery_email_sent = True
        with patch.object(NativeMail, "_send", return_value=True) as smtp:
            mail._send()
            smtp.assert_called_once()

    def test_no_consent(self):
        self.subscription.unlink()
        self.assertFalse(self.order._filter_can_send_abandoned_cart_mail())
        self.assertFalse(self.template.send_mail(self.order.id))

    def test_late_opt_out(self):
        mail = self._queued()
        self.subscription.opt_out = True
        self._assert_blocked_at_send(mail)

    def test_late_blacklist(self):
        mail = self._queued()
        self.env["mail.blacklist"].create({"email": self.partner.email})
        self._assert_blocked_at_send(mail)

    def test_duplicate_opt_out(self):
        other = self.env["mailing.contact"].create({"email": self.partner.email})
        self.env["mailing.contact.subscription"].create({
            "contact_id": other.id, "list_id": self.community.id, "opt_out": True,
        })
        self.assertFalse(self.order._filter_can_send_abandoned_cart_mail())

    def test_missing_mapping(self):
        self.mapping.unlink()
        self.assertFalse(self.template.send_mail(self.order.id))

    def test_late_sale_state(self):
        mail = self._queued()
        self.order.state = "sale"
        self._assert_blocked_at_send(mail)

    def test_later_purchase_native_rule(self):
        mail = self._queued()
        later = self.order.copy({"website_id": self.site.id})
        # copy() retained the abandoned date; simulate actual later confirmation.
        later.write({"state": "sale", "date_order": datetime.utcnow()})
        self._assert_blocked_at_send(mail)

    def test_changed_recipient(self):
        mail = self._queued()
        mail.email_to = "someone-else@example.invalid"
        self._assert_blocked_at_send(mail)

    def test_unrelated_mail_untouched(self):
        mail = self.env["mail.mail"].create({
            "subject": "QA transactional", "body_html": "<p>QA</p>",
            "email_from": "qa@example.invalid", "email_to": self.partner.email,
        })
        with patch.object(NativeMail, "_send", return_value=True) as smtp:
            mail._send()
            smtp.assert_called_once()

    def test_missing_order_is_blocked(self):
        mail = self._queued()
        mail.sienna_recovery_order_id = False
        self._assert_blocked_at_send(mail)

    def test_empty_or_invalid_address(self):
        self.partner.email = False
        self.assertFalse(self.order._filter_can_send_abandoned_cart_mail())

    def test_other_site_unchanged(self):
        self.site.domain = "https://other.example.invalid"
        self.subscription.opt_out = True
        self.assertEqual(self.order._filter_can_send_abandoned_cart_mail(), self.order)
