"""Canonical JSON serialization for content-addressed internal records."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel
from pydantic_core import PydanticSerializationError, to_jsonable_python


def _encode_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _mapping_key(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("canonical JSON mapping keys must be finite")
        return str(value)
    raise TypeError(f"unsupported canonical JSON mapping key type: {type(value).__name__}")


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {
            field_name: _json_value(getattr(value, field_name))
            for field_name in type(value).model_fields
        }
    if isinstance(value, Enum):
        return _json_value(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return _json_value(asdict(value))
    if isinstance(value, Mapping):
        normalized = {}
        for key, item in value.items():
            normalized_key = _mapping_key(key)
            if normalized_key in normalized:
                raise ValueError("canonical JSON mapping key collision after string conversion")
            normalized[normalized_key] = _json_value(item)
        return normalized
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized_items = [_json_value(item) for item in value]
        return sorted(normalized_items, key=_encode_json)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        json_leaf = to_jsonable_python(value)
    except PydanticSerializationError as error:
        raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}") from error
    return _json_value(json_leaf)


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize supported values as stable, compact UTF-8 JSON."""

    return _encode_json(_json_value(value))


def canonical_sha256(value: Any, *, domain: bytes) -> str:
    """Hash canonical content under a non-empty NUL-free domain."""

    if not isinstance(domain, bytes):
        raise TypeError("canonical hash domain must be bytes")
    if not domain or b"\0" in domain:
        raise ValueError("canonical hash domain must be non-empty and contain no NUL bytes")
    return hashlib.sha256(domain + b"\0" + canonical_json_bytes(value)).hexdigest()
