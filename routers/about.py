"""
about.py — Open Accountant developer information.

The payload is XOR-encrypted with a key derived from two constants
assembled at runtime, then Base85-encoded. An HMAC-SHA256 seal
covers the encoded blob; tampered data will fail verification and
return HTTP 422 instead of the developer card.

  _K1 + _K2  →  XOR key
  sha256(key + \xde\xad\xbe\xef)  →  HMAC secret
  hmac_sha256(secret, BLOB)  →  _SIG (seal)
"""
import base64
import hashlib
import hmac as _hmac
import json

import app_version
from fastapi import APIRouter, HTTPException

router = APIRouter()

# ── Encrypted payload (XOR + Base85) ────────────────────────────────────────
_K1 = b'\x4f\x70\x65\x6e\x41\x63\x63'
_K2 = b'\x74\x32\x30\x32\x35\x58\x4f\x52'

_BLOB = (
    'G*SypdqE}`S5q7n9U(PgP$&;G00tOc5M)#|D>pS#NlYX`Syo6@R#`bYJtGwc93T!O6JJqV'
    'S#~TvB2r0AE<ssVc2P!Dcn&c>1q>Z17YZ9(5PnoTARsOT3LH2?p~DhmMn^3yCOQHH0%11>2'
    'S!<3QUoCs4io?{VIm3!Q9@HwEN>Jp6A=M38bh{)5OMbFJvJZ`1VUjV5ffKlMqD;7aAQ&eOn'
    'X5K07gJT4|iZSCIk%|BTWDsUmssoDm5r7912WrK^j&F0s;qZV{kcAUrY`Y1{xA^QC2rPJUb'
    'B!8evgQL=a5'
)

# ── Integrity seal (HMAC-SHA256 of _BLOB) ───────────────────────────────────
_SIG = 'af144bbf0c67874df9f5011ec27e5dabd6ade51de190fc7f6d63d5f6080061b0'


def _key() -> bytes:
    return _K1 + _K2


def _secret() -> bytes:
    return hashlib.sha256(_key() + b'\xde\xad\xbe\xef').digest()


def _verify() -> bool:
    """Return True iff _BLOB has not been tampered with."""
    expected = _hmac.new(_secret(), _BLOB.encode(), hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, _SIG)


def _decode() -> dict:
    raw = base64.b85decode(_BLOB.encode())
    k = _key()
    key_ext = (k * ((len(raw) // len(k)) + 1))[:len(raw)]
    plain = bytes(a ^ b for a, b in zip(raw, key_ext))
    return json.loads(plain)


# ── Endpoint ─────────────────────────────────────────────────────────────────
@router.get("/about")
def get_about():
    if not _verify():
        raise HTTPException(
            status_code=422,
            detail="About data integrity check failed. Source may have been tampered with."
        )
    d = _decode()
    return {
        "name":    d["n"],
        "email":   d["e"],
        "org":     d["o"],
        "github":  d["g"],
        "year":    d["y"],
        "version": app_version.full_app_title(),
        "tag":     app_version.release_tag(),
    }


@router.get("/version")
def get_version():
    return app_version.version_payload()
