"""
isg-multi-tenant template loader.

Sektor sablonlarini (gida, tekstil, insaat, ...) yukleyip, tenant'a ozel
veri ile zenginlestirerek uygulama verisini uretir.

Kullanim:
  from backend.scripts.template_loader import load_template, get_questions

  tpl = load_template("gida_v1")
  questions = tpl["questions"]

CLI:
  python -m backend.scripts.template_loader --list
  python -m backend.scripts.template_loader --template gida_v1 --output backend/questions.json
  python -m backend.scripts.template_loader --template gida_v1 --summary
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT / "backend" / "templates"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def list_templates() -> list[dict[str, Any]]:
    """Mevcut tum sablonlari listele (metadata)."""
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            templates.append({
                "template_id": data.get("template_id", path.stem),
                "template_name": data.get("template_name", path.stem),
                "sector": data.get("sector", "?"),
                "version": data.get("version", "?"),
                "question_count": len(data.get("questions", [])),
                "path": str(path.relative_to(ROOT)),
            })
        except (OSError, json.JSONDecodeError) as e:
            print(f"UYARI: {path} okunamadi: {e}", file=sys.stderr)
    return templates


def load_template(template_id: str) -> dict[str, Any]:
    """
    Belirli bir sablonu yukler. template_id 'gida_v1' veya sadece 'gida' olabilir.

    Raises:
        FileNotFoundError: sablon bulunamazsa
    """
    if not TEMPLATES_DIR.exists():
        raise FileNotFoundError(f"Templates klasoru yok: {TEMPLATES_DIR}")

    # Direkt esleme
    direct = TEMPLATES_DIR / f"{template_id}.json"
    if direct.exists():
        return json.loads(direct.read_text(encoding="utf-8"))

    # Sektor + versiyon esleme (ornek: "gida" -> "gida_v1" ilk bulunan)
    sector_prefix = template_id.split("_")[0]
    for path in sorted(TEMPLATES_DIR.glob(f"{sector_prefix}_v*.json")):
        return json.loads(path.read_text(encoding="utf-8"))

    raise FileNotFoundError(
        f"Templat e bulunamadi: {template_id} "
        f"(denendi: {direct.name}, {sector_prefix}_v*.json)"
    )


def get_questions(template_id: str) -> list[dict[str, Any]]:
    """Sadece soru listesini getir (UI / API icin)."""
    tpl = load_template(template_id)
    return tpl.get("questions", [])


def get_regulatory_map(template_id: str) -> dict[int, dict[str, Any]]:
    """Sorularin mevzuat + yaptirim haritasini getir (PerQuestionReviewer icin)."""
    tpl = load_template(template_id)
    return tpl.get("regulatory_map", {})


def export_questions_json(template_id: str, output_path: Path) -> int:
    """
    Sablonun sorularini duz bir JSON array olarak yaz.
    (Mevcut backend/questions.json formatinda)
    Returns: yazilan soru sayisi
    """
    questions = get_questions(template_id)
    output_path.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return len(questions)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="ISG Multi-Tenant Template Loader")
    parser.add_argument("--list", action="store_true", help="Mevcut sablonlari listele")
    parser.add_argument("--template", type=str, help="Sablon ID (ornek: gida_v1)")
    parser.add_argument("--output", type=Path, help="Cikti JSON dosyasi")
    parser.add_argument("--summary", action="store_true", help="Sablon ozetini goster")
    args = parser.parse_args()

    if args.list:
        templates = list_templates()
        if not templates:
            print("Hicbir sablon bulunamadi.")
            return
        print(f"Toplam {len(templates)} sablon:")
        for t in templates:
            print(f"  - {t['template_id']:20s}  [{t['sector']:8s}]  v{t['version']:6s}  {t['question_count']:3d} soru  ({t['path']})")
        return

    if not args.template:
        parser.print_help()
        return

    tpl = load_template(args.template)

    if args.summary:
        print(f"Template: {tpl.get('template_name', args.template)}")
        print(f"  ID: {tpl.get('template_id')}")
        print(f"  Sektor: {tpl.get('sector')}")
        print(f"  Versiyon: {tpl.get('version')}")
        print(f"  Soru: {len(tpl.get('questions', []))}")
        print(f"  Kategoriler: {len(tpl.get('risk_categories', []))}")
        if tpl.get("regulatory_map"):
            print(f"  Regulatory map: {len(tpl['regulatory_map'])} soru")
        return

    if args.output:
        count = export_questions_json(args.template, args.output)
        print(f"[OK] {count} soru -> {args.output}")
    else:
        # Tek satirlik ozet
        print(json.dumps({
            "template_id": tpl.get("template_id"),
            "sector": tpl.get("sector"),
            "version": tpl.get("version"),
            "question_count": len(tpl.get("questions", [])),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
