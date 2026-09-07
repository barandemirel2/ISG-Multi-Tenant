"""DÖF termin string'lerini due_date hesabı için gün sayısına çevir.

İş birimi kuralı (UAT S1): "Termin Süresi alanı süre (örn: 30 gün, 2 ay) göstermeli,
alan adı ile içerik aynı anlamı taşımalı".

Desteklenen formatlar:
- "Sürekli" / "surekli" → ``None`` (anında müdahale, deadline yok — backend
  bu durumda DÖF'ü ``None`` due_date ile kaydeder, frontend özel badge
  ile gösterir: "SÜREKLİ — Anında Müdahale")
- "acil" / "Acil" → 1 (tek gün)
- "X gün" / "X ay" / "X hafta" / "X yıl" → X (birim çarpımıyla)
- "" / ``None`` / parse edilemez → ``None`` + log warning (caller default belirler)

Yeni davranış: eskiden "5 gün" → 90 gün (else branch) dönüyordu, şimdi
doğru 5 gün. Aynı şekilde "2 hafta" → 14 gün (eskiden 60), "1 yıl" →
365 gün (eskiden 30).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Strict parse: tüm string sadece "X birim" formatında olmalı, başka kelime olmamalı.
# ^...$ anchored, whitespace trim, sadece bilinen Türkçe zaman birimleri.
# Örnekler:
#   "1 Ay"     → 30
#   "5 gün"    → 5
#   "2 hafta"  → 14
#   "1 yıl"    → 365
#   "Sürekli"  → None (handled separately)
#   "acil"     → 1   (handled separately)
#   "yaklaşık 1 ay" → None (extra word, strict reject)
#   "5 gün."   → None (trailing punctuation, strict reject)
_STRICT_TERM_RE = re.compile(
    r"^(\d+)\s*(g[uü]n|hafta|ay|y[iı]l|saat)$",
    re.IGNORECASE | re.UNICODE,
)

# Strict "Sürekli" termin: tam olarak "sürekli" veya "surekli" olmalı, başka kelime olmamalı
_SUREKLI_TERMS = frozenset({"sürekli", "surekli"})

# Strict "acil" termin: tam olarak "acil" olmalı (noktasız), başka kelime olmamalı
_ACIL_TERMS = frozenset({"acil"})


def parse_deadline_to_days(deadline_str: Optional[str]) -> Optional[int]:
    """Termin string'ini gün sayısına çevir. ``None`` = deadline yok / parse edilemez.

    Strict parse — tüm string sadece bilinen formatlardan biri olmalı:
    1. Boş/None → ``None``
    2. Tam "Sürekli" / "surekli" → ``None`` (anında müdahale)
    3. Tam "acil" → 1 gün
    4. Tam "X {gün|ay|hafta|yıl|saat}" → sayısal dönüşüm
    5. Aksi → ``None`` + log warning (caller kendi default'unu uygular)

    İş birimi kuralı (UAT S1): "Termin Süresi alanı süre (örn: 30 gün, 2 ay)
    göstermeli, alan adı ile içerik aynı anlamı taşımalı" — strict parse
    "yaklaşık 1 ay" gibi belirsiz ifadeleri reddeder, içerik tam olarak
    "süre" olmalı.

    Örnekler:
        >>> parse_deadline_to_days("Sürekli")
        None
        >>> parse_deadline_to_days("acil")
        1
        >>> parse_deadline_to_days("1 Ay")
        30
        >>> parse_deadline_to_days("5 gün")
        5
        >>> parse_deadline_to_days("2 hafta")
        14
        >>> parse_deadline_to_days("1 yıl")
        365
        >>> parse_deadline_to_days("30 gün")
        30
        >>> parse_deadline_to_days("yaklaşık 1 ay")
        None  # strict: fazladan kelime
        >>> parse_deadline_to_days("5 gün.")
        None  # strict: trailing punctuation
    """
    if not deadline_str:
        return None
    d = str(deadline_str).strip().lower()
    if not d:
        return None

    # "Sürekli" termin: deadline yok
    if d in _SUREKLI_TERMS:
        return None

    # "acil" — special case, saha tespit anında müdahale
    if d in _ACIL_TERMS:
        return 1

    # Strict: tüm string sadece "X birim" formatında olmalı
    m = _STRICT_TERM_RE.match(d)
    if not m:
        logger.warning(
            "parse_deadline_to_days: termin parse edilemedi: %r (caller default uygulayacak)",
            deadline_str,
        )
        return None

    n = int(m.group(1))
    unit = m.group(2).lower()

    # saat → 1 gün (acil muadili)
    if unit == "saat":
        return 1
    # gün varyasyonları (Türkçe iki nokta üstüste opsiyonel)
    if unit in ("gün", "gun"):
        return n
    if unit == "hafta":
        return n * 7
    if unit == "ay":
        return n * 30
    if unit in ("yıl", "yil"):
        return n * 365

    # Buraya düşmemeli (regex sadece bilinen unit'leri match eder)
    logger.warning("parse_deadline_to_days: bilinmeyen birim: %r", unit)
    return None
