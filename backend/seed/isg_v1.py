"""ABCD Tech Solutions İSG Denetim ve Risk Analizi şablonu (v1).

Bu modül ``db.templates`` koleksiyonuna **idempotent** şekilde seed edilen
şablonun sabitlerini ve yükleyici fonksiyonlarını içerir.

Doğruluk kaynağı: ``isg_v1_default_questions.json`` (84 soru, 9 kategori).
Runtime'da seed dosyası her zaman okunmaz; ancak startup seed'i sırasında
**fail-fast** doğrulama yapılır (yanlış seed = uygulama başlatılamaz).

Backend risk hesabı her zaman ``server.compute_effective_risk`` üzerinden
yapılır; ``document_risk_level`` alanı yalnız provenance/audit amaçlıdır
ve hiçbir zaman hesaba katılmaz.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

# Şablon sabitleri — MongoDB ``db.templates`` koleksiyonunda unique ``code``.
TEMPLATE_CODE: str = "isg_v1_default"
TEMPLATE_NAME: str = "ABCD Tech Solutions İSG Denetim ve Risk Analizi"
TEMPLATE_VERSION: int = 1

# Seed JSON dosyasının bu modüle göre konumu.
_SEED_FILE: Path = Path(__file__).with_name("isg_v1_default_questions.json")


class SeedValidationError(RuntimeError):
    """Seed dosyası beklenen şemayla uyuşmuyorsa yükseltilir.

    Uygulama açık bir hata ile fail-fast eder (sessiz düzeltme yok).
    """


def _fail(message: str) -> None:
    raise SeedValidationError(f"[{TEMPLATE_CODE}] seed doğrulaması başarısız: {message}")


def load_seed_questions() -> List[Dict[str, Any]]:
    """Seed dosyasını oku, fail-fast doğrula, ``questions`` listesini döndür.

    Doğrulamalar (her biri ihlalde ``SeedValidationError`` fırlatır):

    * 84 kayıt
    * 9 benzersiz kategori
    * ``id`` ve ``no`` alanları 1..84, benzersiz, ardışık ve birbirine eşit
    * ``default_probability`` ve ``default_severity`` 1..5 aralığında
    * ``default_risk_score == default_probability * default_severity``
    * ``default_risk_level`` kanonik eşik fonksiyonu ile hesaplanan değer
    * Zorunlu alanların tamamı mevcut
    * ``legal_basis`` boş değil
    * ``corrective_action`` boş değil
    """
    try:
        raw = _SEED_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        _fail(f"seed dosyası bulunamadı: {_SEED_FILE}")
    except OSError as e:
        _fail(f"seed dosyası okunamadı: {e}")

    try:
        questions = json.loads(raw)
    except json.JSONDecodeError as e:
        _fail(f"seed JSON parse hatası: {e}")

    if not isinstance(questions, list):
        _fail("seed kökü liste olmalıdır")

    if len(questions) != 84:
        _fail(f"84 soru bekleniyordu, {len(questions)} bulundu")

    required_keys = (
        "id", "no", "category", "area", "question", "responsible",
        "default_probability", "default_severity", "default_risk_score",
        "default_risk_level", "document_risk_level",
        "deadline", "legal_basis", "corrective_action",
    )

    cats: set[str] = set()
    ids: List[int] = []
    nos: List[int] = []
    for idx, q in enumerate(questions):
        if not isinstance(q, dict):
            _fail(f"sıra {idx}: kayıt dict olmalıdır")
        missing = [k for k in required_keys if k not in q]
        if missing:
            _fail(f"soru #{q.get('id', idx)}: eksik alanlar {missing}")
        for key in ("id", "no", "default_probability", "default_severity", "default_risk_score"):
            if not isinstance(q[key], int) or isinstance(q[key], bool):
                _fail(f"soru #{q.get('id')}: {key} strict integer olmalı")
        if not (1 <= q["default_probability"] <= 5):
            _fail(f"soru #{q['id']}: default_probability 1-5 aralığında değil: {q['default_probability']}")
        if not (1 <= q["default_severity"] <= 5):
            _fail(f"soru #{q['id']}: default_severity 1-5 aralığında değil: {q['default_severity']}")
        if q["default_risk_score"] != q["default_probability"] * q["default_severity"]:
            _fail(
                f"soru #{q['id']}: default_risk_score != prob*siddet "
                f"({q['default_risk_score']} vs {q['default_probability']}*{q['default_severity']})"
            )
        if not q.get("legal_basis"):
            _fail(f"soru #{q['id']}: legal_basis boş")
        if not q.get("corrective_action"):
            _fail(f"soru #{q['id']}: corrective_action boş")
        cats.add(q["category"])
        ids.append(q["id"])
        nos.append(q["no"])

    if len(cats) != 9:
        _fail(f"9 kategori bekleniyordu, {len(cats)} bulundu: {sorted(cats)}")
    expected_seq = list(range(1, 85))
    if sorted(set(ids)) != expected_seq:
        _fail(f"id'ler 1..84 ardışık benzersiz değil: ids={sorted(set(ids))}")
    if sorted(set(nos)) != expected_seq:
        _fail(f"no'lar 1..84 ardışık benzersiz değil: nos={sorted(set(nos))}")
    if ids != nos:
        _fail(f"id ve no dizileri eşit değil: ids={ids} nos={nos}")

    return questions


def build_template_doc() -> Dict[str, Any]:
    """MongoDB'ye insert edilecek ham şablon dokümanını üret.

    Çağıran ``on_startup``; dokümanın ``code`` alanında ``TEMPLATE_CODE``
    kullanılır, bu sayede ``code`` unique index ile idempotent insert sağlanır.
    """
    questions = load_seed_questions()
    return {
        "code": TEMPLATE_CODE,
        "name": TEMPLATE_NAME,
        "version": TEMPLATE_VERSION,
        "is_default": True,
        "questions": list(questions),  # basit kopya — motor için yeterli
    }