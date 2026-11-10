"""Envelope encryption key-per-tenant + crypto-shred (pure)."""

import pytest

from traluat.w5.crypto import CryptoShredded, SoftwareKMS, TenantCrypto


def test_roundtrip_and_tenant_isolation():
    tc = TenantCrypto(SoftwareKMS())
    ct = tc.encrypt("tA", "hợp đồng bí mật của khách A")
    assert tc.decrypt("tA", ct) == "hợp đồng bí mật của khách A"
    # tenant B dùng DEK khác → không giải được ciphertext của A
    with pytest.raises(Exception):
        tc.decrypt("tB", ct)


def test_crypto_shred():
    tc = TenantCrypto(SoftwareKMS())
    ct = tc.encrypt("tA", "dữ liệu")
    tc.crypto_shred("tA")                       # xoá DEK → không giải được nữa
    with pytest.raises(CryptoShredded):
        tc.decrypt("tA", ct)


def test_wrapped_dek_not_plaintext():
    kms = SoftwareKMS()
    tc = TenantCrypto(kms)
    tc.encrypt("tA", "x")
    wrapped = tc.vault["tA"]
    # DEK lưu ở vault là BẢN BỌC (unwrap ra mới dùng được) — không phải key trần
    assert kms.unwrap(wrapped) != wrapped
