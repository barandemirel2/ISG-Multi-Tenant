"""Audit Report Columns (Phase 2B — S4+S6).

İş birimi kuralı (UAT S4+S6 — 2026-08-13):
    S4: ``Excel'deki 11 kolonlu resmi form düzeni nihaî olarak kabul ediliyor mu?``
        → "Hayır, kolon eklemesi yapılıp çıkarılabilmeli."
    S6: ``Excel ve PDF'nin kolon düzenlerinin birbirinden farklı olması bilinçli
        ve kabul edilebilir midir?``
        → "Kesinlikle aynı olmalı."

Bu modül:
    1. ``DEFAULT_COLUMNS`` — Excel ve PDF'in paylaştığı 11 kolon tanımı
    2. Her ``Column`` nesnesi başlık, key, format tipi, genişlik/ipucu içerir
    3. ``render_cell(column, audit_row)`` — kolon tipine göre değer üretir
    4. İleride admin UI ile ``audit_column_config`` koleksiyonundan
       kullanıcıya özel kolon seçimi yapılabilecek (S4'ün devamı).

Şu an hard-coded; S4'ün esneklik kısmı sonraki sprint'te admin UI ile
yapılacak. İş birimi kuralı S6 (Excel ve PDF kesinlikle aynı kolonları
kullanmalı) bu tek kaynaktan beslenir: hem ``export_excel`` hem
``export_pdf`` ``get_columns()`` üzerinden aynı semantik kolonları,
etiketleri ve sırayı tüketir (yalnız sunum metadata'sı exporter'a
özgü olabilir).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class Column:
    """Bir rapor kolonu tanımı.

    Attributes:
        key: Backend/frontend'de kullanılan alan adı (snake_case).
        header: Kullanıcıya görünen başlık (Türkçe).
        width: PDF için genişlik (mm); Excel için sütun pixel genişliği
              (yaklaşık 8.5 px/mm dönüşümü).
        align: Hücre hizalama — ``left``, ``center``, ``right``.
        kind: Değer tipi — ``text``, ``number``, ``risk_score``, ``risk_level``, ``answer``.
        multiline: Uzun metinler için satır kaydırma (True) veya kesme (False).
    """

    key: str
    header: str
    width: float
    align: str = "left"
    kind: str = "text"
    multiline: bool = False
    # Excel sütun genişliği (pixel, açık form düzeni sözleşmesi). PDF için
    # ``width`` (mm) kullanılır; Excel için ``excel_width``. ``None`` ise
    # ``width`` üzerinden yaklaşık dönüşüm uygulanır.
    excel_width: Optional[float] = None

    def render(self, row: Dict[str, Any]) -> str:
        """Satır dict'inden hücre değerini üret.

        ``row`` audit'in serialize edilmiş hali (answers, risk_overrides,
        effective_*, vb.).
        """
        renderer = _RENDERERS.get(self.kind, _render_text)
        return renderer(self, row)


# ──────────────────────────────────────────────────────────────────
# Render yardımcıları
# ──────────────────────────────────────────────────────────────────

def _render_text(col: Column, row: Dict[str, Any]) -> str:
    return str(row.get(col.key, "") or "").strip() or "—"


def _render_number(col: Column, row: Dict[str, Any]) -> str:
    v = row.get(col.key)
    if v is None or v == "":
        return "—"
    try:
        return str(int(v)) if float(v).is_integer() else f"{float(v):.1f}"
    except (TypeError, ValueError):
        return str(v)


def _render_answer(col: Column, row: Dict[str, Any]) -> str:
    """EVET / HAYIR / N/A'yi renk kodu olmadan kısa text olarak."""
    v = row.get(col.key)
    if not v:
        return "—"
    return str(v)


def _render_risk_score(col: Column, row: Dict[str, Any]) -> str:
    score = row.get(col.key)
    if score is None or score == "":
        return "—"
    return f"{score} Puan"


def _render_risk_level(col: Column, row: Dict[str, Any]) -> str:
    level = row.get(col.key)
    return str(level or "—")


def _render_multiline(col: Column, row: Dict[str, Any]) -> str:
    v = str(row.get(col.key, "") or "").strip()
    return v if v else "—"


_RENDERERS: Dict[str, Callable[[Column, Dict[str, Any]], str]] = {
    "text": _render_text,
    "number": _render_number,
    "answer": _render_answer,
    "risk_score": _render_risk_score,
    "risk_level": _render_risk_level,
    "multiline": _render_multiline,
}


# ──────────────────────────────────────────────────────────────────
# DEFAULT KOLONLAR — Excel ve PDF'in paylaştığı 11 kolon
# ──────────────────────────────────────────────────────────────────

DEFAULT_COLUMNS: List[Column] = [
    Column(key="no", header="No", width=8, align="center", kind="number", excel_width=6),
    Column(key="kategori", header="Kategori", width=22, align="left", kind="text", excel_width=24),
    Column(key="soru", header="Tehlike & Risk Maddesi", width=46, align="left", kind="multiline", multiline=True, excel_width=55),
    Column(key="cevap", header="Cevap", width=12, align="center", kind="answer", excel_width=12),
    Column(key="olasilik", header="Olasılık (O)", width=11, align="center", kind="number", excel_width=12),
    Column(key="siddet", header="Şiddet (Ş)", width=11, align="center", kind="number", excel_width=12),
    Column(key="risk_skoru", header="Risk Skoru (R)", width=11, align="center", kind="risk_score", excel_width=14),
    Column(key="risk_seviyesi", header="Risk Seviyesi", width=18, align="center", kind="risk_level", excel_width=18),
    Column(key="sorumlu", header="Sorumlu", width=20, align="left", kind="text", excel_width=20),
    Column(key="termin", header="Termin Süresi", width=15, align="center", kind="text", excel_width=15),
    Column(key="tedbir", header="Alınması Gereken Tedbir (DÖF)", width=42, align="left", kind="multiline", multiline=True, excel_width=50),
]


def get_columns() -> List[Column]:
    """Aktif kolon listesini döndür.

    Şu an hard-coded; ileride ``audit_column_config`` koleksiyonundan
    admin UI ile seçilen kolonlar okunacak.
    """
    return list(DEFAULT_COLUMNS)


# ──────────────────────────────────────────────────────────────────
# Yardımcı: satırdan tüm kolon değerlerini sırayla getir
# ──────────────────────────────────────────────────────────────────

def render_row(row: Dict[str, Any], columns: Optional[List[Column]] = None) -> List[str]:
    """``row`` için tüm kolon değerlerini sırayla döndür."""
    cols = columns or get_columns()
    return [c.render(row) for c in cols]


def total_width(columns: Optional[List[Column]] = None) -> float:
    """Toplam genişlik (mm). PDF layout hesabı için."""
    return sum(c.width for c in (columns or get_columns()))


def num_columns() -> int:
    """Aktif kolon sayısı."""
    return len(get_columns())
