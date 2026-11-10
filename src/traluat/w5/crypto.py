"""Envelope encryption key-per-tenant (W5 §2.4, P3) — mã hoá dữ liệu khách at-rest.

Mỗi tenant 1 DEK; DEK bọc bằng khoá KMS (tenant.kms_key_id). Xoá/rotate DEK ⇒
crypto-shred (phục vụ quyền xoá + zero-retention). KMSProvider port: stub SoftwareKMS
(master key local) ↔ cloud KMS/Vault thật (cùng interface). Nội dung mã Fernet (AES128
+ HMAC). KHÔNG dùng cho KB công (chỉ dữ liệu khách).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cryptography.fernet import Fernet


class CryptoShredded(RuntimeError):
    """DEK của tenant đã bị xoá (crypto-shred) → không giải mã được."""


@runtime_checkable
class KMSProvider(Protocol):
    def wrap(self, dek: bytes) -> bytes: ...
    def unwrap(self, wrapped: bytes) -> bytes: ...


class SoftwareKMS:
    """Stub KMS — bọc DEK bằng master key local. Prod: thay bằng cloud KMS/HSM."""
    def __init__(self, master_key: bytes | None = None) -> None:
        self._f = Fernet(master_key or Fernet.generate_key())

    def wrap(self, dek: bytes) -> bytes:
        return self._f.encrypt(dek)

    def unwrap(self, wrapped: bytes) -> bytes:
        return self._f.decrypt(wrapped)


class RemoteKMSProvider:
    """KMS cắm-ngoài (HSM/cloud) qua 2 callable `wrap_fn/unwrap_fn` — không kéo SDK vào
    lõi. Dùng để bọc AWS KMS / Vault Transit / HSM tự quản mà vẫn giữ `KMSProvider` port.
    Test: truyền hàm khả-nghịch (mock) để kiểm roundtrip."""
    def __init__(self, wrap_fn, unwrap_fn) -> None:
        self._wrap = wrap_fn
        self._unwrap = unwrap_fn

    def wrap(self, dek: bytes) -> bytes:
        return self._wrap(dek)

    def unwrap(self, wrapped: bytes) -> bytes:
        return self._unwrap(wrapped)


class AwsKmsProvider:
    """AWS KMS — DEK được KMS encrypt (envelope). `client` = boto3 kms client (lazy;
    nêu rõ nếu thiếu boto3). `key_id` = CMK/HSM-backed key (CloudHSM key store)."""
    def __init__(self, key_id: str, *, client=None) -> None:
        if client is None:
            try:
                import boto3
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("AwsKmsProvider cần `boto3` (cài extra kms)") from e
            client = boto3.client("kms")
        self._c = client
        self._key_id = key_id

    def wrap(self, dek: bytes) -> bytes:
        return self._c.encrypt(KeyId=self._key_id, Plaintext=dek)["CiphertextBlob"]

    def unwrap(self, wrapped: bytes) -> bytes:
        return self._c.decrypt(CiphertextBlob=wrapped)["Plaintext"]


class VaultTransitProvider:
    """HashiCorp Vault Transit — wrap/unwrap DEK không rời Vault. `client` = hvac client
    (lazy). `key_name` = khoá transit (có thể HSM-backed qua Vault Enterprise seal)."""
    def __init__(self, key_name: str, *, client=None) -> None:
        import base64
        self._b64 = base64
        if client is None:
            try:
                import hvac
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("VaultTransitProvider cần `hvac` (cài extra kms)") from e
            client = hvac.Client()
        self._c = client
        self._key = key_name

    def wrap(self, dek: bytes) -> bytes:
        r = self._c.secrets.transit.encrypt_data(
            name=self._key, plaintext=self._b64.b64encode(dek).decode())
        return r["data"]["ciphertext"].encode()          # "vault:v1:..."

    def unwrap(self, wrapped: bytes) -> bytes:
        r = self._c.secrets.transit.decrypt_data(name=self._key, ciphertext=wrapped.decode())
        return self._b64.b64decode(r["data"]["plaintext"])


class TenantCrypto:
    """Quản DEK-per-tenant + mã/giải nội dung khách. `vault` lưu wrapped-DEK
    (prod: tenant.kms_key_id / Vault; mặc định in-memory)."""

    def __init__(self, kms: KMSProvider, vault: dict[str, bytes] | None = None) -> None:
        self.kms = kms
        self.vault = vault if vault is not None else {}   # tenant_id → wrapped DEK

    def _dek(self, tenant_id: str) -> bytes:
        wrapped = self.vault.get(tenant_id)
        if wrapped is None:
            dek = Fernet.generate_key()
            self.vault[tenant_id] = self.kms.wrap(dek)     # sinh + bọc lần đầu
            return dek
        return self.kms.unwrap(wrapped)

    def encrypt(self, tenant_id: str, plaintext: str) -> bytes:
        return Fernet(self._dek(tenant_id)).encrypt(plaintext.encode("utf-8"))

    def decrypt(self, tenant_id: str, ciphertext: bytes) -> str:
        if tenant_id not in self.vault:
            raise CryptoShredded(f"DEK tenant {tenant_id} đã xoá")
        return Fernet(self._dek(tenant_id)).decrypt(ciphertext).decode("utf-8")

    def crypto_shred(self, tenant_id: str) -> None:
        """Xoá DEK → mọi ciphertext của tenant không còn giải được (quyền xoá/zero-retention)."""
        self.vault.pop(tenant_id, None)
