"""
Tests for crewai_x402.nano — feeless Nano settlement helpers.

Pure functions, no network access required. Covers exact integer conversion,
value preservation (never under-send on rounding), URI shape and validation.
"""

from __future__ import annotations

import unittest

from crewai_x402.nano import make_nano_pay_uri, micro_usd_to_raw

ACCOUNT = "nano_1yo6c1t64ahfjdw1dxizmbbnpdmbrckwhw9phbg5pdkeubrizga4qhnjmnx7"


class TestMicroUsdToRaw(unittest.TestCase):

    def test_positive_amount_produces_raw(self):
        raw = micro_usd_to_raw(1, 150_000_000)
        self.assertGreater(raw, 0)

    def test_zero_amount_is_zero_raw(self):
        self.assertEqual(micro_usd_to_raw(0, 150_000_000), 0)

    def test_negative_amount_raises(self):
        with self.assertRaises(ValueError):
            micro_usd_to_raw(-5, 150_000_000)

    def test_non_positive_price_raises(self):
        with self.assertRaises(ValueError):
            micro_usd_to_raw(10, 0)
        with self.assertRaises(ValueError):
            micro_usd_to_raw(10, -1)

    def test_value_preserved_never_under_sends(self):
        micro = 500
        price = 150_000_000
        raw = micro_usd_to_raw(micro, price)
        back_micro = (raw * price) // 10**30
        self.assertGreaterEqual(back_micro, micro)

    def test_exact_key_value(self):
        expected = -(-(10**30) // 150)  # ceil division
        self.assertEqual(micro_usd_to_raw(1_000_000, 150_000_000), expected)
        self.assertEqual(micro_usd_to_raw(1500, 150_000_000), 10**25)


class TestMakeNanoPayUri(unittest.TestCase):

    def test_produces_standard_uri(self):
        uri = make_nano_pay_uri(ACCOUNT, 123456)
        self.assertTrue(uri.startswith("nano:"))
        self.assertIn(ACCOUNT, uri)
        self.assertIn("?amount=123456", uri)

    def test_rejects_invalid_account(self):
        with self.assertRaises(ValueError):
            make_nano_pay_uri("0x1234", 1)
        with self.assertRaises(ValueError):
            make_nano_pay_uri("nano_not_an_account", 1)

    def test_label_and_message_appended(self):
        uri = make_nano_pay_uri(ACCOUNT, 7, {"label": "per-call", "message": "metered AI call"})
        self.assertIn("&label=per-call", uri)
        self.assertIn("&message=metered%20AI%20call", uri)

    def test_no_opts_no_extra_fields(self):
        uri = make_nano_pay_uri(ACCOUNT, 7)
        self.assertNotIn("&label=", uri)
        self.assertNotIn("&message=", uri)


if __name__ == "__main__":
    unittest.main()
