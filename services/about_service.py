"""Developer metadata and version service functions."""

import base64
import hashlib
import hmac as _hmac
import json

import app_version

from services.errors import IntegrityError

K1 = b"\x4f\x70\x65\x6e\x41\x63\x63"
K2 = b"\x74\x32\x30\x32\x35\x58\x4f\x52"

BLOB = (
    "G*SypdqE}`S5q7n9U(PgP$&;G00tOc5M)#|D>pS#NlYX`Syo6@R#`bYJtGwc93T!O6JJqV"
    "S#~TvB2r0AE<ssVc2P!Dcn&c>1q>Z17YZ9(5PnoTARsOT3LH2?p~DhmMn^3yCOQHH0%11>2"
    "S!<3QUoCs4io?{VIm3!Q9@HwEN>Jp6A=M38bh{)5OMbFJvJZ`1VUjV5ffKlMqD;7aAQ&eOn"
    "X5K07gJT4|iZSCIk%|BTWDsUmssoDm5r7912WrK^j&F0s;qZV{kcAUrY`Y1{xA^QC2rPJUb"
    "B!8evgQL=a5"
)
SIG = "af144bbf0c67874df9f5011ec27e5dabd6ade51de190fc7f6d63d5f6080061b0"


def key() -> bytes:
    return K1 + K2


def secret() -> bytes:
    return hashlib.sha256(key() + b"\xde\xad\xbe\xef").digest()


def verify() -> bool:
    expected = _hmac.new(secret(), BLOB.encode(), hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, SIG)


def decode() -> dict:
    raw = base64.b85decode(BLOB.encode())
    full_key = key()
    extended = (full_key * ((len(raw) // len(full_key)) + 1))[: len(raw)]
    plain = bytes(a ^ b for a, b in zip(raw, extended))
    return json.loads(plain)


def get_about() -> dict:
    if not verify():
        raise IntegrityError(
            "About data integrity check failed. Source may have been tampered with."
        )
    decoded = decode()
    return {
        "name": decoded["n"],
        "email": decoded["e"],
        "org": decoded["o"],
        "github": decoded["g"],
        "year": decoded["y"],
        "version": app_version.full_app_title(),
        "tag": app_version.release_tag(),
    }


def get_version() -> dict:
    return app_version.version_payload()
