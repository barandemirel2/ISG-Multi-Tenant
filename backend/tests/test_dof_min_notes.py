"""S9 — DÖF Not + Güncelleyen Raporlarda.

DofUpdateInput Pydantic model'inin KAPATILDI durumu için:
  * ``notes`` min 20 karakter zorunlu
  * ``resolution_note`` da min 20 karakter zorunlu (verilmişse)

Diğer durumlar (AÇIK, İŞLEMDE) için notes opsiyonel (default "").
"""
import pytest
from pydantic import ValidationError


def test_dof_kapatildi_min_20_chars_notes():
    """KAPATILDI + 20+ karakter notes kabul."""
    from server import DofUpdateInput
    p = DofUpdateInput(status="KAPATILDI", notes="x" * 20)
    assert p.status == "KAPATILDI"
    assert len(p.notes) == 20


def test_dof_kapatildi_19_chars_notes_rejected():
    """KAPATILDI + 19 karakter notes → ValidationError."""
    from server import DofUpdateInput
    with pytest.raises(ValidationError) as exc:
        DofUpdateInput(status="KAPATILDI", notes="x" * 19)
    assert "KAPATILDI" in str(exc.value)
    assert "20 karakter" in str(exc.value)


def test_dof_kapatildi_empty_notes_rejected():
    """KAPATILDI + boş notes → ValidationError."""
    from server import DofUpdateInput
    with pytest.raises(ValidationError) as exc:
        DofUpdateInput(status="KAPATILDI", notes="")
    assert "KAPATILDI" in str(exc.value)


def test_dof_kapatildi_19_chars_resolution_note_rejected():
    """KAPATILDI + 19 karakter resolution_note → ValidationError."""
    from server import DofUpdateInput
    with pytest.raises(ValidationError) as exc:
        DofUpdateInput(
            status="KAPATILDI",
            notes="Bu 20+ karakter not icerigi yeterli uzunlukta",
            resolution_note="x" * 19,
        )
    assert "resolution_note" in str(exc.value)


def test_dof_acik_empty_notes_allowed():
    """AÇIK + boş notes kabul (default davranış)."""
    from server import DofUpdateInput
    p = DofUpdateInput(status="AÇIK", notes="")
    assert p.status == "AÇIK"
    assert p.notes == ""


def test_dof_islemde_short_notes_allowed():
    """İŞLEMDE + kısa notes kabul (sadece KAPATILDI zorunlu)."""
    from server import DofUpdateInput
    p = DofUpdateInput(status="İŞLEMDE", notes="başladı")
    assert p.status == "İŞLEMDE"
    assert p.notes == "başladı"


def test_dof_notes_trimmed():
    """Notes trim ediliyor (whitespace kırpılıyor)."""
    from server import DofUpdateInput
    p = DofUpdateInput(status="KAPATILDI", notes="   " + "x" * 20 + "   ")
    assert p.notes == "x" * 20  # whitespace kırpıldı


def test_dof_kapatildi_min_20_with_resolution_note():
    """KAPATILDI + 20+ notes + 20+ resolution_note kabul."""
    from server import DofUpdateInput
    p = DofUpdateInput(
        status="KAPATILDI",
        notes="Bu 20+ karakter not icerigi yeterli uzunlukta",
        resolution_note="Bu cozum notu 20+ karakter iceriyor",
    )
    assert p.status == "KAPATILDI"
    assert len(p.notes) >= 20
    assert len(p.resolution_note) >= 20
