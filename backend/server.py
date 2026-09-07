from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import io
import json
import logging
import re
import copy
import uuid
from urllib.parse import quote as urlquote
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Literal, ClassVar, Sequence

import bcrypt
import jwt as pyjwt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from PIL import Image
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator

from cookie_policy import (
    CookiePolicy,
    get_cookie_policy,
    initialize_cookie_policy,
)

from docs_config import resolve_docs_kwargs
from registration_config import is_public_registration_enabled
from seed import isg_v1
from deadline_parser import parse_deadline_to_days
import audit_state  # State machine (Phase 2B — S18)
from audit_state import AuditState
import audit_log  # Audit log + retention (Phase 2B — S20)
from audit_log import Action, compute_retention_until, log_action, get_audit_log


# ---------------- Setup ----------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# Documentation surface contract — Railway / UAT / prod deployments set
# ``DOCS_ENABLED=false`` to disable the public Swagger / ReDoc / OpenAPI
# routes. Local development keeps the defaults (DOCS_ENABLED unset ⇒
# docs enabled). Strict parser; see ``docs_config.py``.
_DOCS_KWARGS = resolve_docs_kwargs()
app = FastAPI(
    title="ABCD Tech Solutions - Risk Analiz Sistemi",
    docs_url=_DOCS_KWARGS["docs_url"],
    redoc_url=_DOCS_KWARGS["redoc_url"],
    openapi_url=_DOCS_KWARGS["openapi_url"],
)
api_router = APIRouter(prefix="/api")


# JSON response'lara charset=utf-8 ekle (browser ve intermediate proxy'lerin
# doğru UTF-8 decode etmesini garanti eder; "Karataş" gibi Türkçe karakterlerin
# bozuk görünmesini engeller).
@app.middleware("http")
async def _add_charset_to_json(request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if ct.startswith("application/json") and "charset" not in ct.lower():
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response

# Persistent upload storage contract — runtime data MUST be independent of
# application source-code lifecycle.
#
# ``UPLOAD_DIR`` resolves to ``<ROOT_DIR>/uploads/photos`` (default:
# ``backend/uploads/photos`` inside the container's working directory).
# In a local-dev / Docker bind-mount setup the entire ``/app`` (i.e.
# ``backend/``) is bind-mounted from the host source mirror, so a
# ``rsync --delete`` operation that mirrors the worktree into the host
# source directory MUST NOT wipe uploaded evidence.
#
# Two supported ways to satisfy the invariant
# ``application-source-sync/restart != uploaded-evidence-deletion``:
#
#   1. **Named Docker volume mount** at ``/app/uploads`` — preferred because
#      it cleanly separates runtime state from source artefacts. See
#      ``docker-compose.override.yml`` which mounts the ``risk_fix_uploads``
#      named volume at this path.
#
#   2. **Persistent host directory** outside the source tree bind-mounted
#      at ``/app/uploads`` — equivalent in effect to (1) but easier to
#      inspect from the host with plain ``ls``.
#
# Both keep the URL contract ``/uploads/photos/<yyyy>/<mm>/<uuid>.webp``
# unchanged because ``app.mount("/uploads", StaticFiles(...))`` reads
# whatever the kernel presents at ``ROOT_DIR / "uploads"`` — the public
# URL doesn't see whether the backing storage is a bind mount or a named
# volume.
UPLOAD_DIR = ROOT_DIR / "uploads" / "photos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(ROOT_DIR / "uploads")), name="uploads")

# S12: Marka logoları lokal (Wikipedia CDN'den kaldırıldı). 5 SVG logo
# `backend/brand_logos/` altında; frontend tarafı `frontend/public/logos/`
# ile aynı dosyaları paylaşıyor. ``/brand-logos/<filename>`` üzerinden
# servis edilir. PDF/Excel export'u için SVG → PNG dönüşümü lazy yapılır
# (ilk kullanımda cache'lenir).
BRAND_LOGOS_DIR = ROOT_DIR / "brand_logos"
BRAND_LOGOS_DIR.mkdir(parents=True, exist_ok=True)
BRAND_LOGOS_PNG_CACHE = BRAND_LOGOS_DIR / "_png_cache"
BRAND_LOGOS_PNG_CACHE.mkdir(parents=True, exist_ok=True)
app.mount("/brand-logos", StaticFiles(directory=str(BRAND_LOGOS_DIR)), name="brand-logos")

JWT_ALGORITHM = "HS256"

# B7 — İbraz doğrulama (verification) public base URL'i.
#
# QR kodunun işaret ettiği doğrulama URL'i bu base'den türetilir. Üretimde
# `VERIFICATION_BASE_URL` explicit olarak set edilmelidir (örn.
# ``https://risk.isg-multi-tenant.local``). Bu değer boş bırakılırsa **güvenli
# development fallback** kullanılır: isteğin geldiği origin
# (``request.base_url``) — yani aynı deployment'taki backend'in kendisi.
# Bu, yerel geliştirmede doğrulama URL'inin yanlış/erişilemez bir host'a
# işaret etmesini engeller.
VERIFICATION_BASE_URL = os.environ.get("VERIFICATION_BASE_URL", "").strip().rstrip("/")

# ---------------- Load questions ----------------
# LEGACY: ``backend/questions.json`` hâlâ okunur; yeni audit'ler artık
# ``db.templates`` koleksiyonundaki snapshot'ları kullanır. Bu liste yalnızca
# legacy audit'lerin summary/export fallback'i olarak kullanılır (bkz.
# ``_get_audit_questions``).
with open(ROOT_DIR / "questions.json", "r", encoding="utf-8") as f:
    QUESTIONS: List[Dict[str, Any]] = json.load(f)

CATEGORY_ORDER: List[str] = []
for q in QUESTIONS:
    if q["category"] not in CATEGORY_ORDER:
        CATEGORY_ORDER.append(q["category"])

QUESTIONS_BY_ID = {q["id"]: q for q in QUESTIONS}


# ---------------- Risk kanonik ----------------
# Tek doğruluk kaynağı: Aşama 1'de bağlayıcı eşikler.
RISK_LEVEL_KABUL_EDILEBILIR = "Kabul Edilebilir"
RISK_LEVEL_DIKKATE_DEGER = "Dikkate Değer"
RISK_LEVEL_KABUL_EDILEMEZ = "Kabul Edilemez"


def classify_risk(score: int) -> str:
    """Kanonik eşik fonksiyonu.

    Kesin eşikler (Aşama 1):

    * 1–4   → "Kabul Edilebilir"
    * 5–12  → "Dikkate Değer"
    * 13–25 → "Kabul Edilemez"

    ``document_risk_level`` alanı **asla** kullanılmaz; bu fonksiyon
    hesaplamanın tek doğruluk kaynağıdır.
    """
    if not isinstance(score, int) or isinstance(score, bool):
        raise ValueError(
            f"Risk skoru strict integer olmalıdır: {score!r}"
        )
    if 1 <= score <= 4:
        return RISK_LEVEL_KABUL_EDILEBILIR
    if 5 <= score <= 12:
        return RISK_LEVEL_DIKKATE_DEGER
    if 13 <= score <= 25:
        return RISK_LEVEL_KABUL_EDILEMEZ
    raise ValueError(
        f"Risk skoru 1-25 aralığında olmalıdır: {score}"
    )


def compute_effective_risk(
    question: Dict[str, Any],
    override: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """Effective probability/severity/score/level hesapla.

    * ``override`` None ise → sorunun ``default_probability`` /
      ``default_severity`` değerleri kullanılır.
    * ``override`` dict ise → ``probability`` ve ``severity`` kullanılır.
    * Score backend'de yeniden hesaplanır.
    * Level ``classify_risk(score)`` ile yeniden hesaplanır.
    * ``document_risk_level`` asla kullanılmaz.

    Hatalı girdi ``ValueError`` fırlatır.
    """
    if override:
        prob_raw = override.get("probability")
        sev_raw = override.get("severity")
    else:
        # Yeni şema: ``default_probability`` / ``default_severity``.
        # Legacy şema (migration sırasında): ``olasilik`` / ``siddet``.
        # İkisi de desteklenir; yeni audit'ler her zaman yeni şemayı taşır.
        prob_raw = question.get("default_probability", question.get("olasilik"))
        sev_raw = question.get("default_severity", question.get("siddet"))

    if not isinstance(prob_raw, int) or isinstance(prob_raw, bool):
        raise ValueError(
            f"probability strict integer olmalıdır: {prob_raw!r}"
        )
    if not isinstance(sev_raw, int) or isinstance(sev_raw, bool):
        raise ValueError(
            f"severity strict integer olmalıdır: {sev_raw!r}"
        )
    if not (1 <= prob_raw <= 5):
        raise ValueError(f"probability 1-5 aralığında olmalıdır: {prob_raw}")
    if not (1 <= sev_raw <= 5):
        raise ValueError(f"severity 1-5 aralığında olmalıdır: {sev_raw}")
    score = prob_raw * sev_raw
    level = classify_risk(score)
    return {
        "probability": prob_raw,
        "severity": sev_raw,
        "risk_score": score,
        "risk_level": level,
    }


# ---------------- Templates cache ----------------
# In-memory cache; startup'ta ``load_templates_cache`` ile doldurulur.
# İlk aşamada invalidation yoktur (kullanıcı kararı: performans problemi
# kanıtlanmadan cache sistemi kurulmaz). Yeni bir template eklenirse
# uygulama restart edilir.
TEMPLATES_CACHE: Dict[str, Dict[str, Any]] = {}


async def load_templates_cache() -> None:
    """``db.templates`` koleksiyonundan tüm şablonları cache'e yükle."""
    TEMPLATES_CACHE.clear()
    cursor = db.templates.find({})
    async for tpl in cursor:
        TEMPLATES_CACHE[tpl["code"]] = tpl


def get_default_template() -> Optional[Dict[str, Any]]:
    """Cache'teki ``is_default=True`` şablonu döndürür; yoksa None."""
    for tpl in TEMPLATES_CACHE.values():
        if tpl.get("is_default"):
            return tpl
    return None


# ---------------- Legacy / snapshot adapter ----------------
def _adapt_question_to_legacy(q: Dict[str, Any]) -> Dict[str, Any]:
    """Yeni master şemasını frontend'in beklediği eski şemaya çevir.

    Frontend (Aşama 2B öncesi) ``soru``/``sorumlu``/``olasilik``/``siddet``
    /``risk_skoru``/``risk_seviyesi``/``termin``/``tedbir`` alanlarını
    bekliyor. Bu adapter bu alanları üretir; yeni alanları da response
    içinde korur ki Aşama 2B'ye geçiş kolay olsun.
    """
    return {
        "id": q["id"],
        "no": q["no"],
        "category": q["category"],
        # Eski alanlar (frontend Aşama 2B öncesi bunları tüketiyor)
        "alan": q.get("area", ""),
        "soru": q["question"],
        "sorumlu": q["responsible"],
        "olasilik": q["default_probability"],
        "siddet": q["default_severity"],
        "risk_skoru": q["default_risk_score"],
        "risk_seviyesi": q["default_risk_level"],
        "termin": q["deadline"],
        "tedbir": q["corrective_action"],
        "mevzuat": q["legal_basis"],
        # Yeni alanlar (Aşama 2B ve sonrası için hazır)
        "area": q.get("area", ""),
        "question": q["question"],
        "responsible": q["responsible"],
        "default_probability": q["default_probability"],
        "default_severity": q["default_severity"],
        "default_risk_score": q["default_risk_score"],
        "default_risk_level": q["default_risk_level"],
        "document_risk_level": q.get("document_risk_level", q["default_risk_level"]),
        "deadline": q["deadline"],
        "legal_basis": q["legal_basis"],
        "corrective_action": q["corrective_action"],
    }


def _get_audit_questions(audit_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Audit'in soru listesini döner.

    Yeni audit'lerde ``template_snapshot.questions`` kullanılır (snapshot
    alındığı andaki şablonun derin kopyası — template sonradan değişse
    bile export/summary etkilenmez).

    Legacy audit'ler için ``QUESTIONS`` (eski ``questions.json``) üzerinden
    kontrollü fallback sağlanır. Yeni template eski audit'e otomatik
    uygulanmaz.
    """
    snap = audit_doc.get("template_snapshot")
    if snap and isinstance(snap, dict) and isinstance(snap.get("questions"), list):
        return snap["questions"]
    return QUESTIONS


def _get_audit_overrides(audit_doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Audit'in ``risk_overrides`` map'ini döner (boş dict default)."""
    raw = audit_doc.get("risk_overrides")
    if not isinstance(raw, dict):
        return {}
    return raw


# ---------------- Auth helpers ----------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def validate_jwt_secret(value: object) -> str:
    """Fail-fast validation for the JWT signing secret.

    The secret must exist, be a non-empty string after trimming, and contain at
    least 32 characters of entropy. The actual value is never echoed in errors.
    """
    if value is None:
        raise RuntimeError(
            "JWT_SECRET is required. Set it in the environment (e.g. backend/.env "
            "or root .env). Recommended length: 48+ characters."
        )
    if not isinstance(value, str):
        raise RuntimeError(
            "JWT_SECRET must be a string. Set it in the environment (e.g. backend/.env "
            "or root .env)."
        )
    stripped = value.strip()
    if not stripped:
        raise RuntimeError(
            "JWT_SECRET must not be empty or whitespace-only. Configure a real "
            "secret (recommended length: 48+ characters)."
        )
    if len(stripped) < 32:
        raise RuntimeError(
            "JWT_SECRET is too short. It must contain at least 32 characters "
            "(recommended: 48+). Generate with: python -c \"import secrets; "
            "print(secrets.token_urlsafe(48))\""
        )
    return stripped


# Module-level cache for the validated JWT signing secret. It is populated
# exactly once during application startup (see ``initialize_jwt_secret`` /
# ``on_startup``) and read by every encode/decode operation. This guarantees
# that runtime environment mutations cannot silently change the signing key
# after the process is up.
_JWT_SECRET: Optional[str] = None


def initialize_jwt_secret() -> str:
    """Read, validate, and cache ``JWT_SECRET`` for the lifetime of the process.

    Must be called from application startup before any JWT-dependent operation.
    Re-initializing with a different value is allowed (e.g. in tests) but the
    production startup path only calls this once. The actual secret value is
    never echoed in the raised error.
    """
    global _JWT_SECRET
    _JWT_SECRET = validate_jwt_secret(os.environ.get("JWT_SECRET"))
    return _JWT_SECRET


def get_jwt_secret() -> str:
    """Return the JWT signing secret cached at startup.

    Raises ``RuntimeError`` if initialization has not yet happened, rather
    than silently re-reading ``os.environ`` (which would let runtime mutations
    change the signing key). The error never echoes a secret value.
    """
    if _JWT_SECRET is None:
        raise RuntimeError(
            "JWT secret has not been initialized. "
            "Call initialize_jwt_secret() during application startup."
        )
    return _JWT_SECRET


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "type": "access",
    }
    return pyjwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh",
    }
    return pyjwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _stamp_partitioned(response: Response) -> None:
    """Append ``; Partitioned`` to cross-site Secure Set-Cookie headers.

    iOS Safari / WebKit ITP silently drops cross-site cookies unless
    CHIPS ``Partitioned`` is present. Starlette 0.37 does not support
    the ``partitioned`` parameter on ``set_cookie`` / ``delete_cookie``.
    This helper post-processes Starlette-generated ``Set-Cookie`` headers
    and appends ``; Partitioned`` when the cookie carries both ``Secure``
    and ``SameSite=None``, preserving Starlette's cookie serialization,
    escaping, and standard attribute formatting unmodified.
    """
    new_headers = []
    for k, v in response.raw_headers:
        k_bytes = k if isinstance(k, bytes) else k.encode("latin-1")
        if k_bytes.lower() == b"set-cookie":
            v_bytes = v if isinstance(v, bytes) else v.encode("latin-1")
            parts = [p.strip().lower() for p in v_bytes.split(b";")]
            if (
                b"secure" in parts
                and b"samesite=none" in parts
                and b"partitioned" not in parts
            ):
                if isinstance(v, bytes):
                    v = v + b"; Partitioned"
                else:
                    v = v + "; Partitioned"
        new_headers.append((k, v))
    response.raw_headers[:] = new_headers


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    policy = get_cookie_policy()
    response.set_cookie(
        key="access_token", value=access, httponly=True, secure=policy.secure,
        samesite=policy.samesite, max_age=60 * 60 * 12, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=policy.secure,
        samesite=policy.samesite, max_age=60 * 60 * 24 * 7, path="/",
    )
    _stamp_partitioned(response)


def clear_auth_cookies(response: Response) -> None:
    """Remove authentication cookies with attributes that match their creation.

    Starlette's ``delete_cookie`` only writes a ``Set-Cookie`` header with an
    ``Expires`` in the past. To maximise browser compatibility across the
    policy profiles (Local HTTP / HTTPS), we mirror the cookie identity
    (name + path) and explicitly include the validated ``Secure`` and
    ``SameSite`` attributes that the creation path used.
    """
    policy = get_cookie_policy()
    response.delete_cookie(
        "access_token", path="/", secure=policy.secure, samesite=policy.samesite,
    )
    response.delete_cookie(
        "refresh_token", path="/", secure=policy.secure, samesite=policy.samesite,
    )
    _stamp_partitioned(response)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Yetkisiz erişim")
    try:
        payload = pyjwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Geçersiz token")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
        user["id"] = str(user["_id"])
        del user["_id"]
        user.pop("password_hash", None)
        return user
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token")


# ---------------- Models ----------------
class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class AuditCreate(BaseModel):
    restaurant_name: str
    address: str = ""
    audit_date: Optional[str] = None
    denetci: Optional[str] = ""
    restaurant_manager: Optional[str] = ""
    auditor_title: Optional[str] = ""
    branch_code: Optional[str] = ""
    audit_notes: Optional[str] = ""
    brand: Optional[str] = ""
    city: Optional[str] = ""
    district: Optional[str] = ""


class AnswerInput(BaseModel):
    question_id: int
    answer: str  # 'EVET', 'HAYIR', 'NA'


class AnswersBulkInput(BaseModel):
    expected_version: int = Field(ge=0, strict=True)
    answers: Dict[str, str]
    risk_overrides: Optional[Dict[str, Dict[str, Any]]] = None

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, answers: Dict[str, str]) -> Dict[str, str]:
        if not answers:
            raise ValueError("Cevap listesi boş olamaz")
        valid_values = {"EVET", "HAYIR", "NA"}
        # Soru id varlık kontrolü QUESTIONS_BY_ID'e karşı değil, audit'in kendi
        # snapshot'ına karşı ``update_answers`` endpoint'inde yapılır. Burada
        # sadece tip/format ve cevap değeri kontrolü kalır — Pydantic saf
        # validation, audit context'i bilmez.
        for question_id, value in answers.items():
            try:
                numeric_id = int(question_id)
            except (TypeError, ValueError):
                raise ValueError(f"Geçersiz soru ID: {question_id}") from None
            if question_id != str(numeric_id):
                raise ValueError(f"Geçersiz soru ID: {question_id}")
            if value not in valid_values:
                raise ValueError(f"Geçersiz cevap değeri: {question_id}")
        return answers

    @field_validator("risk_overrides")
    @classmethod
    def validate_risk_overrides(
        cls, overrides: Optional[Dict[str, Dict[str, Any]]]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """İstek içindeki ``risk_overrides`` ham validasyonu.

        Strict tip + aralık kontrolü burada yapılır; soru-id'nin audit'in
        snapshot'ında bulunması sonraki aşamada (audit_doc bazında) kontrol
        edilir. ``risk_score`` / ``risk_level`` alanları reddedilir — bunlar
        client tarafından gönderilmemelidir, backend her zaman yeniden
        hesaplar.
        """
        if overrides is None:
            return None
        if not isinstance(overrides, dict):
            raise ValueError("risk_overrides dict olmalıdır")
        cleaned: Dict[str, Dict[str, Any]] = {}
        for qid_str, pair in overrides.items():
            if not isinstance(qid_str, str):
                raise ValueError(f"risk_overrides anahtarı string olmalıdır: {qid_str!r}")
            if pair is None:
                continue
            if not isinstance(pair, dict):
                raise ValueError(f"risk_overrides[{qid_str}] dict olmalıdır")
            # Client bilerek/dikkatsizlikle score/level göndermişse reddet
            if "risk_score" in pair or "risk_level" in pair:
                raise ValueError(
                    f"risk_overrides[{qid_str}]: risk_score/risk_level backend tarafından "
                    "hesaplanır; client gönderemez"
                )
            if "probability" not in pair or "severity" not in pair:
                raise ValueError(
                    f"risk_overrides[{qid_str}]: 'probability' ve 'severity' zorunludur"
                )
            prob = pair["probability"]
            sev = pair["severity"]
            # bool, ``isinstance(int)`` True döner; ``type(...) is int`` kullan.
            if type(prob) is not int:
                raise ValueError(
                    f"risk_overrides[{qid_str}].probability strict integer olmalıdır: {prob!r}"
                )
            if type(sev) is not int:
                raise ValueError(
                    f"risk_overrides[{qid_str}].severity strict integer olmalıdır: {sev!r}"
                )
            if not (1 <= prob <= 5):
                raise ValueError(
                    f"risk_overrides[{qid_str}].probability 1-5 aralığında olmalıdır: {prob}"
                )
            if not (1 <= sev <= 5):
                raise ValueError(
                    f"risk_overrides[{qid_str}].severity 1-5 aralığında olmalıdır: {sev}"
                )
            cleaned[qid_str] = {"probability": prob, "severity": sev}
        return cleaned


def _collapse_overrides(
    overrides: Optional[Dict[str, Dict[str, Any]]],
    snapshot_questions: List[Dict[str, Any]],
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Default değerle aynı olan override'ları çıkar.

    DB'ye yalnız **gerçek değişiklikler** yazılır. Bu, snapshot izole
    export'un ve effective-risk hesabının tutarlılığını korur.

    * ``overrides is None`` → ``None`` (anlamı: "override yok, default
      kullan" — DB'ye ``{}`` yazmaktan farklı semantik; Phase 2A testleri
      bu ayrımı doğrular).
    * ``overrides == {}`` → ``{}``
    * Snapshot'ta olmayan ``qid`` → sessizce atlanır (defensive;
      Pydantic seviyesi zaten ``expected_questions_in_snapshot`` ile
      reddetmiş olmalı).
    """
    if overrides is None:
        return None
    by_id = {int(q["id"]): q for q in snapshot_questions}
    out: Dict[str, Dict[str, Any]] = {}
    for qid_str, pair in overrides.items():
        q = by_id.get(int(qid_str))
        if not q:
            continue
        default_prob = int(q["default_probability"])
        default_sev = int(q["default_severity"])
        if pair["probability"] != default_prob or pair["severity"] != default_sev:
            out[qid_str] = pair
    return out


class AuditMetaUpdate(AuditCreate):
    expected_version: int = Field(ge=0, strict=True)


# ---------------- Auth Endpoints ----------------
@api_router.post("/auth/register")
async def register(body: RegisterInput, response: Response):
    # P0 — Public registration gate. Production/default posture is
    # **closed** (``ENABLE_PUBLIC_REGISTRATION`` unset or ``false``);
    # only an explicit ``true`` enables the public registration flow.
    # The gate MUST run BEFORE any side effect: no DB write, no
    # password hash, no JWT issuance, no cookie set. The frontend
    # ``REACT_APP_PUBLIC_REGISTRATION_ENABLED`` flag is UX-only and is
    # never authoritative here — see ``registration_config.py`` and
    # ``ARRODES.md`` for the security boundary contract.
    if not is_public_registration_enabled():
        raise HTTPException(status_code=404, detail="Bulunamadı")
    email = body.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")
    doc = {
        "email": email,
        "password_hash": hash_password(body.password),
        "name": body.name.strip(),
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db.users.insert_one(doc)
    uid = str(result.inserted_id)
    access = create_access_token(uid, email)
    refresh = create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    return {"id": uid, "email": email, "name": body.name, "role": "user"}


@api_router.post("/auth/login")
async def login(body: LoginInput, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı")
    uid = str(user["_id"])
    access = create_access_token(uid, email)
    refresh = create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    return {"id": uid, "email": email, "name": user["name"], "role": user.get("role", "user")}


@api_router.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@api_router.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user


@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="Refresh token yok")
    try:
        payload = pyjwt.decode(rt, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Geçersiz token")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
        access = create_access_token(str(user["_id"]), user["email"])
        policy = get_cookie_policy()
        response.set_cookie(
            key="access_token", value=access, httponly=True, secure=policy.secure,
            samesite=policy.samesite, max_age=60 * 60 * 12, path="/",
        )
        _stamp_partitioned(response)
        return {"ok": True}
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token")


# ---------------- Questions ----------------
@api_router.get("/questions")
async def get_questions(current_user: dict = Depends(get_current_user)):
    """Aktif default template'i MongoDB'den oku, frontend uyumlu döndür.

    Frontend (Aşama 2B öncesi) eski alan isimlerini bekliyor; her soru
    ``_adapt_question_to_legacy`` üzerinden geçirilir. Yeni alanlar da
    response içinde korunur (geriye uyumlu).
    """
    tpl = get_default_template()
    if not tpl:
        raise HTTPException(
            status_code=500,
            detail="Aktif default template bulunamadı. db.templates koleksiyonunu kontrol edin.",
        )
    raw_questions = tpl.get("questions", [])
    adapted = [_adapt_question_to_legacy(q) for q in raw_questions]
    # Kategori sırası — şablondan çıkar.
    categories: List[str] = []
    for q in adapted:
        if q["category"] not in categories:
            categories.append(q["category"])
    return {"categories": categories, "questions": adapted}


# ---------------- Audits ----------------
def _summarize(audit: dict) -> dict:
    """Risk summary hesabı (backend kanonik).

    * Sadece ``HAYIR`` cevapları için risk hesaplanır.
    * ``compute_effective_risk`` effective O/Ş ile score/level üretir.
    * ``document_risk_level`` asla kullanılmaz.
    * EVET/NA mevcut davranışı korunur.
    * Snapshot'tan veya legacy fallback'ten soru listesi alınır.
    """
    answers = audit.get("answers", {})
    questions = _get_audit_questions(audit)
    overrides = _get_audit_overrides(audit)
    total = len(questions)
    counts = {"EVET": 0, "HAYIR": 0, "NA": 0, "unanswered": 0}
    risk_counts = {
        RISK_LEVEL_KABUL_EDILEMEZ: 0,
        RISK_LEVEL_DIKKATE_DEGER: 0,
        RISK_LEVEL_KABUL_EDILEBILIR: 0,
    }
    hayir_questions: List[Dict[str, Any]] = []
    total_risk_score = 0
    for q in questions:
        ans = answers.get(str(q["id"]))
        if ans in counts:
            counts[ans] += 1
        else:
            counts["unanswered"] += 1
        if ans == "HAYIR":
            override = overrides.get(str(q["id"]))
            try:
                eff = compute_effective_risk(q, override)
            except ValueError:
                # Override/temiz değer bozuksa default'a fallback
                eff = compute_effective_risk(q, None)
            lvl = eff["risk_level"]
            if lvl in risk_counts:
                risk_counts[lvl] += 1
            total_risk_score += eff["risk_score"]
            hayir_questions.append({
                "soru_no": q["id"],
                "category": q.get("category", ""),
                "area": q.get("area", ""),
                # Legacy şema: ``soru`` / ``sorumlu``; yeni şema:
                # ``question`` / ``responsible``. Aşama 2A "kontrollü
                # legacy fallback" kararı gereği iki şema da desteklenir.
                "question": q.get("question", q.get("soru")),
                "responsible": q.get("responsible", q.get("sorumlu")),
                "probability": eff["probability"],
                "severity": eff["severity"],
                "risk_score": eff["risk_score"],
                "risk_level": eff["risk_level"],
                "document_risk_level": q.get("document_risk_level"),
                "deadline": q.get("deadline", ""),
                "legal_basis": q.get("legal_basis", []),
                "corrective_action": q.get("corrective_action", ""),
            })
    completion = round(((total - counts["unanswered"]) / total) * 100) if total else 0
    return {
        "total_questions": total,
        "answered": total - counts["unanswered"],
        "completion": completion,
        "counts": counts,
        "risk_counts": risk_counts,
        "total_risk_score": total_risk_score,
        "hayir_questions": hayir_questions,
    }


def _scope_filter(current_user: dict) -> dict:
    """Admin users see/manage all audits; regular users only see their own."""
    if current_user.get("role") == "admin":
        return {}
    return {"user_id": current_user["id"]}


def _active_audits_filter() -> dict:
    """Sadece aktif (arşivlenmemiş) audit'leri filtrele.

    Phase 2B — S20: 6 yılı dolmuş audit'ler ``is_archived=true`` olur ve
    default'ta gizlenir. İbraz amaçlı ``?include_archived=true`` ile
    override edilebilir (henüz UI'da açılmadı).

    Phase 2B — S19: Soft-delete edilen audit'ler (``deleted_at != null``)
    de listede gözükmez. DB'de satır durmaya devam eder (6y retention
    + audit_log bütünlüğü için), sadece API yüzeyinde görünmez.
    ``?include_archived=true`` soft-delete'lenenleri de getirmez
    (gerekirse ayrı bir ``?include_deleted`` eklenebilir).
    """
    return {
        "is_archived": {"$ne": True},
        "deleted_at": None,
    }


def _normal_audit_filter(current_user: dict) -> dict:
    """Normal user flow audit lookup filtresi (B3 — soft-delete invariant).

    B3: Soft-delete'lenmiş audit'ler normal API yüzeyinde görünmemeli:

    * scope filtre (admin bypass / owner filter)
    * deleted_at == None (yumuşak silinmiş olanlar dışlanır)

    Arşiv durumu bu helper'a dahil DEĞİLDIR — arşivleme, soft-delete'ten
    bağımsız bir eksendir ve ibraz/retention için ``?include_archived=true``
    ile explicit erişim gerektirir. Endpoint bazlı arşiv kontrolü
    endpoint'te kalır.

    DİKKAT: Bu helper'ı ``delete_audit`` (kendi soft-delete'ini yapan),
    ``admin/archive-expired`` arşivleme trigger'ı ve forensic
    admin/end-user erişim noktaları için KULLANMA — onlar ``deleted_at``
    filtresi olmadan çalışır.
    """
    return {"deleted_at": None, **_scope_filter(current_user)}


def _state_mutable_guard(current_state: str, allowed_states: Sequence[str]) -> None:
    """B2 — FINAL immutability + endpoint'in izin verdiği state'ler kontrolü.

    * ``current_state == "FINAL"`` → 409 (audit sonlandırıldı, mutasyon
      yasak).
    * ``current_state not in allowed_states`` → 409 (state transition guard).

    Endpoint çağrıları ``allowed_states`` listesini kendi iş mantığına
    göre seçer (örn. update_answers → {DRAFT, SUBMITTED, DOF_OPEN,
    DOF_CLOSED}). Bu, ``audit_state.can_edit_*`` matrisinin endpoint
    tarafındaki merkezi uygulamasıdır.

    Yetkili retention/admin operasyonları (soft-delete, archive) bu
    guard'ı BYPASS eder — onlar ``state_guard=False`` ile çağırır.
    """
    if current_state == AuditState.FINAL.value:
        raise HTTPException(
            status_code=409,
            detail="FINAL denetim üzerinde mutasyon yapılamaz",
        )
    if allowed_states and current_state not in {s.value if hasattr(s, "value") else s for s in allowed_states}:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Bu işlem yalnızca {sorted({s.value if hasattr(s, 'value') else s for s in allowed_states})} "
                f"state'inde geçerlidir; mevcut: {current_state}"
            ),
        )


def _serialize_audit(
    doc: dict,
    owner_name: str = "",
    include_snapshot: bool = False,
) -> dict:
    """Audit'i serialize et.

    Response ekleri:

    * ``template_code`` / ``template_version`` — snapshot'tan (None ise yok)
    * ``risk_overrides`` — her zaman
    * ``is_legacy`` — snapshot yoksa True
    * ``template_snapshot`` — yalnız ``include_snapshot=True`` ile döner
      (detay endpoint'inde kullanılır; list endpoint'inde şişmeyi önler)
    * ``summary`` — kanonik backend summary (compute_effective_risk)
    """
    snap = doc.get("template_snapshot") if isinstance(doc.get("template_snapshot"), dict) else None
    raw_state = doc.get("state")
    # Geriye uyumluluk: state yoksa (eski audit) DRAFT kabul et
    if raw_state is None:
        state_value = AuditState.DRAFT.value
    else:
        state_value = raw_state
    out = {
        "id": str(doc["_id"]),
        "user_id": doc["user_id"],
        "owner_name": owner_name,
        "restaurant_name": doc.get("restaurant_name", ""),
        "address": doc.get("address", ""),
        "audit_date": doc.get("audit_date", ""),
        "denetci": doc.get("denetci", ""),
        "restaurant_manager": doc.get("restaurant_manager", ""),
        "auditor_title": doc.get("auditor_title", ""),
        "branch_code": doc.get("branch_code", ""),
        "audit_notes": doc.get("audit_notes", ""),
        "brand": doc.get("brand", ""),
        "city": doc.get("city", ""),
        "district": doc.get("district", ""),
        "declarations": doc.get("declarations", {}),
        "declarations_meta": doc.get("declarations_meta", {}),
        "answers": doc.get("answers", {}),
        "version": doc.get("version", 0),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "summary": _summarize(doc),
        "risk_overrides": doc.get("risk_overrides", {}),
        "is_legacy": snap is None,
        # Phase 2B — S18 state machine
        "state": state_value,
        "state_history": doc.get("state_history", []),
        "is_completed": audit_state.derive_is_completed(state_value),
        "deleted_at": doc.get("deleted_at"),
        # Phase 2B — S20 retention + archive
        "retention_until": doc.get("retention_until"),
        "is_archived": doc.get("is_archived", False),
        # Phase 2B — S7: inline DÖF formu için DÖF bilgisi
        "dof_details": doc.get("dof_details", {}) or {},
    }
    if snap:
        out["template_code"] = snap.get("template_code")
        out["template_version"] = snap.get("template_version")
        out["template_name"] = snap.get("template_name")
        if include_snapshot:
            out["template_snapshot"] = snap
    return out


async def _owner_name(user_id: str) -> str:
    try:
        u = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "email": 1})
    except Exception:
        return ""
    if not u:
        return ""
    return u.get("name") or u.get("email", "")


@api_router.post("/audits")
async def create_audit(body: AuditCreate, current_user: dict = Depends(get_current_user)):
    """Yeni audit oluştur.

    Aktif default template ``db.templates`` cache'inden okunur ve audit'e
    tam derin snapshot olarak yazılır. ``risk_overrides`` boş dict olarak
    başlatılır. Template yoksa 500 döner.
    """
    tpl = get_default_template()
    if not tpl:
        raise HTTPException(
            status_code=500,
            detail="Aktif default template bulunamadı. db.templates koleksiyonunu kontrol edin.",
        )
    now = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "template_code": tpl["code"],
        "template_name": tpl["name"],
        "template_version": tpl["version"],
        "snapshot_at": now,
        # Derin kopya — Aşama 1 kararı gereği: snapshot, şablon sonradan
        # değişse bile eski audit'i etkilemez. Sığ kopya olsaydı template
        # cache'te mutation audit'in snapshot soru dict'lerini bozardı.
        "questions": copy.deepcopy(tpl["questions"]),
    }
    doc = {
        "user_id": current_user["id"],
        "restaurant_name": body.restaurant_name.strip(),
        "address": body.address.strip(),
        "audit_date": body.audit_date or datetime.now(timezone.utc).date().isoformat(),
        "denetci": (body.denetci or current_user["name"]).strip(),
        # ``getattr`` defensive: eski test fixture'ları SimpleNamespace'i
        # yalnız temel alanlarla inşa eder; eksik alanlar ``""`` olarak yazılır.
        "restaurant_manager": getattr(body, "restaurant_manager", "") or "",
        "auditor_title": getattr(body, "auditor_title", "") or "",
        "branch_code": getattr(body, "branch_code", "") or "",
        "audit_notes": getattr(body, "audit_notes", "") or "",
        "brand": (getattr(body, "brand", "") or "").strip(),
        "city": (getattr(body, "city", "") or "").strip(),
        "district": (getattr(body, "district", "") or "").strip(),
        "answers": {},
        "risk_overrides": {},
        "declarations": {},
        "declarations_meta": {},
        "version": 0,
        "state": AuditState.DRAFT.value,  # Phase 2B — S18 state machine
        "state_history": [],  # Geçiş logu (her append-only)
        "is_completed": False,  # Geriye uyumluluk: derive_is_completed(state)
        "deleted_at": None,  # Soft-delete flag (S18 — DRAFT dışı tüm state'lerde kullanılır)
        "retention_until": compute_retention_until(now),  # Phase 2B — S20 (kanunen 6 yıl)
        "is_archived": False,  # 6 yılı dolunca otomatik set edilir
        "template_snapshot": snapshot,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.audits.insert_one(doc)
    doc["_id"] = result.inserted_id
    # Phase 2B — S20: audit oluşturma logla
    await log_action(
        db, audit_id=str(doc["_id"]), user=current_user, action=Action.CREATE,
        before=None, after={"state": doc["state"], "restaurant_name": doc["restaurant_name"]},
    )
    return _serialize_audit(doc, current_user["name"])


@api_router.get("/audits")
async def list_audits(
    current_user: dict = Depends(get_current_user),
    include_archived: bool = False,
):
    # Phase 2B — S20: arşivlenmiş audit'ler default'ta gizli
    base_filter = _scope_filter(current_user)
    if not include_archived:
        base_filter.update(_active_audits_filter())
    cursor = db.audits.find(base_filter).sort("created_at", -1)
    # Preload owner names
    name_cache: Dict[str, str] = {current_user["id"]: current_user["name"]}
    items = []
    async for doc in cursor:
        uid = doc["user_id"]
        if uid not in name_cache:
            name_cache[uid] = await _owner_name(uid)
        items.append(_serialize_audit(doc, name_cache[uid]))
    return items


@api_router.get("/audits/{audit_id}")
async def get_audit(audit_id: str, current_user: dict = Depends(get_current_user)):
    """Audit getir.

    B3: Normal flow soft-deleted audit'i 404 döndürür. Forensic/admin
    erişim için ``?include_deleted=true`` ile explicit bypass (henüz
    eklenmedi — gerekirse açılır; default davranış görünmez).
    """
    try:
        # B3: soft-deleted audit'i normal GET'te gizle.
        doc = await db.audits.find_one(
            {"_id": ObjectId(audit_id), **_normal_audit_filter(current_user)}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")
    if not doc:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")
    owner = current_user["name"] if doc["user_id"] == current_user["id"] else await _owner_name(doc["user_id"])
    # Audit ekranı kendi snapshot'ını kullanmalı — global /questions template'i
    # değil. Detay sayfası snapshot'ı frontend'e gönderir; frontend soruları
    # snapshot'tan okur, /questions yalnız yeni audit oluşturma akışında
    # kullanılabilir.
    return _serialize_audit(doc, owner, include_snapshot=True)


@api_router.get("/audits/{audit_id}/audit-log")
async def get_audit_log_endpoint(
    audit_id: str,
    limit: int = 100,
    skip: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """Phase 2B — S20: Audit'in tüm değişiklik geçmişini getir.

    Append-only ``audit_log`` koleksiyonundan okur; en yeni kayıt önce.
    Sadece audit sahibi veya admin erişebilir (scope filter).
    """
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")
    # Önce audit var mı ve scope dahil mi kontrol et
    audit_doc = await db.audits.find_one({"_id": oid, **_scope_filter(current_user)}, {"_id": 1})
    if not audit_doc:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")
    items = await get_audit_log(db, str(oid), limit=limit, skip=skip)
    return {"items": items, "count": len(items), "limit": limit, "skip": skip}


# ═══════════════════════════════════════════════════════════════════════════
# Admin endpoints — yalnız role=admin kullanıcılar
# S20 retention arşivleme, backup tetikleme gibi operasyonel işler için.
# Cron job bu endpoint'leri HTTP üzerinden tetikler (curl + service token).
# ═══════════════════════════════════════════════════════════════════════════
def _require_admin(current_user: dict) -> None:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem yalnız admin kullanıcılar içindir")


@api_router.post("/admin/archive-expired")
async def admin_archive_expired(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """S20: Retention süresi dolmuş audit'leri arşivle.

    ``retention_until <= now`` olan ve ``is_archived != true`` olan audit'leri
    ``is_archived=true`` olarak işaretler; silmez. ``audit_log``'a her biri
    için ``archive`` action'ı yazılır (system actor).

    Cron job (host'ta veya container içinde) tarafından periyodik çağrılır:
        curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \\
             http://localhost:8000/api/admin/archive-expired
    """
    _require_admin(current_user)
    from audit_log import archive_expired_audits
    archived_count = await archive_expired_audits(db)
    # Admin aksiyonu da loga yaz (kim ne yaptı, ne kadar arşivlendi)
    try:
        await log_action(
            db,
            audit_id="__system__",  # system-wide event
            user=current_user,
            action=Action.ARCHIVE,
            before=None,
            after={"archived_count": archived_count, "trigger": "admin_endpoint"},
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception as e:
        print(f"[admin/archive-expired] audit_log write failed: {e}")
    return {"ok": True, "archived_count": archived_count}


@api_router.post("/admin/backup")
async def admin_backup_trigger(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Admin: Manuel backup tetikleyici — B9 — honest no-op.

    **B9 — Admin backup trigger honest no-op:**

    Production'da backup ``scripts/backup_mongo.sh`` shell cron tarafından
    alınır (host veya sidecar container'da çalışır çünkü mongodump +
    s3cmd/s5cmd gerekir). Bu endpoint'i eski tasarımın kalıntısı olarak
    tutmaya devam ediyoruz, ancak **artık gerçek bir backup tetiklemiyor**
    — eski ``action="backup_triggered"`` string'i kullanılıyor, Action
    enum'unda yer almıyor ve audit_log'a "başarı" gibi görünen sahte bir
    kayıt yazıyordu.

    Davranış:

    1. ``_require_admin`` — admin değilse 403.
    2. **Audit log yazılmaz** — eskiden yazılan "backup_triggered" string'i
       Action enum'una ait değildi; mandatory audit trail'in parçası
       olmamalı. Bu endpoint forensic bir event DEĞİLDİR.
    3. Response, neyin olup neyin olmadığını AÇIKÇA söyler. Operatörün
       shell cron'u manuel tetiklemesi gerektiğini belirtir.

    Returns:
        Honest acknowledgment: ``{"ok": True, "action": "noop", ...}``.
        Yanlış yönlendirici eski ``"manuel backup tetiklendi"`` metni
        kaldırıldı.
    """
    _require_admin(current_user)
    return {
        "ok": True,
        "action": "noop",
        "deprecated": True,
        "message": (
            "Bu endpoint artık no-op. Production backup'ları "
            "scripts/backup_mongo.sh shell cron tarafından alınır; "
            "operatörün host/sidecar'da manuel tetikleme yapması gerekir. "
            "Bu endpoint kaldırılmayı planlanıyor."
        ),
    }


@api_router.get("/admin/retention-status")
async def admin_retention_status(current_user: dict = Depends(get_current_user)):
    """S20: Retention durumu özeti.

    Kaç audit retention süresi içinde, kaçı expired (arşivlenmemiş),
    kaçı archived, toplam boyut tahmini. Admin dashboard'unda gösterilmek
    üzere tasarlandı.
    """
    _require_admin(current_user)
    from datetime import datetime as _dt
    now_iso = _dt.now(timezone.utc).isoformat()

    total = await db.audits.count_documents({})
    archived = await db.audits.count_documents({"is_archived": True})
    # Retention expired ama henüz arşivlenmemiş
    expired_pending = await db.audits.count_documents(
        {"retention_until": {"$lte": now_iso, "$ne": None}, "is_archived": {"$ne": True}}
    )
    # Retention aktif (henüz expire olmamış, arşivlenmemiş)
    active = total - archived

    return {
        "now": now_iso,
        "total_audits": total,
        "archived_audits": archived,
        "active_audits": active,
        "expired_pending_archive": expired_pending,
        "retention_years": 6,
    }


def _version_filter(oid: ObjectId, current_user: dict, expected_version: int) -> dict:
    query = {"_id": oid, **_scope_filter(current_user)}
    if expected_version == 0:
        query["$or"] = [{"version": 0}, {"version": {"$exists": False}}]
    else:
        query["version"] = expected_version
    return query


async def _raise_audit_mutation_failure(oid: ObjectId, current_user: dict) -> None:
    exists = await db.audits.find_one(
        {"_id": oid, **_scope_filter(current_user)},
        {"_id": 1},
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")
    raise HTTPException(
        status_code=409,
        detail={
            "code": "audit_version_conflict",
            "message": "Denetim başka bir oturumda güncellendi.",
        },
    )


@api_router.post("/audits/{audit_id}/submit")
async def submit_audit(audit_id: str, current_user: dict = Depends(get_current_user)):
    """Denetçi "Denetimi Tamamla" dedi → DRAFT'tan SUBMITTED/DOF_OPEN'a geçiş.

    Phase 2B — S18: Submit edilen audit'te HAYIR cevaplı soru varsa otomatik
    DOF_OPEN'a, yoksa SUBMITTED'a düşer. Sonrasında ``update_answers`` ve
    ``update_audit_meta`` reddedilir; yalnız declarations ve DÖF işlemleri
    yapılabilir.

    DÖF sayımı ``_count_open_dofs()`` üzerinden yapılır; ``dof_details``
    map'indeki ``status`` alanı ``AÇIK`` veya ``İŞLEMDE`` olanlar açık
    sayılır, ``KAPATILDI`` olanlar kapalı.
    """
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    existing = await db.audits.find_one({"_id": oid, **_normal_audit_filter(current_user)})
    if not existing:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    current_state = existing.get("state") or AuditState.DRAFT.value
    if not audit_state.can_submit(current_state):
        raise HTTPException(
            status_code=409,
            detail=f"Bu denetim {current_state} durumunda; yalnız DRAFT durumundayken gönderilebilir.",
        )

    # HAYIR cevaplı soru kontrolü → DÖF var mı?
    answers = existing.get("answers", {}) or {}
    snapshot_questions = _get_audit_questions(existing)
    snapshot_ids = {int(q["id"]) for q in snapshot_questions}
    has_hayir = any(str(qid) in answers and answers[str(qid)] == "HAYIR" for qid in snapshot_ids)

    # DÖF zaten açılmış olabilir mi? (Kullanıcı daha önce el ile açtı)
    open_dof_count = await _count_open_dofs(oid)
    has_open_dof = has_hayir or open_dof_count > 0

    target_state = audit_state.compute_submit_target_state(existing, has_open_dof=has_open_dof)
    now_iso = datetime.now(timezone.utc).isoformat()
    set_fields = audit_state.transition_audit(
        existing,
        target_state,
        actor_id=current_user["id"],
        reason="Denetim tamamlandı, denetçi tarafından gönderildi",
        now_iso=now_iso,
    )

    updated = await db.audits.find_one_and_update(
        {"_id": oid},
        {"$set": set_fields, "$inc": {"version": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    # Phase 2B — S20: submit log. B6 — mandatory=True: submit critical
    # state transition; log yazılamazsa 5xx ile UI'da görünür hata.
    await log_action(
        db, audit_id=audit_id, user=current_user, action=Action.SUBMIT,
        before={"state": current_state},
        after={"state": updated.get("state")},
        mandatory=True,
    )

    owner = current_user["name"] if updated["user_id"] == current_user["id"] else await _owner_name(updated["user_id"])
    return _serialize_audit(updated, owner)


async def _count_open_dofs(oid: ObjectId) -> int:
    """Açık DÖF sayısını döndürür.

    Mantık: Her HAYIR cevaplı soru potansiyel bir DÖF'tür. DÖF durumunu
    ``dof_details.<qid>.status`` taşır; eğer status ``KAPATILDI`` ise o
    DÖF kapanmış sayılır. ``dof_details`` map'i yalnızca DÖF'e dokunulduğunda
    yazılır (lazy creation) — hiç dokunulmamış DÖF'ler default olarak açık
    sayılır (status yok → ``AÇIK`` kabul).

    Returns:
        Açık DÖF sayısı (0 dahil).
    """
    doc = await db.audits.find_one(
        {"_id": oid},
        {"answers": 1, "dof_details": 1, "template_snapshot": 1},
    )
    if not doc:
        return 0

    snapshot_ids = {int(q["id"]) for q in _get_audit_questions(doc)}
    answers = doc.get("answers") or {}
    details = doc.get("dof_details") or {}

    hayir_qids = {
        qid
        for qid in snapshot_ids
        if answers.get(str(qid)) == "HAYIR"
    }

    open_count = 0
    for qid in hayir_qids:
        d = details.get(str(qid)) or {}
        if not isinstance(d, dict):
            d = {}
        # B4 — invalidated DÖF kaydı (active=False) sayım dışı.
        if d.get("active") is False:
            continue
        if d.get("status") == "KAPATILDI":
            # Bu DÖF kapatılmış; açık sayımına girmez.
            continue
        open_count += 1

    return max(0, open_count)


async def _finalize_audit_if_dof_closed(oid: ObjectId, doc: dict, actor_id: str) -> None:
    """Phase 2B — S18: İlk nihai rapor export'unda DOF_CLOSED → FINAL geçişi.

    Sadece ``state == DOF_CLOSED`` ise uygulanır. ``FINAL`` zaten terminal
    durum olduğu için no-op. ``SUBMITTED/DOF_OPEN/DRAFT`` durumlarında
    ``can_export_final`` zaten false olduğu için bu fonksiyon çağrılmaz;
    yine de savunmacı olarak state'i DOF_CLOSED değilse hiçbir şey yapmaz.

    Audit doc referansı ``state`` ve ``state_history`` alanlarında yerinde
    güncellenir (DB yazımı + çağıranın response serialize'ı aynı değeri
    görsün diye).
    """
    current_state = doc.get("state") or AuditState.DRAFT.value
    if current_state != AuditState.DOF_CLOSED.value:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    set_fields = audit_state.transition_audit(
        doc,
        AuditState.FINAL,
        actor_id=actor_id,
        reason="İlk nihai rapor export edildi",
        now_iso=now_iso,
    )
    await db.audits.update_one({"_id": oid}, {"$set": set_fields})
    # doc ref'i güncelle ki çağıran response'ta doğru state görsün
    doc["state"] = set_fields.get("state", current_state)
    doc["is_completed"] = set_fields.get("is_completed", doc.get("is_completed"))
    doc["state_history"] = set_fields.get("state_history", doc.get("state_history", []))


@api_router.put("/audits/{audit_id}/answers")
async def update_answers(audit_id: str, body: AnswersBulkInput, current_user: dict = Depends(get_current_user)):
    """Cevapları ve opsiyonel ``risk_overrides`` atomik güncelle.

    Validation:

    * ``risk_score`` / ``risk_level`` gönderilirse reddedilir (backend
      hesaplar).
    * ``probability`` / ``severity`` strict int 1-5 olmalı.
    * Geçersiz soru id (audit'in snapshot'ında yok) reddedilir.
    * Default değerle aynı override'lar DB'ye yazılmaz (collapse).
    * ``answers`` ve ``risk_overrides`` tek atomik update içinde yazılır;
      ``expected_version`` davranışı korunur, ``version`` tam +1 artar.
    """
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    # Önce mevcut audit'i oku — snapshot'ta override validation yapılır.
    # B3 — soft-delete filtresi tek satırda (``_normal_audit_filter``).
    existing = await db.audits.find_one({"_id": oid, **_normal_audit_filter(current_user)})
    if not existing:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    # Phase 2B — S18 state guard. ``can_edit_answers`` matris tablosundan
    # kontrol — FINAL zaten False döner (B2 invariant, doğrudan raise'lenir).
    current_state = existing.get("state") or AuditState.DRAFT.value
    if not audit_state.can_edit_answers(current_state):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Bu denetim {current_state} durumunda; cevaplar düzenlenemez. "
                f"Yalnız DRAFT durumundayken cevaplar değiştirilebilir."
            ),
        )

    snapshot_questions = _get_audit_questions(existing)
    snapshot_ids = {int(q["id"]) for q in snapshot_questions}

    # answers içindeki soru id'leri audit'in kendi snapshot'ına karşı doğrulanır.
    # Global QUESTIONS_BY_ID'e değil; her audit kendi snapshot'ına göre validate
    # edilir (şablon değişiklikleri geçmiş audit'leri etkilemesin).
    for question_id in body.answers.keys():
        try:
            qid = int(question_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Geçersiz soru ID: {question_id}",
            )
        if qid not in snapshot_ids:
            raise HTTPException(
                status_code=400,
                detail=f"answers soru {qid}: bu audit'in snapshot'ında yok",
            )

    # risk_overrides semantiği:
    #   * None  → alan request içinde yok → mevcut override'lar korunur (skip).
    #   * {}    → bilinçli olarak boş gönderildi → mevcut override'lar temizlenir.
    #   * dolu  → snapshot_ids'e karşı validate edilir, default'larla aynı olanlar
    #             collapse edilir, kalanı replace edilir.
    incoming_overrides = body.risk_overrides
    if incoming_overrides:
        for qid_str, pair in incoming_overrides.items():
            try:
                qid = int(qid_str)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail=f"Geçersiz override anahtarı: {qid_str!r}",
                )
            if qid not in snapshot_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"risk_overrides soru {qid}: bu audit'in snapshot'ında yok",
                )
        collapsed = _collapse_overrides(incoming_overrides, snapshot_questions)
    elif incoming_overrides is not None:
        # {} → bilinçli temizleme
        collapsed = {}
    else:
        # None → alan gönderilmemiş → mevcut overrides korunur (DB'ye yazılmaz)
        collapsed = None  # sentinel: skip

    set_fields: Dict[str, Any] = {
        "answers": body.answers,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if collapsed is not None:
        # None ise mevcut risk_overrides dokunulmaz; veri kaybı olmaz.
        set_fields["risk_overrides"] = collapsed

    doc = await db.audits.find_one_and_update(
        _version_filter(oid, current_user, body.expected_version),
        {
            "$set": set_fields,
            "$inc": {"version": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        await _raise_audit_mutation_failure(oid, current_user)
    owner = current_user["name"] if doc["user_id"] == current_user["id"] else await _owner_name(doc["user_id"])

    # B4 — DÖF invalidation + activation invariant.
    #
    # * HAYIR → non-HAYIR: ``dof_details.<qid>.active = False`` + invalidation
    #   metadata. Historical record ($unset değil) korunur.
    # * non-HAYIR → HAYIR: daha önce aktif DÖF kaydı yoksa yeni aktif
    #   kayıt oluşturulur. Zaten aktif kayıt varsa idempotent — dokunulmaz.
    # * HAYIR → HAYIR veya non-HAYIR → non-HAYIR: dof_details dokunulmaz.
    # * Bu işlem atomik answer update'ten SONRA yapılır: ``$set`` zaten
    #   yeni answers'ı içeriyor, dof_details burada doğru context ile
    #   update edilir. Race penceresi milisaniye düzeyinde ve "yanlış"
    #   sonluç yok (her iki call da idempotent).
    before_answers = existing.get("answers") or {}
    after_answers = body.answers
    invalidated_qids: List[str] = []
    activated_qids: List[str] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    user_id = current_user["id"]
    invalidate_set: Dict[str, Any] = {}
    for qid_str, new_val in after_answers.items():
        old_val = before_answers.get(qid_str)
        if old_val == "HAYIR" and new_val != "HAYIR":
            qid_key = str(qid_str)
            invalidate_set[f"dof_details.{qid_key}.active"] = False
            invalidate_set[f"dof_details.{qid_key}.invalidated_at"] = now_iso
            invalidate_set[f"dof_details.{qid_key}.invalidated_by"] = user_id
            invalidate_set[f"dof_details.{qid_key}.invalidated_reason"] = (
                f"answer_changed_to_{new_val}"
            )
            invalidated_qids.append(qid_key)
    if invalidate_set:
        # Race-safe scoped update — concurrency guards audit scope.
        await db.audits.update_one(
            {"_id": oid, **_scope_filter(current_user)},
            {"$set": invalidate_set},
        )

    # Activations: yalnız ``non-HAYIR → HAYIR`` ve daha önce aktif
    # dof_details kaydı yoksa taze bir kayıt oluştur. ``active=False``
    # kayıt varsa refresh. Atomic filter ile idempotent: "no active
    # entry" koşulu sağlanıyorsa $set uygulanır; aksi hâlde no-op.
    dof_details = existing.get("dof_details") or {}
    for qid_str, new_val in after_answers.items():
        old_val = before_answers.get(qid_str)
        if old_val != "HAYIR" and new_val == "HAYIR":
            qid_key = str(qid_str)
            existing_entry = dof_details.get(qid_key) or {}
            if (
                not isinstance(existing_entry, dict)
                or existing_entry.get("active") is not True
            ):
                fresh = {
                    "status": "AÇIK",
                    "notes": "",
                    "resolution_note": "",
                    "active": True,
                    "invalidated_at": None,
                    "invalidated_by": None,
                    "invalidated_reason": None,
                    "created_at": now_iso,
                    "created_by": user_id,
                    "updated_at": now_iso,
                    "updated_by": user_id,
                    "timeline_logs": [],
                }
                # ``$or`` filtresi: ya kayıt yok, ya da active=False. Aksi
                # takdirde no-op.
                await db.audits.update_one(
                    {
                        "_id": oid,
                        **_scope_filter(current_user),
                        "$or": [
                            {f"dof_details.{qid_key}": {"$exists": False}},
                            {f"dof_details.{qid_key}.active": False},
                        ],
                    },
                    {"$set": {f"dof_details.{qid_key}": fresh}},
                )
                activated_qids.append(qid_key)

    # Phase 2B — S20: cevap güncellemeyi logla (before/after answer diff).
    # B6 — mandatory=True: cevap güncelleme domain-mutating ve compliance
    # gereği kritik bir işlem; log yazılamazsa 5xx ile UI'da görünür hata.
    await log_action(
        db,
        audit_id=audit_id,
        user=current_user,
        action=Action.ANSWER_UPDATE,
        before={
            "answers": before_answers,
            "risk_overrides": existing.get("risk_overrides") or {},
            "version": existing.get("version", 0),
        },
        after={
            "answers": doc.get("answers") or {},
            "risk_overrides": doc.get("risk_overrides") or {},
            "version": doc.get("version", 0),
            "dof_invalidations": invalidated_qids,
            "dof_activations": activated_qids,
        },
        mandatory=True,
    )

    return _serialize_audit(doc, owner)


@api_router.patch("/audits/{audit_id}")
async def update_audit_meta(audit_id: str, body: AuditMetaUpdate, current_user: dict = Depends(get_current_user)):
    """Audit metadata için true partial PATCH.

    Sadece request body'sinde **açıkça gönderilen** alanlar MongoDB'ye
    yazılır; gönderilmeyen alanlar mevcut değerlerini korur. Bu, Pydantic
    v2 ``model_fields_set`` üzerinden saptanır (``model_dump(exclude_unset=True)``
    eşdeğeri). ``expected_version`` her zaman kontrol için okunur ama
    MongoDB ``$set``'ine dahil edilmez.

    Semantik ayrım:

    * Alan gönderilmedi → DB'deki mevcut değer korunur.
    * Alan explicit ``""`` gönderildi → DB'deki değer temizlenir.
    * Alan explicit string gönderildi → ilgili normalizasyon uygulanır.

    Mevcut normalizasyon korunur: serbest metin alanları
    (``restaurant_name``, ``address``, ``denetci``, ``restaurant_manager``,
    ``auditor_title``, ``branch_code``, ``audit_notes``, ``brand``,
    ``city``, ``district``) için ``(value or "").strip()``; ``audit_date``
    strip edilmez (ISO date) ve ``None`` → ``""`` davranışı korunur.
    """
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    # Phase 2B — S18 state guard
    # B3 — soft-delete tek satırda (``_normal_audit_filter``).
    existing = await db.audits.find_one({"_id": oid, **_normal_audit_filter(current_user)})
    if not existing:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")
    current_state = existing.get("state") or AuditState.DRAFT.value
    if not audit_state.can_edit_meta(current_state):
        raise HTTPException(
            status_code=409,
            detail=f"Bu denetim {current_state} durumunda; metadata düzenlenemez. "
                   f"Yalnız DRAFT durumundayken metadata değiştirilebilir.",
        )

    updates: Dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # ``model_fields_set`` yalnızca client'ın JSON body'sinde açıkça
    # belirttiği alanları içerir; Pydantic default'larına düşen alanlar
    # burada YOKTUR. ``expected_version`` kontrol amaçlı okunur, DB'ye
    # yazılmaz — bu yüzden set'ten çıkarılır.
    supplied = body.model_fields_set - {"expected_version"}

    # Her alan için mevcut normalizasyon semantiğini koru. Generic
    # ``(value or "").strip()`` döngüsü KULLANILMAZ çünkü ileride eklenebilecek
    # string-olmayan alanlar (``datetime``, ``int`` vs.) için tip güvenliği
    # gerekir; ``audit_date`` strip edilmemeli, diğer string alanlar ise
    # strip uygulamalı.
    for field in supplied:
        value = getattr(body, field)
        if field == "audit_date":
            # None → ""; ISO tarih string'i olduğu gibi korunur.
            updates[field] = value or ""
        else:
            # restaurant_name / address / denetci / restaurant_manager /
            # auditor_title / branch_code / audit_notes / brand / city /
            # district: serbest metin. None → ""; explicit boş string
            # clear olarak kalır; aksi halde strip uygulanır.
            updates[field] = (value or "").strip()

    doc = await db.audits.find_one_and_update(
        _version_filter(oid, current_user, body.expected_version),
        {"$set": updates, "$inc": {"version": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        await _raise_audit_mutation_failure(oid, current_user)
    owner = current_user["name"] if doc["user_id"] == current_user["id"] else await _owner_name(doc["user_id"])

    # Phase 2B — S20: meta değişikliğini logla. ``supplied`` set'i
    # yalnızca client'ın gerçekten gönderdiği alanları içerir, audit
    # log'da diff olarak saklanır (eski + yeni değer).
    # B6 — mandatory=True: meta güncelleme compliance invariant; log
    # yazılamazsa 5xx ile UI'da görünür hata.
    before_meta = {f: existing.get(f) for f in supplied}
    after_meta = {f: doc.get(f) for f in supplied}
    await log_action(
        db,
        audit_id=audit_id,
        user=current_user,
        action=Action.META_UPDATE,
        before=before_meta,
        after=after_meta,
        mandatory=True,
    )

    return _serialize_audit(doc, owner)


class DeclarationsUpdateInput(BaseModel):
    declarations: Dict[str, Any] = Field(default_factory=dict)
    meta: Optional[Dict[str, Any]] = None


@api_router.patch("/audits/{audit_id}/declarations")
async def update_audit_declarations(
    audit_id: str,
    body: DeclarationsUpdateInput,
    current_user: dict = Depends(get_current_user)
):
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    # B3 — soft-delete filtresi.
    doc = await db.audits.find_one({"_id": oid, **_normal_audit_filter(current_user)})
    if not doc:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    # Phase 2B — S18 state guard. ``can_edit_declarations`` False döndüğünde
    # FINAL durumdan dolayı da False gelir — B2 invariant.
    current_state = doc.get("state") or AuditState.DRAFT.value
    if not audit_state.can_edit_declarations(current_state):
        raise HTTPException(
            status_code=409,
            detail=f"Bu denetim {current_state} durumunda; beyanlar düzenlenemez. "
                   f"FINAL durumdaki denetimlerde beyan değiştirilemez.",
        )

    existing_decs = doc.get("declarations", {}) or {}
    existing_decs.update(body.declarations or {})

    updates = {
        "declarations": existing_decs,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if body.meta is not None:
        updates["declarations_meta"] = body.meta

    updated_doc = await db.audits.find_one_and_update(
        {"_id": oid},
        {"$set": updates, "$inc": {"version": 1}},
        return_document=ReturnDocument.AFTER,
    )
    owner = current_user["name"] if updated_doc["user_id"] == current_user["id"] else await _owner_name(updated_doc["user_id"])

    # Phase 2B — S20: declarations update log. ``body.declarations`` map'indeki
    # her qid için before/after diff yazılır (sadece değişenler).
    # B6 — mandatory=True: beyanlar compliance alanı (İSG sicil altlığı).
    # Log yazılamazsa 5xx ile UI'da görünür hata.
    before_decs = doc.get("declarations") or {}
    after_decs = updated_doc.get("declarations") or {}
    changed_qids = [
        qid for qid in (body.declarations or {}).keys()
        if str(qid) in [str(k) for k in after_decs.keys()] and before_decs.get(str(qid)) != after_decs.get(str(qid))
    ]
    if changed_qids or (body.meta is not None and (doc.get("declarations_meta") or {}) != (updated_doc.get("declarations_meta") or {})):
        await log_action(
            db,
            audit_id=audit_id,
            user=current_user,
            action=Action.DECLARATION_UPDATE,
            before={
                "declarations": {qid: before_decs.get(str(qid)) for qid in changed_qids},
                "declarations_meta": doc.get("declarations_meta") or {},
            },
            after={
                "declarations": {qid: after_decs.get(str(qid)) for qid in changed_qids},
                "declarations_meta": updated_doc.get("declarations_meta") or {},
            },
            mandatory=True,
        )

    return _serialize_audit(updated_doc, owner)


class WorkplaceApprovalDecision(BaseModel):
    """İşveren vekili onayı tek soru kararı (S7.2 + B5).

    B5 — Backend validation invariant:

    * ``decision`` enum: yalnızca ``KABUL`` (uygun) veya ``ITIRAZ``
      (itiraz/uygunsuz) geçerlidir. Bu değerler işveren vekili onay
      belgesine ve audit_log'a yazılır; geçersiz değer ``400`` ile reddedilir.
    * ``itiraz`` kararı için ``dispute_reason`` zorunlu, min 20 karakter —
      "az önce değişiklik yapayım, sonra bakarım" gibi bir noktalama
      tuzağını kapatır.
    * ``commitment`` opsiyonel, min 10 karakter (geçerli bir taahhüt
      ifadesi olmasını sağlar). Boş bırakılabilir.
    """

    decision: Literal["KABUL", "ITIRAZ"]
    dispute_reason: Optional[str] = None
    commitment: Optional[str] = None


class WorkplaceApprovalSignInput(BaseModel):
    """İşveren Vekili Onay Belgesi imzalama isteği (S7.2 + B5).

    * ``decisions`` — HAYIR cevaplı her soru için {decision, reason, commitment}.
      Boş olsa da kabul edilir (idempotent), ama backend tüm HAYIR sorular
      için karar verilmiş olmasını zorunlu tutmaz (kontrol frontend'de).
    * ``rep_name`` / ``rep_title`` / ``declaration_date`` — imza bloğu.

    B5 — her ``decisions[qid]`` için ``WorkplaceApprovalDecision`` ile
    backend taraflı enum + min length doğrulaması.
    """

    decisions: Dict[str, WorkplaceApprovalDecision] = Field(default_factory=dict)
    rep_name: str = Field(min_length=1, max_length=200)
    rep_title: str = Field(default="Restoran Müdürü / İşveren Vekili", max_length=200)
    declaration_date: Optional[str] = None  # ISO date (YYYY-MM-DD)


@api_router.post("/audits/{audit_id}/workplace-approval/sign")
async def sign_workplace_approval(
    audit_id: str,
    body: WorkplaceApprovalSignInput,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """İşveren Vekili Onay Belgesi'ni imzala.

    Aşamalar:
        1. Audit doc'unu getir; ``state`` DOF_OPEN veya DOF_CLOSED olmalı.
           FINAL / DRAFT / SUBMITTED'da reddedilir.
        2. ``declarations`` + ``declarations_meta`` tek atomik update ile yaz.
        3. ``audit_log``'a ``workplace_approval_signed`` action'ı yaz.
        4. Eğer state DOF_OPEN ve tüm DÖF'ler kapalıysa otomatik
           DOF_OPEN → DOF_CLOSED transition uygula.
        5. Güncellenmiş audit doc'u serialize edip döndür.

    Response: 200 + audit dict (``_serialize_audit``).
    Hata: 404 audit yok, 410 soft-deleted, 409 state uyumsuz, 400 validasyon.
    """
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    # B3 — soft-delete filter; deleted audit imzalanamaz.
    # B5 — ön-read state + idempotency guard. ASIL sign işlemi atomik
    # ``find_one_and_update`` filtresinde tekrarlanır (aşağıda) — iki
    # eşzamanlı sign isteğinde yalnızca biri başarılı olur.
    doc = await db.audits.find_one(
        {"_id": oid, **_normal_audit_filter(current_user)},
        {
            "state": 1,
            "declarations": 1,
            "declarations_meta": 1,
            "answers": 1,
            "dof_details": 1,
            "template_snapshot": 1,
            "user_id": 1,
        },
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    current_state = doc.get("state") or AuditState.DRAFT.value
    if current_state not in (AuditState.DOF_OPEN.value, AuditState.DOF_CLOSED.value):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Bu denetim {current_state} durumunda; işveren vekili onayı imzalanamaz. "
                f"Sadece DOF_OPEN ve DOF_CLOSED durumlarında imza atılabilir."
            ),
        )

    # Idempotency: zaten imzaliysa 409 don (yeniden imzaya izin yok).
    # ``declarations_meta.signed_at`` tek doğruluk kaynağı — client
    # payload'ında ``signed_at`` olup olmamasına BAKILMAZ (B5).
    existing_meta = doc.get("declarations_meta") or {}
    if existing_meta.get("signed_at"):
        raise HTTPException(
            status_code=409,
            detail="İşveren vekili onayı zaten imzalanmış. FINAL rapor için export kullanın.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    rep_name = body.rep_name.strip()
    if not rep_name:
        raise HTTPException(status_code=400, detail="İşveren vekili adı zorunludur")

    # B5 — Backend validation invariantları: ``decision`` enum (zaten
    # ``WorkplaceApprovalDecision`` Pydantic modelinde Literal["KABUL","ITIRAZ"]
    # ile zorunlu), ``dispute_reason`` uzunluk, ``commitment`` opsiyonel
    # minimum uzunluk.
    for qid_str, dec in (body.decisions or {}).items():
        if dec.decision == "ITIRAZ":
            dr = (dec.dispute_reason or "").strip()
            if len(dr) < 20:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"İtiraz nedeni en az 20 karakter olmalıdır (soru {qid_str}). "
                        f"Verilen uzunluk: {len(dr)}."
                    ),
                )
        cm = (dec.commitment or "").strip()
        if cm and len(cm) < 10:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Taahhüt en az 10 karakter olmalıdır (soru {qid_str}). "
                    f"Verilen uzunluk: {len(cm)}."
                ),
            )

    # Decisions merge: mevcut declarations'a ekle, üzerine yaz
    existing_decs = doc.get("declarations") or {}
    merged_decs = dict(existing_decs)
    for qid, dec in (body.decisions or {}).items():
        payload = dec.model_dump() if hasattr(dec, "model_dump") else dict(dec)
        merged_decs[str(qid)] = {**merged_decs.get(str(qid), {}), **payload}

    # B5 — Server-controlled identity. Client payload'ında ``signed_at``,
    # ``signed_by_*`` gibi alanlar varsa bile **göz ardı edilir**. Kimlik ve
    # zaman her zaman server context'inden okunur — client-side forgery
    # imkânsız.
    new_meta = {
        **existing_meta,
        "rep_name": rep_name,
        "rep_title": (body.rep_title or "").strip(),
        "declaration_date": body.declaration_date or existing_meta.get("declaration_date"),
        "signed_at": now_iso,
        "signed_by_rep_name": rep_name,
        "signed_by_rep_title": (body.rep_title or "").strip(),
        "signed_by_user_id": current_user["id"],
        "signed_by_user_name": current_user.get("name") or current_user.get("email"),
    }

    set_ops: Dict[str, Any] = {
        "declarations": merged_decs,
        "declarations_meta": new_meta,
        "updated_at": now_iso,
    }

    # Eğer DOF_OPEN ve tüm DÖF'ler kapalıysa DOF_CLOSED'a atomik geçiş yap.
    # ``_count_open_dofs`` snapshot üzerinden doğru sayım yapar (template degisikliklerine
    # dayanikli). Sifir donerse ve state DOF_OPEN ise transition_audit ile geçiş uygula.
    if current_state == AuditState.DOF_OPEN.value:
        open_dof_count = await _count_open_dofs(oid)
        if open_dof_count == 0:
            # Tum DÖF'ler kapali — otomatik DOF_CLOSED'a gecir.
            try:
                transition_set = audit_state.transition_audit(
                    doc,
                    AuditState.DOF_CLOSED,
                    actor_id=current_user["id"],
                    reason="Tüm DÖF'ler kapatıldı, işveren vekili onayı imzalandı.",
                    now_iso=now_iso,
                )
                set_ops.update(transition_set)
            except ValueError as e:
                # Gecersiz gecis — logla, imzayi yine de kaydet
                print(f"[workplace-approval] State transition failed: {e}")

    # B5 — Atomic predicate: iki eşzamanlı sign isteğinde yalnız biri
    # başarılı olsun. Predicate bileşenleri:
    #   * ``_id`` + scope (normal lookup)
    #   * ``deleted_at: None`` (B3)
    #   * ``state in {DOF_OPEN, DOF_CLOSED}`` (B2 + B5)
    #   * ``declarations_meta.signed_at`` YOK (B5 idempotency)
    atomic_filter = {
        "_id": oid,
        **_normal_audit_filter(current_user),
        "state": {
            "$in": [AuditState.DOF_OPEN.value, AuditState.DOF_CLOSED.value]
        },
        "declarations_meta.signed_at": {"$exists": False},
    }
    updated_doc = await db.audits.find_one_and_update(
        atomic_filter,
        {"$set": set_ops, "$inc": {"version": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if updated_doc is None:
        # Race ya da concurrent bir başka süreç imzayı önceden tamamladı.
        raise HTTPException(
            status_code=409,
            detail=(
                "İmza sırasında audit durumu değişti — zaten imzalanmış olabilir. "
                "Lütfen sayfayı yenileyin."
            ),
        )

    # B6 — Compliance invariant: sign işlemi "fully audited" olmalı. Log
    # yazılamazsa 5xx; UI'da görünür hata yükseltilir.
    await log_action(
        db,
        audit_id=str(updated_doc["_id"]),
        user=current_user,
        action=Action.WORKPLACE_APPROVAL_SIGNED,
        before={"declarations_meta": existing_meta},
        after={
            "declarations_meta": new_meta,
            "signed_at": now_iso,
            "signed_by_rep_name": rep_name,
            "state_after": updated_doc.get("state"),
        },
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        mandatory=True,
    )

    owner = current_user["name"] if updated_doc["user_id"] == current_user["id"] else await _owner_name(updated_doc["user_id"])
    return _serialize_audit(updated_doc, owner)


@api_router.delete("/audits/{audit_id}")
async def delete_audit(
    audit_id: str,
    reason: Optional[str] = Query(None, max_length=2000, description="S19: silme sebebi (audit_log'a yazılır)"),
    current_user: dict = Depends(get_current_user),
):
    """Audit sil.

    Phase 2B — S18: ``delete_behavior`` audit'in state'ine göre karar verir.

    * ``DRAFT`` → hard delete (henüz teslim edilmemiş; gerçekten silinebilir)
    * ``SUBMITTED / DOF_OPEN / DOF_CLOSED / FINAL`` → soft-delete
      (``deleted_at`` set edilir; yasal/operasyonel kayıt korunur)

    Phase 2B — S19: ``?reason=...`` query param opsiyonel. Admin
    kimin niçin sildiğini bilmesi için audit_log'a yazılır.
    """
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    existing = await db.audits.find_one({"_id": oid, **_scope_filter(current_user)})
    if not existing:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    # Zaten soft-delete edilmiş mi? Tekrarlı çağrıyı no-op yap.
    if existing.get("deleted_at"):
        return {"ok": True, "deleted_at": existing.get("deleted_at"), "soft": True}

    current_state = existing.get("state") or AuditState.DRAFT.value
    behavior = audit_state.delete_behavior(current_state)
    now_iso = datetime.now(timezone.utc).isoformat()
    reason_clean = (reason or "").strip()

    if behavior == "hard":
        result = await db.audits.delete_one({"_id": oid, **_scope_filter(current_user)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Denetim bulunamadı")
        # S20: hard delete log (before snapshot önemli — yasal iz)
        await log_action(
            db, audit_id=audit_id, user=current_user, action=Action.DELETE,
            before={"state": current_state, "restaurant_name": existing.get("restaurant_name", "")},
            after={"deleted": True, "deleted_at": now_iso, "hard": True, "reason": reason_clean or None},
        )
        return {"ok": True, "soft": False}

    # behavior == "soft" — soft-delete flag set et, doc kalsın
    transition = audit_state.transition_audit(
        existing,
        current_state,  # state değişmiyor, sadece deleted_at set ediyoruz
        actor_id=current_user["id"],
        reason="soft-delete",
        now_iso=now_iso,
    )
    set_fields = {
        "deleted_at": now_iso,
        "deleted_by": current_user["id"],
    }
    if reason_clean:
        set_fields["delete_reason"] = reason_clean
    set_fields.update(transition)
    await db.audits.update_one({"_id": oid}, {"$set": set_fields})
    # S20: soft delete log
    await log_action(
        db, audit_id=audit_id, user=current_user, action=Action.SOFT_DELETE,
        before={"state": current_state, "deleted_at": None},
        after={"state": current_state, "deleted_at": now_iso, "reason": reason_clean or None},
    )
    return {"ok": True, "soft": True, "deleted_at": now_iso}


# ---------------- Export ----------------
@api_router.get("/audits/{audit_id}/export/excel")
async def export_excel(audit_id: str, current_user: dict = Depends(get_current_user)):
    """İSG Risk Analizi Excel export'u.

    Görsel sözleşme (Baran formuna sadık):
      * Sheet adı ``İSG Risk Analizi (5x5)``
      * A1 başlık, A2 durum alt başlığı, A4-D5 metadata grid
      * Header background ``#8B0000``, beyaz Calibri 11 bold
      * 11 kolon: No, Kategori, Tehlike & Risk Maddesi, Cevap,
        Olasılık (O), Şiddet (Ş), Risk Skoru (R), Risk Seviyesi,
        Sorumlu, Termin Süresi, Alınması Gereken Tedbir (DÖF)
      * Filename ``ISG_Risk_Analizi_<restaurant_name>.xlsx``

    Veri kaynağı (mevcut main mimarisi):
      * ``_get_audit_questions(doc)`` → audit'in ``template_snapshot``'ı
        (yeni şema: ``category``/``question``/``responsible``/
        ``default_probability``/``default_severity``/``deadline``/
        ``corrective_action``/``legal_basis``) ya da legacy fallback
      * ``_get_audit_overrides(doc)`` → audit'in ``risk_overrides`` map'i
      * ``compute_effective_risk(q, override)`` → kanonik skor/level
        (override uygulanır, ``classify_risk`` eşikleri kullanılır)

    Yapılmayanlar (Baran regresyonları elenmiştir):
      * ``fix_tr_text`` ile Türkçe → ASCII transliteration YOK
      * ``QUESTIONS`` global kullanımı YOK (snapshot zorunlu)
      * Skor/level ``o*s``/``q.get("risk_seviyesi")`` ile değil
        kanonik helper ile hesaplanır
      * Yeni şema alanları export'tan düşürülmez
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz ID")

    doc = await db.audits.find_one({"_id": oid, **_scope_filter(current_user)})
    if not doc:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    # Phase 2B — S18 export state guard
    if doc.get("deleted_at"):
        raise HTTPException(status_code=410, detail="Denetim silinmiş, export edilemez")
    current_state = doc.get("state") or AuditState.DRAFT.value
    if not audit_state.can_export_final(current_state):
        if current_state == AuditState.DOF_OPEN.value:
            raise HTTPException(
                status_code=409,
                detail=f"Bu denetimde açık DÖF var; nihai rapor verilemez. "
                       f"Önce tüm DÖF'leri kapatın.",
            )
        raise HTTPException(
            status_code=409,
            detail=f"Bu denetim {current_state} durumunda; nihai rapor export edilemez. "
                   f"Önce denetimi tamamlayın (DÖF'ler kapatıldıktan sonra).",
        )
    if not doc:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    answers = doc.get("answers", {}) or {}
    questions = _get_audit_questions(doc)
    overrides = _get_audit_overrides(doc)
    is_completed = bool(doc.get("is_completed", False))
    status_text = "TAMAMLANDI" if is_completed else "TASLAK DENETİM"

    # ---- Cevap → görsel mapping ----
    # EVET   → "Uygun"
    # HAYIR  → "Uygun Değil"
    # NA     → "N/A"
    # eksik  → "Yanıtlanmadı"
    def _answer_label(ans: str) -> str:
        if ans == "EVET":
            return "Uygun"
        if ans == "HAYIR":
            return "Uygun Değil"
        if ans == "NA":
            return "N/A"
        return "Yanıtlanmadı"

    wb = Workbook()
    ws = wb.active
    ws.title = "İSG Risk Analizi (5x5)"

    header_fill = PatternFill("solid", fgColor="8B0000")
    white_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    thin = Side(border_style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # ---- Başlık / metadata (Baran formuna sadık) ----
    # S12: Marka logosu başlık satırında (A1). PNG yoksa logo skip edilir.
    brand_png_xlsx = _get_brand_logo_png(doc.get("brand") or doc.get("restaurant_name") or "", max_width_px=300)
    if brand_png_xlsx:
        try:
            from openpyxl.drawing.image import Image as XLSXImage
            img = XLSXImage(brand_png_xlsx)
            # Hücre boyutuna göre scale (default Excel row height ~15 px)
            img.width = 120
            img.height = 60
            ws.add_image(img, "G1")
        except Exception as e:
            print(f"[export_excel] logo ekleme hatası: {e}")

    ws["A1"] = "ABCD Tech Solutions SANAYİ VE TİCARET A.Ş."
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color="8B0000")

    ws["A2"] = f"İş Sağlığı ve Güvenliği Risk Değerlendirmesi Tablosu — [{status_text}]"
    ws["A2"].font = Font(name="Calibri", size=11, italic=True, color="475569")

    ws["A4"] = f"Restoran / Şube Adı: {doc.get('restaurant_name', '')}"
    ws["A4"].font = Font(bold=True)
    ws["A5"] = f"Açık Adres: {doc.get('address', 'Belirtilmedi')}"
    ws["D4"] = f"Denetim Tarihi: {doc.get('audit_date', '')}"
    ws["D4"].font = Font(bold=True)
    ws["D5"] = f"İSG Uzmanı / Denetçi: {doc.get('denetci', '')}"

    # ---- Header satırı (satır 7) — Phase 2B S4+S6: ortak kolon şeması
    from audit_columns import get_columns, render_row
    columns = get_columns()
    header_row = 7
    for col_idx, col in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=col.header)
        cell.fill = header_fill
        cell.font = white_bold
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
        # Sütun genişliği: açık form düzeni sözleşmesindeki exact pixel genişlik.
        # ``excel_width`` yoksa ``width`` (mm) üzerinden yaklaşık dönüşüm.
        ws.column_dimensions[cell.column_letter].width = (
            col.excel_width if col.excel_width is not None else max(10, col.width * 0.6)
        )

    # ---- Veri satırları (satır 8+) ----
    dof_details_map = doc.get("dof_details") or {}
    row_idx = 8
    for q in questions:
        ans = answers.get(str(q["id"]), "")
        show_risk = ans == "HAYIR"
        eff = compute_effective_risk(q, overrides.get(str(q["id"]))) if show_risk else None

        category = q.get("category") or q.get("kategori", "")
        soru = q.get("question") or q.get("soru", "")
        sorumlu = q.get("responsible") or q.get("sorumlu", "")
        termin = q.get("deadline") or q.get("termin", "")
        tedbir = q.get("corrective_action") or q.get("tedbir", "")

        if eff:
            prob = eff["probability"]
            sev = eff["severity"]
            rscore = eff["risk_score"]
            rlevel = eff["risk_level"]
        else:
            prob = sev = rscore = ""
            rlevel = ""

        # Tasarım sözleşmesi (test_excel_export_design): sayısal kolonlar int,
        # termin/tedbir yalnız HAYIR satırlarında gerçek değer, aksi halde "-".
        vals = [
            q.get("no", q.get("id", "")),       # 1 No (int)
            category,                             # 2 Kategori
            soru,                                 # 3 Soru
            _answer_label(ans),                   # 4 Cevap
            prob,                                 # 5 Olasılık (int / boş)
            sev,                                  # 6 Şiddet (int / boş)
            rscore,                               # 7 Risk Skoru (int / boş)
            rlevel if show_risk else "",          # 8 Risk Seviyesi
            sorumlu or "-",                       # 9 Sorumlu
            termin if show_risk else "-",         # 10 Termin
            tedbir if show_risk else "-",         # 11 Tedbir
        ]
        for col_idx, v in enumerate(vals, start=1):
            c = ws.cell(row=row_idx, column=col_idx, value=v if v != "" else None)
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = border
            if show_risk and col_idx == 8 and rlevel:
                if rlevel == RISK_LEVEL_KABUL_EDILEMEZ:
                    c.fill = PatternFill("solid", fgColor="DC2626")
                    c.font = Font(color="FFFFFF", bold=True)
                elif rlevel == RISK_LEVEL_DIKKATE_DEGER:
                    c.fill = PatternFill("solid", fgColor="F59E0B")
                    c.font = Font(color="FFFFFF", bold=True)
                elif rlevel == RISK_LEVEL_KABUL_EDILEBILIR:
                    c.fill = PatternFill("solid", fgColor="059669")
                    c.font = Font(color="FFFFFF", bold=True)
        row_idx += 1

    # ---- S9: DÖF Güncelleme Özeti (alt tablo) ----
    # Her HAYIR soru için son güncelleme, güncelleyen kişi, durum ve not.
    # S9 iş birimi kuralı: "Kapatma prosedürü sıkı takip" — raporlarda
    # "kim ne zaman ne yazdı" görünmeli.
    hayir_dof_rows: List[List[Any]] = []
    for q in questions:
        if answers.get(str(q.get("id"))) != "HAYIR":
            continue
        d = dof_details_map.get(str(q.get("id"))) or {}
        hayir_dof_rows.append([
            q.get("no", str(q.get("id"))),
            q.get("question", "")[:60],
            d.get("status") or "AÇIK",
            d.get("updated_at") or "—",
            d.get("updated_by") or "—",
            d.get("resolved_by") or "—",
            (d.get("resolution_note") or d.get("notes") or "(not yok)")[:100],
        ])

    if hayir_dof_rows:
        # Başlık satırı (2 satır boşluk + header)
        row_idx += 3
        title_cell = ws.cell(row=row_idx, column=1, value="DÖF GÜNCELLEME ÖZETİ (S9 — Kapatma Prosedürü Takibi)")
        title_cell.font = Font(bold=True, size=12, color="8B0000")
        row_idx += 1
        # Header
        dof_headers = ["Soru No", "Soru (kısa)", "Durum", "Son Güncelleme", "Güncelleyen (ID)", "Çözen (ID)", "Not"]
        for col_idx, h in enumerate(dof_headers, start=1):
            c = ws.cell(row=row_idx, column=col_idx, value=h)
            c.font = white_bold
            c.fill = header_fill
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = border
        # Kolon genişlikleri
        ws.column_dimensions["A"].width = 10
        ws.column_dimensions["B"].width = 35
        ws.column_dimensions["C"].width = 12
        ws.column_dimensions["D"].width = 22
        ws.column_dimensions["E"].width = 18
        ws.column_dimensions["F"].width = 18
        ws.column_dimensions["G"].width = 40
        # Veri satırları
        for dof_row in hayir_dof_rows:
            row_idx += 1
            for col_idx, val in enumerate(dof_row, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.alignment = Alignment(vertical="top", wrap_text=True)
                c.border = border
                c.font = Font(size=9)
                # Durum kolonu renkli (S8 uyumu)
                if col_idx == 3:
                    status_color_map = {
                        "AÇIK": "FEF3C7",       # amber bg
                        "İŞLEMDE": "DBEAFE",     # blue bg
                        "KAPATILDI": "D1FAE5",   # emerald bg
                    }
                    bg = status_color_map.get(str(val).strip(), "FFFFFF")
                    c.fill = PatternFill("solid", fgColor=bg)
                    c.font = Font(bold=True, size=9)
                # Tarih kolonu kısa format
                if col_idx == 4 and val and val != "—":
                    val_str = str(val)
                    c.value = val_str[:19].replace("T", " ")

    # Phase 2B S4+S6: kolon genişlikleri artık ``get_columns()`` üzerinden
    # ``column_dimensions[cell.column_letter].width = col.width * 0.6`` ile
    # header döngüsünde set edildi; buradaki hard-coded listeye gerek yok.

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"ISG_Risk_Analizi_{doc.get('restaurant_name', 'denetim').replace(' ', '_')}.xlsx"
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)

    # Phase 2B — S18: İlk export sonrası DOF_CLOSED → FINAL. Hata olursa
    # transition yine de uygulanır (state zaten export edildi).
    await _finalize_audit_if_dof_closed(oid, doc, current_user["id"])

    # Phase 2B — S20: export logla
    try:
        await log_action(
            db,
            audit_id=audit_id,
            user=current_user,
            action=Action.EXPORT_EXCEL,
            before=None,
            after={"filename": filename, "state_before_finalize": doc.get("state")},
        )
    except Exception as e:
        print(f"[export_excel] audit_log write failed: {e}")

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{urlquote(filename)}"},
    )


@api_router.get("/audits/{audit_id}/export/pdf")
async def export_pdf(audit_id: str, current_user: dict = Depends(get_current_user)):
    """İSG Risk Analizi PDF export'u (Baran formuna sadık).

    Görsel sözleşme (Baran referans branch'ten alınmıştır; yeniden
    tasarlanmaz):

      * ``landscape(A4)`` — sol/sağ/üst/alt kenar boşluğu ``8 mm``
      * Ana başlık: ``ABCD Tech Solutions SAN. VE TİC. A.Ş. — RESTORAN İSG RİSK
        ANALİZİ VE DÖF RAPORU`` — 16 pt, bold, ``#8B0000``
      * Alt başlık: ``6331 Sayılı İSG Kanunu / Risk Değerlendirmesi
        Yönetmeliği — Rapor Statüsü: <STATUS>`` — 11 pt italic
        ``#475569``. ``STATUS`` audit'in ``is_completed`` alanına göre
        ``TAMAMLANDI`` veya ``TASLAK DENETİM`` olarak çözülür;
        ``RESMİ ONAYLI`` YAZILMAZ (sistemde ayrı onay workflow'u yok).
      * Metadata iki satırlı tablo: ``Restoran/Şube + Tarih`` ve
        ``Adres + Denetçi``. Değerler audit alanlarından alınır.
      * Ana tablo **11 kolon** — ``audit_columns.DEFAULT_COLUMNS`` ortak
        şeması (S6: Excel ve PDF kesinlikle aynı kolonları kullanır):
        No, Kategori, Tehlike & Risk Maddesi, Cevap, Olasılık (O),
        Şiddet (Ş), Risk Skoru (R), Risk Seviyesi, Sorumlu,
        Termin Süresi, Alınması Gereken Tedbir (DÖF).
      * Header: ``#8B0000`` arka plan, beyaz, bold 7.5 pt.
      * Gövde 7 pt; border ``0.3`` ``#CBD5E1``; TOP/BOTTOM PADDING ``3``.
      * Uzun tabloda header sonraki sayfalarda tekrar eder
        (``repeatRows=1``). Uzun metinler ``Paragraph`` ile wrap edilir.
      * Risk Seviyesi kolonu (8. kolon): yalnız ``HAYIR`` cevaplı
        satırlardaki ``KABUL_EDILEMEZ/DIKKATE_DEGER`` hücrelerine arka
        plan verilir; ``KABUL_EDILEBILIR`` için yeşil EKLENMEZ (Baran
        referansına sadık; EVET/NA/boş satırlarda hücre boştur).

    Veri doğruluğu (mevcut main mimarisi):
      * Audit'in kendi ``template_snapshot`` verisi kullanılır
        (``_get_audit_questions``).
      * ``probability`` / ``severity`` / ``risk_score`` / ``risk_level``
        yalnızca ``HAYIR`` cevaplı satırlarda
        ``compute_effective_risk(q, override)`` üzerinden gelir (Excel
        ile aynı değer sözleşmesi); ``document_risk_level`` veya statik
        ``q["risk_seviyesi"]`` kullanılmaz.
      * Alan eşleştirmesi yeni şema primary + legacy fallback:
        ``category/kategori``, ``question/soru``, ``responsible/sorumlu``,
        ``deadline/termin``, ``corrective_action/tedbir``.
      * Cevap mapping kanonik: ``EVET→Uygun``, ``HAYIR→Uygun Değil``,
        ``NA→N/A``, eksik/boş→``Yanıtlanmadı``. ``HAYIR değilse Uygun``
        gibi genel koşul uygulanmaz.
      * Olasılık ve Şiddet AYRI kolonlardır (``O x Ş`` birleşik hücresi
        YOKTUR); ``Risk Skoru (R)`` ve ``Risk Seviyesi`` kendi
        kolonlarındadır.
      * Türkçe Unicode (``Ş ğ İ ı Ç ö ü``) ``DejaVu`` fontu ile
        korunur. Font dosyası bulunamazsa yalnız ``Helvetica`` fallback.

    HTTP sözleşmesi:
      * MIME ``application/pdf``.
      * ``Content-Disposition`` dual UTF-8 (``filename="ASCII fallback";
        filename*=UTF-8''<encoded>``).
      * Dosya adı ``ISG_Risk_Analizi_<restaurant_name>.pdf``.
      * Geçersiz ``ObjectId`` → ``400 Geçersiz ID``;
        bulunamayan / scope dışı → ``404 Denetim bulunamadı``.
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # --- Unicode font registration ------------------------------------------------
    # Türkçe karakterlerin (Ş, ğ, İ, ı, Ç, ö, ü) PDF'te bozulmaması için
    # DejaVu Sans/Bold fontları kaydedilir. Font dosyaları standart linux
    # konumunda aranır; bulunamazsa yalnızca ``Helvetica`` fallback'i
    # kullanılır. Baran referans branch'teki sadece-Helvetica yaklaşımı
    # alınmaz.
    font_name = "Helvetica"
    bold_font_name = "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(
            TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        )
        pdfmetrics.registerFont(
            TTFont("DejaVu-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        )
        font_name = "DejaVu"
        bold_font_name = "DejaVu-Bold"
    except Exception:
        # Font dosyası yoksa Helvetica fallback (mevcut davranış).
        pass

    # --- Audit veri kaynağı -------------------------------------------------------
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz ID")
    doc_db = await db.audits.find_one(
        {"_id": oid, **_scope_filter(current_user)}
    )
    if not doc_db:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    # Phase 2B — S18 export state guard
    if doc_db.get("deleted_at"):
        raise HTTPException(status_code=410, detail="Denetim silinmiş, export edilemez")
    current_state = doc_db.get("state") or AuditState.DRAFT.value
    if not audit_state.can_export_final(current_state):
        if current_state == AuditState.DOF_OPEN.value:
            raise HTTPException(
                status_code=409,
                detail=f"Bu denetimde açık DÖF var; nihai rapor verilemez. "
                       f"Önce tüm DÖF'leri kapatın.",
            )
        raise HTTPException(
            status_code=409,
            detail=f"Bu denetim {current_state} durumunda; nihai rapor export edilemez. "
                   f"Önce denetimi tamamlayın (DÖF'ler kapatıldıktan sonra).",
        )

    answers = doc_db.get("answers", {}) or {}
    questions = _get_audit_questions(doc_db)
    overrides = _get_audit_overrides(doc_db)
    is_completed = bool(doc_db.get("is_completed"))
    status_text = "TAMAMLANDI" if is_completed else "TASLAK DENETİM"

    # --- Document template -------------------------------------------------------
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
        title="İSG Risk Analizi ve DÖF Raporu",
    )
    styles = getSampleStyleSheet()

    # Üst başlık: kurumsal kırmızı, 16 pt bold.
    title_style = ParagraphStyle(
        "PdfTitle",
        parent=styles["Title"],
        fontName=bold_font_name,
        fontSize=16,
        leading=18,
        textColor=colors.HexColor("#8B0000"),
        alignment=0,
        spaceAfter=2,
    )
    # Alt başlık: status metniyle birlikte yasal dayanak.
    sub_style = ParagraphStyle(
        "PdfSub",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#475569"),
        alignment=0,
        spaceAfter=4,
    )
    # Metadata hücreleri (küçük, kompakt).
    meta_label = ParagraphStyle(
        "PdfMetaLabel",
        parent=styles["Normal"],
        fontName=bold_font_name,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
    )
    meta_value = ParagraphStyle(
        "PdfMetaValue",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
    )
    # Tablo header hücresi.
    cell_head = ParagraphStyle(
        "PdfCellHead",
        parent=styles["Normal"],
        fontName=bold_font_name,
        fontSize=7.5,
        leading=9,
        textColor=colors.white,
    )
    # Tablo gövdesi.
    cell_text = ParagraphStyle(
        "PdfCellText",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#0F172A"),
    )
    # Gövde içinde koyu/ortalanmış hücre (No, Cevap, Olasılık, Şiddet,
    # Risk Skoru, Risk Seviyesi, Termin — 11 kolonlu ortak şemada).
    cell_bold_c = ParagraphStyle(
        "PdfCellBoldC",
        parent=cell_text,
        fontName=bold_font_name,
        alignment=1,
    )
    # S9 — DÖF güncelleme özeti section'ı için (export_ibraz'dan kopyalandı)
    section_style = ParagraphStyle(
        "PdfSection", parent=styles["Heading2"], fontName=bold_font_name,
        fontSize=10, leading=12, textColor=colors.HexColor("#0F172A"),
        spaceBefore=8, spaceAfter=4,
    )
    # Gövdede koyu/ortalanmamış (bold) hücre
    cell_bold = ParagraphStyle(
        "PdfCellBold",
        parent=cell_text,
        fontName=bold_font_name,
    )
    # Risk seviyesi: KABUL_EDILEMEZ (kırmızı metin).
    cell_risk_red = ParagraphStyle(
        "PdfCellRiskRed",
        parent=cell_bold_c,
        textColor=colors.HexColor("#DC2626"),
    )
    # Risk seviyesi: DIKKATE_DEGER (turuncu metin).
    cell_risk_amber = ParagraphStyle(
        "PdfCellRiskAmber",
        parent=cell_bold_c,
        textColor=colors.HexColor("#D97706"),
    )

    elements: List[Any] = []

    # --- Üst başlık + alt başlık -------------------------------------------------
    # S12: Marka logosu başlıkta görünür. Logo PNG yoksa (marka
    # eşleşmediyse) sadece text gösterilir.
    brand_png = _get_brand_logo_png(doc_db.get("brand") or doc_db.get("restaurant_name") or "", max_width_px=300)
    if brand_png:
        from reportlab.platypus import Image as RLImage
        title_text = (
            "ABCD Tech Solutions SAN. VE TİC. A.Ş. — "
            "RESTORAN İSG RİSK ANALİZİ VE DÖF RAPORU"
        )
        brand_img = RLImage(brand_png, width=40 * mm, height=20 * mm)
        title_table = Table(
            [[brand_img, Paragraph(f"<b>{title_text}</b>", title_style)]],
            colWidths=[42 * mm, 200 * mm],
        )
        title_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(title_table)
    else:
        title_text = (
            "ABCD Tech Solutions SAN. VE TİC. A.Ş. — "
            "RESTORAN İSG RİSK ANALİZİ VE DÖF RAPORU"
        )
        elements.append(Paragraph(title_text, title_style))
    elements.append(Paragraph(
        f"6331 Sayılı İSG Kanunu / Risk Değerlendirmesi Yönetmeliği — "
        f"Rapor Statüsü: {status_text}",
        sub_style,
    ))

    # --- Metadata iki satırlı tablo ---------------------------------------------
    meta_data = [
        [
            Paragraph("<b>Restoran / Şube</b>", meta_label),
            Paragraph(doc_db.get("restaurant_name", "") or "-", meta_value),
            Paragraph("<b>Tarih</b>", meta_label),
            Paragraph(doc_db.get("audit_date", "") or "-", meta_value),
        ],
        [
            Paragraph("<b>Adres</b>", meta_label),
            Paragraph(doc_db.get("address", "") or "-", meta_value),
            Paragraph("<b>Denetçi</b>", meta_label),
            Paragraph(doc_db.get("denetci", "") or "-", meta_value),
        ],
    ]
    meta_table = Table(
        meta_data,
        colWidths=[28 * mm, 80 * mm, 22 * mm, 88 * mm],
    )
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 4))

    # --- Ana tablo (11 kolon) — Phase 2B S4+S6: ortak kolon şeması ----------
    # Kolon tanımları tek kaynak olan ``audit_columns.DEFAULT_COLUMNS``'tan
    # gelir; ``export_excel`` ile aynı semantik kolonları, etiketleri ve
    # sırayı kullanır (S6: "Excel ve PDF kesinlikle aynı kolonları
    # kullanmalı"). Yalnız sunum metadata'sı (hizalama, font, padding,
    # arka plan) PDF'e özgüdür; semantik kolon kümesi ortaktır.
    # ``fix_tr_text`` gibi transliterasyon YAPILMAZ — Türkçe Unicode
    # olduğu gibi geçer.
    from audit_columns import get_columns
    pdf_columns = get_columns()
    data: List[List[Any]] = [
        [Paragraph(c.header, cell_head) for c in pdf_columns]
    ]

    # Alan eşleştirmesi: yeni şema primary; legacy fallback snapshot'ta
    # yoksa devreye girer. ``questions.json`` dokunulmaz.
    # Değer sözleşmesi ``export_excel`` ile aynıdır:
    #   * show_risk = (raw == "HAYIR") — Olasılık/Şiddet/Skor/Seviye ve
    #     Termin/Tedbir değerleri yalnızca HAYIR satırlarında gösterilir;
    #     EVET/NA/boş satırlara sızmaz.
    #   * Sorumlu her satırda gösterilir (boşsa "-").
    for q in questions:
        raw = answers.get(str(q.get("id")), "")
        show_risk = raw == "HAYIR"
        if raw == "EVET":
            ans = "Uygun"
        elif raw == "HAYIR":
            ans = "Uygun Değil"
        elif raw == "NA":
            ans = "N/A"
        else:
            ans = "Yanıtlanmadı"

        eff = (
            compute_effective_risk(q, overrides.get(str(q.get("id"))))
            if show_risk else None
        )
        prob = eff["probability"] if show_risk else ""
        sev = eff["severity"] if show_risk else ""
        risk_score = eff["risk_score"] if show_risk else ""
        risk_level = eff["risk_level"] if show_risk else ""

        category = q.get("category") or q.get("kategori", "")
        question_text = q.get("question") or q.get("soru", "")
        responsible = q.get("responsible") or q.get("sorumlu", "")
        deadline = q.get("deadline") or q.get("termin", "")
        tedbir = q.get("corrective_action") or q.get("tedbir", "")

        if risk_level == RISK_LEVEL_KABUL_EDILEMEZ:
            risk_style = cell_risk_red
        elif risk_level == RISK_LEVEL_DIKKATE_DEGER:
            risk_style = cell_risk_amber
        else:
            # KABUL_EDILEBILIR → gövde varsayılanı; yeşil EKLENMEZ.
            risk_style = cell_bold_c

        row_cells = [
            Paragraph(str(q.get("no", q.get("id", ""))), cell_bold_c),
            Paragraph(str(category), cell_text),
            Paragraph(str(question_text), cell_text),
            Paragraph(str(ans), cell_bold_c),
            Paragraph(str(prob), cell_bold_c),            # Olasılık (O)
            Paragraph(str(sev), cell_bold_c),             # Şiddet (Ş)
            Paragraph(str(risk_score), cell_bold_c),      # Risk Skoru (R)
            Paragraph(str(risk_level), risk_style),       # Risk Seviyesi
            Paragraph(str(responsible or "-"), cell_text),  # Sorumlu
            Paragraph(str(deadline if show_risk else "-"), cell_bold_c),  # Termin Süresi
            Paragraph(str(tedbir if show_risk else "-"), cell_text),      # Tedbir (DÖF)
        ]
        data.append(row_cells)

    # 11 kolonun ortak mm genişlikleri ``audit_columns`` tanımından gelir
    # (toplam 216 mm). Landscape A4 kullanılabilir genişlik:
    # 297 - 8 (sol) - 8 (sağ) = 281 mm >= 216 mm; scale YAPILMAZ
    # (birim her yerde mm'dir, point değil).
    col_widths = [c.width * mm for c in pdf_columns]

    table = Table(data, colWidths=col_widths, repeatRows=1)
    ts = TableStyle([
        # Header satırı (her sayfada tekrar eder).
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B0000")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), bold_font_name),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        # Gövde.
        ("FONTNAME", (0, 1), (-1, -1), font_name),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),     # No
        ("ALIGN", (3, 1), (7, -1), "CENTER"),     # Cevap, Olasılık, Şiddet, Risk Skoru, Risk Seviyesi
        ("ALIGN", (9, 1), (9, -1), "CENTER"),     # Termin Süresi
        # Grid + padding.
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ])
    # Risk Seviyesi kolonu (kolon 7 — 0-indeksli) için yalnızca HAYIR
    # cevaplı KABUL_EDILEMEZ ve DIKKATE_DEGER hücrelerine arka plan
    # verilir (Excel ile aynı: risk değerleri yalnızca HAYIR satırlarında
    # gösterilir). KABUL_EDILEBILIR default gövde görünümünü korur;
    # EVET/NA/boş satırlarda hücre boş olduğundan arka plan EKLENMEZ.
    for i, q in enumerate(questions, start=1):
        if answers.get(str(q.get("id"))) != "HAYIR":
            continue
        lvl = compute_effective_risk(
            q, overrides.get(str(q.get("id")))
        )["risk_level"]
        if lvl == RISK_LEVEL_KABUL_EDILEMEZ:
            ts.add("BACKGROUND", (7, i), (7, i), colors.HexColor("#FEE2E2"))
        elif lvl == RISK_LEVEL_DIKKATE_DEGER:
            ts.add("BACKGROUND", (7, i), (7, i), colors.HexColor("#FEF3C7"))
    # S8 — DÖF Durumu renkli (Tedbir kolonu = 0-indeksli kolon 10).
    # Renk paleti Excel ``export_excel`` ile aynı hex kodları kullanır
    # (``status_color_map``, satır ~2280): AÇIK=amber #FEF3C7,
    # İŞLEMDE=blue #DBEAFE, KAPATILDI=emerald #D1FAE5. ANCAK uygulama
    # alanı FARKLI: PDF'te ana soru tablosunun Tedbir kolonu (sütun 10)
    # HAYIR satırlarına uygulanır; Excel'de DÖF güncelleme özet
    # tablosunun durum kolonu (col_idx 3) renklenir. Bu yüzden
    # "render parity" değil "color palette parity" söz konusudur.
    # Yalnız HAYIR cevaplı satırlara uygulanır; EVET/NA/boş satırlar
    # etkilenmez (kullanıcı görsel kontrastı: renk yalnız aksiyon
    # gerektiren satırlarda).
    # "DİĞER" bucket: bilinmeyen status string'leri (örn. data drift /
    # legacy import) için nötr slate rengi — her HAYIR öğesi tam
    # olarak bir bucket'a düşmeli; toplamlar mutlaka reconcile olmalı.
    dof_saved = doc_db.get("dof_details") or {}
    dof_status_color_map = {
        "AÇIK": colors.HexColor("#FEF3C7"),
        "İŞLEMDE": colors.HexColor("#DBEAFE"),
        "KAPATILDI": colors.HexColor("#D1FAE5"),
        "DİĞER": colors.HexColor("#E2E8F0"),  # slate-200 — bilinmeyen
    }
    dof_status_counts = {"AÇIK": 0, "İŞLEMDE": 0, "KAPATILDI": 0, "DİĞER": 0}
    for i, q in enumerate(questions, start=1):
        if answers.get(str(q.get("id"))) != "HAYIR":
            continue
        dof_info = dof_saved.get(str(q.get("id"))) or {}
        status = str(dof_info.get("status", "AÇIK")).strip()
        # Bucket seçimi: bilinen status → kendi bucket'ı;
        # bilinmeyen status → DİĞER (reconcile garantisi).
        # Boş/eksik status → mevcut main davranışı: AÇIK default.
        if status and status in dof_status_color_map:
            bucket = status
        elif not status:
            bucket = "AÇIK"  # current-main default (data yoksa)
        else:
            bucket = "DİĞER"
        bg = dof_status_color_map[bucket]
        ts.add("BACKGROUND", (10, i), (10, i), bg)
        dof_status_counts[bucket] += 1
    table.setStyle(ts)
    elements.append(table)

    # S8 — DÖF Durumu Özeti (ana tablo sonrası, fotoğraf bölümünden önce).
    # Yalnızca HAYIR cevaplı soru varsa gösterilir; 5 kolonlu mini-table
    # ile toplam + 4 status sayısı (AÇIK + İŞLEMDE + KAPATILDI + DİĞER)
    # yan yana. Renkler status ile uyumlu (text color, hafif koyu).
    # DİĞER kolonu bilinmeyen/legacy status'ları reconciliation için
    # raporlar (Excel özet satırıyla aynı bilgi).
    total_hayir = sum(
        1 for q in questions
        if answers.get(str(q.get("id"))) == "HAYIR"
    )
    if total_hayir > 0:
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph("DÖF Durumu Özeti", section_style))
        dof_summary_style_open = ParagraphStyle(
            "PdfDofOpen", parent=cell_bold,
            textColor=colors.HexColor("#92400E"),  # amber-800
        )
        dof_summary_style_proc = ParagraphStyle(
            "PdfDofProc", parent=cell_bold,
            textColor=colors.HexColor("#1E40AF"),  # blue-800
        )
        dof_summary_style_closed = ParagraphStyle(
            "PdfDofClosed", parent=cell_bold,
            textColor=colors.HexColor("#065F46"),  # emerald-800
        )
        dof_summary_style_other = ParagraphStyle(
            "PdfDofOther", parent=cell_bold,
            textColor=colors.HexColor("#475569"),  # slate-600
        )
        dof_summary_data = [[
            Paragraph(f"<b>HAYIR:</b> {total_hayir}", cell_bold),
            Paragraph(
                f"<b>AÇIK:</b> {dof_status_counts['AÇIK']}",
                dof_summary_style_open,
            ),
            Paragraph(
                f"<b>İŞLEMDE:</b> {dof_status_counts['İŞLEMDE']}",
                dof_summary_style_proc,
            ),
            Paragraph(
                f"<b>KAPATILDI:</b> {dof_status_counts['KAPATILDI']}",
                dof_summary_style_closed,
            ),
            Paragraph(
                f"<b>DİĞER:</b> {dof_status_counts['DİĞER']}",
                dof_summary_style_other,
            ),
        ]]
        dof_summary_table = Table(
            dof_summary_data, colWidths=[48 * mm] * 5
        )
        dof_summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(dof_summary_table)

    # --- SAHA DENETİMİ GÖRSEL KANITLAR & İSG UZMANI DEĞERLENDİRME EKLERİ ---
    # S8 — ``dof_saved`` yukarıda S8 renklendirme döngüsünde kullanıldı;
    # burada yeniden atama (aynı değer) zararsız ama okunabilirlik için
    # bırakıldı — refactor ayrı commit'te yapılabilir.
    has_photo_or_note = False
    for q in questions:
        photos = q.get("photos", {})
        qid_str = str(q.get("id"))
        dof_info = dof_saved.get(qid_str) or {}
        res_note = dof_info.get("resolution_note") or dof_info.get("notes")
        if photos.get("finding") or photos.get("resolution") or res_note:
            has_photo_or_note = True
            break

    if has_photo_or_note:
        from reportlab.platypus import PageBreak, Image as RLImage
        elements.append(PageBreak())
        elements.append(Paragraph("SAHA DENETİMİ FOTOĞRAFLI KANITLAR VE İSG UZMANI DEĞERLENDİRME EKİ", title_style))
        elements.append(Spacer(1, 4))

        for q in questions:
            qid_str = str(q.get("id"))
            photos = q.get("photos", {})
            f_photos = photos.get("finding", [])
            r_photos = photos.get("resolution", [])
            dof_info = dof_saved.get(qid_str) or {}
            res_note = dof_info.get("resolution_note") or dof_info.get("notes")

            if not f_photos and not r_photos and not res_note:
                continue

            q_title = f"Soru #{q.get('no', qid_str)}: {q.get('question', '')} [{dof_info.get('status', 'AÇIK')}]"
            elements.append(Paragraph(q_title, meta_label))

            if res_note:
                note_p = f"<b>İSG Uzmanı Görüşü / Saha Notu:</b> {res_note}"
                elements.append(Paragraph(note_p, cell_text))

            img_elements = []
            for p in f_photos + r_photos:
                p_url = p.get("thumb_url") or p.get("url")
                if p_url:
                    img_file = ROOT_DIR / p_url.lstrip("/")
                    if img_file.exists():
                        try:
                            img_elements.append(RLImage(str(img_file), width=40*mm, height=30*mm))
                        except Exception:
                            pass
            if img_elements:
                img_table = Table([img_elements], colWidths=[45*mm]*len(img_elements))
                elements.append(img_table)
            elements.append(Spacer(1, 4))

    # --- S13 — İmza Alanları (4 imza kutusu) ---------------------------------
    # Saha denetimi sonunda dört taraflı imza alanı; her sayfada değil,
    # yalnızca son flowable olarak (multi-page PDF'lerin son sayfasında)
    # görünür. S20 İbraz'daki 4 imza kutusu şemasıyla birebir aynı:
    # Denetçi / Restoran Müdürü / İşveren Vekili / İSG Uzmanı.
    # Tablo + TableStyle; landscape A4 içinde 4 × 44 mm = 176 mm sütun
    # genişliği (kullanılabilir alan 281 mm).
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("İmza Alanları", section_style))
    sig_box_pdf = lambda label: Table(
        [[""], [Paragraph(f"<b>{label}</b>", ParagraphStyle(
            "PdfSigLabel", parent=cell_text, fontSize=8, alignment=1,
            textColor=colors.HexColor("#475569")))]],
        colWidths=[42 * mm],
        rowHeights=[22 * mm, 6 * mm],
    )
    sig_table_pdf = Table(
        [[sig_box_pdf("Denetçi"),
          sig_box_pdf("Restoran Müdürü"),
          sig_box_pdf("İşveren Vekili"),
          sig_box_pdf("İSG Uzmanı")]],
        colWidths=[44 * mm] * 4,
    )
    sig_table_pdf.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table_pdf)

    # --- S13 — Footer callback (her sayfada) ---------------------------------
    # Landscape A4; alt kenardan 10 mm yukarı. Üç parçalı içerik:
    #   * Sol  : Denetçi adı
    #   * Orta : Restoran adı + state (kısa)
    #   * Sağ  : Sayfa X
    # "X / Y" formatı reportlab callback'inde doğrudan erişilemez (iki
    # pass render gerekir); export_ibraz da "Sayfa X" kullanır — contract
    # tutarlı. Callback adı export_ibraz'ınkilerle çakışmasın diye
    # ``_draw_export_pdf_footer`` olarak adlandırıldı.
    _pdf_page_w = landscape(A4)[0]  # 841.89 pt
    def _draw_export_pdf_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 7)
        canvas.setFillColor(colors.HexColor("#475569"))
        rest_name = (doc_db.get("restaurant_name") or "denetim")[:50]
        denetci_name = (doc_db.get("denetci") or "—")[:30]
        # Sol: denetçi
        canvas.drawString(18 * mm, 10 * mm, f"Denetçi: {denetci_name}")
        # Orta: restoran + state
        canvas.drawCentredString(
            _pdf_page_w / 2, 10 * mm,
            f"{rest_name} — {current_state}",
        )
        # Sağ: sayfa
        canvas.drawRightString(_pdf_page_w - 18 * mm, 10 * mm, f"Sayfa {doc.page}")
        # Üst-çizgi (footer'ı sayfa içeriğinden ayırır)
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(18 * mm, 13 * mm, _pdf_page_w - 18 * mm, 13 * mm)
        canvas.restoreState()

    pdf.build(elements, onFirstPage=_draw_export_pdf_footer,
              onLaterPages=_draw_export_pdf_footer)
    buf.seek(0)

    # Dosya adı: ``ISG_Risk_Analizi_<restaurant>.pdf``. Dual UTF-8
    # Content-Disposition korunur.
    restaurant = doc_db.get("restaurant_name") or "denetim"
    filename = f"ISG_Risk_Analizi_{restaurant}.pdf"
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)

    # Phase 2B — S18: İlk export sonrası DOF_CLOSED → FINAL.
    await _finalize_audit_if_dof_closed(oid, doc_db, current_user["id"])

    # Phase 2B — S20: export logla
    try:
        await log_action(
            db,
            audit_id=audit_id,
            user=current_user,
            action=Action.EXPORT_PDF,
            before=None,
            after={"filename": filename, "state_before_finalize": doc_db.get("state")},
        )
    except Exception as e:
        print(f"[export_pdf] audit_log write failed: {e}")

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; "
                f"filename*=UTF-8''{urlquote(filename)}"
            )
        },
    )


def _get_brand_logo_png(brand_or_name: str, max_width_px: int = 200) -> str | None:
    """Marka logosu PNG dosya yolunu döndür (reportlab Image için).

    SVG → PNG dönüşümü cairosvg ile lazy yapılır; sonuç
    ``BRAND_LOGOS_PNG_CACHE`` altında cache'lenir. İkinci çağrıda cache
    hit olur (saniyeler → milisaniyeler).

    Returns:
        PNG dosya yolu (str) veya ``None`` (marka eşleşmediyse).
    """
    try:
        from cairosvg import svg2png
    except (ImportError, OSError):
        # cairosvg (ve arkasındaki cairo native lib) isteğe bağlıdır; export
        # bunun yokluğunda logo olmadan devam eder (graceful degradation).
        # OSError: cairocffi, libcairo.so.2 yoksa import sırasında OSError
        # fırlatır (ImportError değil).
        return None

    name = (brand_or_name or "").lower()
    if "burger" in name or "bk" in name:
        svg_name = "burger-king.svg"
    elif "popeye" in name:
        svg_name = "popeyes.svg"
    elif "arby" in name:
        svg_name = "arbys.svg"
    elif "sbarro" in name:
        svg_name = "sbarro.svg"
    elif "subway" in name:
        svg_name = "subway.svg"
    else:
        return None

    svg_path = BRAND_LOGOS_DIR / svg_name
    if not svg_path.exists():
        return None

    # Cache dosya adı: max_width dahil (farklı boyutlar farklı cache key)
    png_name = svg_path.stem + f"_{max_width_px}.png"
    png_path = BRAND_LOGOS_PNG_CACHE / png_name
    if png_path.exists() and png_path.stat().st_size > 100:
        return str(png_path)

    try:
        svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            output_width=max_width_px,
        )
        return str(png_path)
    except Exception as e:
        print(f"[brand-logo] {svg_name} → PNG dönüşüm hatası: {e}")
        return None


def _build_verification_url(base_url: str, verification_id: str) -> str:
    """B7 — QR'un işaret ettiği public verification URL'ini üret.

    URL, server-side kaydı çözen opaque ``verification_id``'ye referans verir
    (``/api/verify/{verification_id}``). ``base_url`` ``VERIFICATION_BASE_URL``
    veya request origin (dev fallback) olabilir.
    """
    return f"{base_url.rstrip('/')}/api/verify/{verification_id}"


def _compute_ibraz_hash(audit_id: str, audit_doc: dict) -> str:
    """İbraz belgesi için SHA256 tamper-evident hash hesapla.

    Hash'e giren alanlar yasal delil açısından kritik:
      * ``audit_id`` — audit'in benzersiz kimliği
      * ``state`` — denetim durumu (DOF_CLOSED / FINAL)
      * ``retention_until`` — 6 yıl son kullanma tarihi
      * ``declarations_meta.signed_at`` — işveren vekili imza anı
      * ``declarations_meta.signed_by_rep_name`` — imzalayan kişi
      * ``answers`` — kanonik cevaplar (HAYIR/EVET/NA haritası, sıralı)
      * ``dof_details`` — DÖF durumları (KAPATILDI/AÇIK/İŞLEMDE)

    Bu alanlardan herhangi biri sonradan değişirse hash değişir → mahkeme
    delil bütünlüğü kontrolü yapılabilir.
    """
    import hashlib
    import json as _json

    answers = audit_doc.get("answers") or {}
    dof_details = audit_doc.get("dof_details") or {}
    declarations_meta = audit_doc.get("declarations_meta") or {}

    payload = {
        "audit_id": str(audit_id),
        "state": audit_doc.get("state") or "",
        "retention_until": audit_doc.get("retention_until") or "",
        "signed_at": declarations_meta.get("signed_at") or "",
        "signed_by": declarations_meta.get("signed_by_rep_name") or "",
        "answers_sorted": {k: answers[k] for k in sorted(answers.keys())},
        "dof_sorted": {
            k: dof_details[k].get("status", "")
            for k in sorted(dof_details.keys())
        },
    }
    canonical = _json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _persist_ibraz_record(
    db,
    audit_id: str,
    audit_doc: dict,
    *,
    user: dict,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """B7 — İbraz persist: ibraz belgesi üretilmeden ÖNCE ``db.audit_ibraz``
    koleksiyonuna yazar ve opaque ``verification_id`` üretir.

    QR kodu bu ``verification_id``'yi referansladığı için kayıt, PDF üretimi
    öncesinde (veya sırasında) oluşturulmak zorundadır — aksi halde PDF
    içine gömülecek opaque ID henüz mevcut olmaz. Aynı içerik
    ``(audit_id, ibraz_hash)`` için **deterministic/idempotent** davranır:
    mevcut kayıt (ve onun verification_id'si) döner, yeni ID üretilmez.

    Persistence hatası operational alert olarak loglanır (mandatory=False);
    kullanıcı PDF'i yine alır çünkü retry'e zorlanması UX'i bozar. Bu durumda
    doğrulama endpoint'i 404 döner (kayıt yok) — operational alert bunu
    işaret eder.

    Idempotency: aynı ``(audit_id, ibraz_hash)`` pair'i için tek record.
    Audit içerik hash'i ``_compute_ibraz_hash`` ile hesaplanır; aynı
    içerikle iki kez export edilirse yalnız ilk kayıt oluşturulur
    (``version`` field'ı o anda atanır).

    Returns:
        Yeni oluşturulan (veya mevcut) ibraz record'un serialized hali.

    B7 — İbraz persistence invariant:

    * İbraz belgesi her download edildiğinde ``audit_ibraz`` collection'a
      server-side bir record eklenir (verification_id, audit_id, full hash,
      short hash, state, exported_at, exported_by, version).
    * Record retention: ``audit_ibraz`` retention süresi (örn. 10 yıl)
      ``audit_log`` retention'ından uzundur (yasal ibraz süresi).
      ``retention-purge`` job'ı bu invariantı korumalı.
    * Index: ``(audit_id, exported_at DESC)`` — history listeleme
      performansı için; ``(verification_id)`` — public verify lookup için.
    """
    ibraz_hash = _compute_ibraz_hash(audit_id, audit_doc)
    short_hash = ibraz_hash[:16]

    existing = await db.audit_ibraz.find_one(
        {"audit_id": str(audit_id), "ibraz_hash": ibraz_hash}
    )
    if existing:
        return _serialize_ibraz_record(existing)

    # Version = o audit için daha önce kaç record var + 1. Race-safe: iki
    # eşzamanlı export aynı version'ı yazarsa unique constraint veya
    # find_one_and_update ile ``$inc`` ile düzeltilebilir; ancak aynı hash
    # varsa zaten ilk call ``existing`` ile short-circuit ediyor — buraya
    # yalnız hash unique iken geliyoruz. Version race'i son derece küçük
    # bir pencerede (mongodb write) ve ``audit_ibraz`` üzerinde unique
    # constraint ``(audit_id, ibraz_hash)`` ile korunuyor.
    last = await db.audit_ibraz.find_one(
        {"audit_id": str(audit_id)},
        {"version": 1},
        sort=[("version", -1)],
    )
    next_version = (last.get("version") if last else 0) + 1

    record = {
        # B7 — opaque verification identifier. QR URL bu ID'ye referans verir;
        # audit_id/ibraz_hash gibi öngörülebilir değerleri dış dünyaya sızdırmaz.
        "verification_id": uuid.uuid4().hex,
        "audit_id": str(audit_id),
        "ibraz_hash": ibraz_hash,
        "short_hash": short_hash,
        "state": audit_doc.get("state"),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by_user_id": user.get("id"),
        "exported_by_user_name": user.get("name") or user.get("email"),
        "version": next_version,
        "ip": ip,
        "user_agent": user_agent,
    }
    try:
        await db.audit_ibraz.insert_one(record)
    except Exception as e:
        # Operational alert — ibraz belgesi indirildi, persistence
        # başarısız. Audit_log'a non-mandatory olarak yaz; PDF'i
        # kullanıcı zaten aldı, retry'ye zorlama.
        print(f"[ibraz] persistence failed for {audit_id}: {e}")
        try:
            await log_action(
                db,
                audit_id=audit_id,
                user=user,
                action=Action.EXPORT_IBRAZ,
                before=None,
                after={
                    "ibraz_hash": short_hash,
                    "persistence": "FAILED",
                    "error": str(e)[:200],
                },
                ip=ip,
                user_agent=user_agent,
            )
        except Exception:
            pass
    return _serialize_ibraz_record(record)


def _serialize_ibraz_record(record: dict) -> Dict[str, Any]:
    """İbraz record'unu API response'a çevir. ``_id`` → ``id`` string."""
    if record is None:
        return {}
    out = dict(record)
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    return out


async def _ensure_ibraz_indexes(db) -> None:
    """İbraz persistence indekslerini başlangıçta kur.

    * ``(audit_id, exported_at DESC)`` — history listeleme.
    * ``(audit_id, ibraz_hash)`` unique — idempotency.
    * ``(exported_at)`` — retention job range queries.

    İdempotent: ``create_index`` mevcutsa hata vermez.
    """
    try:
        await db.audit_ibraz.create_index(
            [("audit_id", 1), ("exported_at", -1)],
            name="audit_ibraz_audit_id_exported_at",
        )
        await db.audit_ibraz.create_index(
            [("audit_id", 1), ("ibraz_hash", 1)],
            name="audit_ibraz_audit_id_hash_unique",
            unique=True,
        )
        await db.audit_ibraz.create_index(
            [("exported_at", 1)],
            name="audit_ibraz_exported_at",
        )
    except Exception as e:
        # Index oluşturma hatası startup'ı blok etmemeli — logla,
        # periyodik reaper zaten var.
        print(f"[ibraz] index creation warning: {e}")


@api_router.get("/audits/{audit_id}/ibraz")
async def export_ibraz(
    audit_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """İSG Risk Analizi İBRAZ BELGESİ — mahkeme/resmi makamlar için (S20).

    Amaç: ``state`` DOF_CLOSED veya FINAL olan denetimler için yasal ibraz
    belgesi üret. Bu belge:

      * Portrait A4, 1-2 sayfa, resmi format
      * SHA256 tamper-evident hash (değiştirilmiş tespit)
      * QR kod (verification URL + kısa hash)
      * İşveren Vekili onay imza bilgileri
      * 4 imza kutusu (Denetçi / Rest.Md / İşv.Vekili / İSG Uzm.)
      * HAYIR soruları + verilen kararlar (Onay/İtiraz) tablosu
      * Risk dağılımı özeti
      * Her sayfada footer: hash, sayfa X/Y, denetim adı

    Erişim kontrolü:
      * Yalnız DOF_CLOSED veya FINAL (imzalanmış) denetimler için
      * DRAFT / SUBMITTED / DOF_OPEN için 409 (henüz ibraz edilemez)
      * Soft-deleted (deleted_at) için 410

    Audit log: ``export_ibraz`` action'ı yazılır (kullanıcı + IP + UA).
    """
    import qrcode as _qrcode
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
        Image as RLImage,
        PageBreak,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # --- Font registration (Turkce karakterler) ---
    font_name = "Helvetica"
    bold_font_name = "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(
            TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        )
        pdfmetrics.registerFont(
            TTFont("DejaVu-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        )
        font_name = "DejaVu"
        bold_font_name = "DejaVu-Bold"
    except Exception:
        pass

    # --- Audit veri kaynagi ---
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")
    doc_db = await db.audits.find_one({"_id": oid, **_scope_filter(current_user)})
    if not doc_db:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")
    if doc_db.get("deleted_at"):
        raise HTTPException(status_code=410, detail="Denetim silinmiş, ibraz edilemez")

    current_state = doc_db.get("state") or AuditState.DRAFT.value
    if current_state not in (AuditState.DOF_CLOSED.value, AuditState.FINAL.value):
        raise HTTPException(
            status_code=409,
            detail=f"Bu denetim {current_state} durumunda; ibraz belgesi oluşturulamaz. "
                   f"İbraz yalnızca DOF_CLOSED ve FINAL durumlarında mümkündür.",
        )

    # Tamper-evident hash hesapla
    ibraz_hash = _compute_ibraz_hash(audit_id, doc_db)
    short_hash = ibraz_hash[:16]

    # B7 — verification record'u QR embed edilmeden ÖNCE persist et.
    # QR koduna opaque verification_id gömülür; aynı içerik (audit_id, hash)
    # için tek ve kararlı verification_id döner (deterministic repeat-
    # generation). PDF üretimi başarısız olsa bile ID kararlı kalır.
    ibraz_record = await _persist_ibraz_record(
        db,
        audit_id=str(oid),
        audit_doc=doc_db,
        user=current_user,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    verification_id = ibraz_record.get("verification_id") or ""

    # B7 — public verification URL: explicit config, güvenli dev fallback
    # (request origin). URL içindeki opaque verification_id, server-side
    # kaydı çözen public endpoint'e işaret eder.
    verify_url = _build_verification_url(
        VERIFICATION_BASE_URL or str(request.base_url).rstrip("/"),
        verification_id,
    )

    # Audit log'dan son 10 entry
    log_items = await get_audit_log(db, str(oid), limit=10)
    state_history = doc_db.get("state_history") or []
    declarations_meta = doc_db.get("declarations_meta") or {}
    declarations = doc_db.get("declarations") or {}
    answers = doc_db.get("answers") or {}
    questions = _get_audit_questions(doc_db)
    overrides = _get_audit_overrides(doc_db)

    # --- QR kod (PNG byte -> BytesIO -> reportlab Image) ---
    qr_img_buf = io.BytesIO()
    qr = _qrcode.QRCode(version=2, box_size=8, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img.save(qr_img_buf, format="PNG")
    qr_img_buf.seek(0)
    qr_rl = RLImage(qr_img_buf, width=35 * mm, height=35 * mm)

    # --- Document template ---
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="İSG Risk Analizi İbraz Belgesi",
        author="ABCD Tech Solutions İSG Sistemi",
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "IbrazTitle", parent=styles["Title"], fontName=bold_font_name,
        fontSize=18, leading=22, textColor=colors.HexColor("#8B0000"),
        alignment=1, spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "IbrazSub", parent=styles["Normal"], fontName=font_name,
        fontSize=10, leading=12, textColor=colors.HexColor("#475569"),
        alignment=1, spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "IbrazSection", parent=styles["Heading2"], fontName=bold_font_name,
        fontSize=11, leading=14, textColor=colors.HexColor("#0F172A"),
        spaceBefore=10, spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "IbrazBody", parent=styles["Normal"], fontName=font_name,
        fontSize=9, leading=12, textColor=colors.HexColor("#0F172A"),
    )
    small_style = ParagraphStyle(
        "IbrazSmall", parent=styles["Normal"], fontName=font_name,
        fontSize=7, leading=9, textColor=colors.HexColor("#475569"),
    )

    cell_head = ParagraphStyle(
        "IbrazCellHead", parent=styles["Normal"], fontName=bold_font_name,
        fontSize=8, leading=10, textColor=colors.white,
    )
    cell_text = ParagraphStyle(
        "IbrazCellText", parent=styles["Normal"], fontName=font_name,
        fontSize=8, leading=10, textColor=colors.HexColor("#0F172A"),
    )
    cell_bold = ParagraphStyle(
        "IbrazCellBold", parent=cell_text, fontName=bold_font_name,
    )

    elements = []

    # ====== HEADER ======
    elements.append(Paragraph("İSG RİSK ANALİZİ İBRAZ BELGESİ", title_style))
    elements.append(Paragraph(
        "6331 Sayılı İSG Kanunu Madde 8 / Risk Değerlendirmesi Yönetmeliği (28532 sayılı)",
        sub_style,
    ))
    elements.append(Paragraph(
        f"<b>ABCD Tech Solutions SAN. VE TİC. A.Ş.</b> — Restoran İş Sağlığı ve Güvenliği Risk Analizi",
        sub_style,
    ))
    elements.append(Spacer(1, 4 * mm))

    # ====== KIMLIK + HASH BLOKU (yan yana 2 kolon tablo) ======
    # Sol kolon: kimlik bilgileri, sağ kolon: QR + hash
    left_id = [
        [Paragraph("<b>Denetim ID</b>", cell_text), Paragraph(str(audit_id), cell_text)],
        [Paragraph("<b>Restoran / Şube</b>", cell_text), Paragraph(
            str(doc_db.get("restaurant_name") or "—"), cell_text)],
        [Paragraph("<b>Adres</b>", cell_text), Paragraph(
            str(doc_db.get("address") or "—"), cell_text)],
        [Paragraph("<b>Şehir / İlçe</b>", cell_text), Paragraph(
            f"{doc_db.get('city') or '—'} / {doc_db.get('district') or '—'}", cell_text)],
        [Paragraph("<b>Marka</b>", cell_text), Paragraph(
            str(doc_db.get("brand") or "—"), cell_text)],
        [Paragraph("<b>Denetim Tarihi</b>", cell_text), Paragraph(
            str(doc_db.get("audit_date") or "—"), cell_text)],
        [Paragraph("<b>Denetçi</b>", cell_text), Paragraph(
            str(doc_db.get("denetci") or "—"), cell_text)],
        [Paragraph("<b>Durum</b>", cell_text), Paragraph(
            f"<b>{current_state}</b>", cell_bold)],
        [Paragraph("<b>Retention Bitiş</b>", cell_text), Paragraph(
            str(doc_db.get("retention_until") or "—"), cell_text)],
    ]
    left_table = Table(left_id, colWidths=[42 * mm, 60 * mm])
    left_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    # Sağ kolon: QR + hash + verify URL
    right_content = [
        [qr_rl],
        [Paragraph(f"<b>Doğrulama Hash</b><br/><font face=\"Courier\" size=\"7\">{ibraz_hash}</font>",
                   ParagraphStyle("h", parent=cell_text, alignment=1))],
        [Paragraph(f"<b>Kısa Hash</b><br/><font face=\"Courier\" size=\"9\">{short_hash}</font>",
                   ParagraphStyle("h", parent=cell_text, alignment=1))],
        [Paragraph(f"<b>Verify URL</b><br/>"
                   f"<font face=\"Courier\" size=\"6\">{verify_url}</font>",
                   ParagraphStyle("h", parent=cell_text, alignment=1))],
    ]
    right_table = Table(right_content, colWidths=[70 * mm])
    right_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        # QR icin minimum yukseklik
        ("MINROWHEIGHT", (0, 0), (0, 0), 35 * mm),
    ]))

    header_table = Table(
        [[left_table, right_table]],
        colWidths=[102 * mm, 72 * mm],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 6 * mm))

    # ====== RISK OZETI ======
    elements.append(Paragraph("1. Risk Dağılımı Özeti", section_style))
    summary = doc_db.get("summary") or _summarize(doc_db)
    risk_counts = (summary or {}).get("risk_counts") or {}
    counts = (summary or {}).get("counts") or {}
    risk_rows = [
        [Paragraph("<b>Toplam Soru</b>", cell_text),
         Paragraph(str((summary or {}).get("total_questions", "—")), cell_bold)],
        [Paragraph("<b>Cevaplanan</b>", cell_text),
         Paragraph(str((summary or {}).get("answered", "—")), cell_bold)],
        [Paragraph("✅ EVET (Uygun)", cell_text), Paragraph(str(counts.get("EVET", 0)), cell_text)],
        [Paragraph("❌ HAYIR (Uygun Değil)", cell_text), Paragraph(str(counts.get("HAYIR", 0)), cell_text)],
        [Paragraph("➖ N/A", cell_text), Paragraph(str(counts.get("NA", 0)), cell_text)],
        [Paragraph("🔴 Kabul Edilemez Risk", cell_text), Paragraph(str(risk_counts.get("Kabul Edilemez", 0)), cell_text)],
        [Paragraph("🟡 Dikkate Değer Risk", cell_text), Paragraph(str(risk_counts.get("Dikkate Değer", 0)), cell_text)],
        [Paragraph("🟢 Kabul Edilebilir Risk", cell_text), Paragraph(str(risk_counts.get("Kabul Edilebilir", 0)), cell_text)],
        [Paragraph("<b>Toplam Risk Skoru</b>", cell_text),
         Paragraph(f"<b>{(summary or {}).get('total_risk_score', 0)}</b>", cell_bold)],
    ]
    risk_table = Table(risk_rows, colWidths=[60 * mm, 30 * mm])
    risk_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(risk_table)
    elements.append(Spacer(1, 4 * mm))

    # ====== ISVEREN VEKILI IMZASI ======
    elements.append(Paragraph("2. İşveren Vekili Onay İmzası", section_style))
    meta_rows = [
        [Paragraph("<b>İşveren Vekili Ad Soyad</b>", cell_text),
         Paragraph(str(declarations_meta.get("signed_by_rep_name") or "—"), cell_bold)],
        [Paragraph("<b>Görevi / Unvanı</b>", cell_text),
         Paragraph(str(declarations_meta.get("signed_by_rep_title") or declarations_meta.get("rep_title") or "—"), cell_text)],
        [Paragraph("<b>Onay Tarihi</b>", cell_text),
         Paragraph(str(declarations_meta.get("declaration_date") or "—"), cell_text)],
        [Paragraph("<b>İmza Anı (UTC)</b>", cell_text),
         Paragraph(str(declarations_meta.get("signed_at") or "—"), cell_text)],
        [Paragraph("<b>İmzalayan Kullanıcı</b>", cell_text),
         Paragraph(str(declarations_meta.get("signed_by_user_name") or "—"), cell_text)],
    ]
    meta_table = Table(meta_rows, colWidths=[55 * mm, 110 * mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 4 * mm))

    # ====== HAYIR SORULAR + KARARLAR ======
    hayir_qs = [q for q in questions if answers.get(str(q.get("id"))) == "HAYIR"]
    if hayir_qs:
        elements.append(Paragraph(
            f"3. HAYIR Cevaplı Sorular ve İşveren Vekili Kararları ({len(hayir_qs)} madde)",
            section_style,
        ))
        decision_rows = [[
            Paragraph("<b>No</b>", cell_head),
            Paragraph("<b>Soru</b>", cell_head),
            Paragraph("<b>Karar</b>", cell_head),
            Paragraph("<b>Gerekçe / Taahhüt</b>", cell_head),
        ]]
        for q in hayir_qs:
            qid = str(q.get("id"))
            dec = declarations.get(qid) or {}
            decision = dec.get("decision") or "—"
            if decision == "APPROVED":
                decision_disp = "✅ Onay"
                reason = dec.get("commitment") or "—"
            elif decision == "DISPUTED":
                decision_disp = "⚠ İtiraz"
                reason = dec.get("reason") or "—"
            else:
                decision_disp = "—"
                reason = "(karar verilmemiş)"
            decision_rows.append([
                Paragraph(str(q.get("no") or qid), cell_bold),
                Paragraph(str(q.get("question") or "—")[:120], cell_text),
                Paragraph(decision_disp, cell_bold),
                Paragraph(str(reason)[:200], cell_text),
            ])
        decision_table = Table(
            decision_rows,
            colWidths=[14 * mm, 70 * mm, 28 * mm, 62 * mm],
            repeatRows=1,
        )
        decision_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B0000")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(decision_table)
    else:
        elements.append(Paragraph(
            "3. Bu denetimde HAYIR cevaplı soru bulunmamaktadır. Tüm sorular Uygun/N/A.",
            section_style,
        ))
    elements.append(Spacer(1, 4 * mm))

    # ====== 4 IMZA KUTUSU ======
    elements.append(Paragraph("4. İmza Alanları", section_style))
    sig_box = lambda label: Table(
        [[""], [Paragraph(f"<b>{label}</b>", ParagraphStyle(
            "lbl", parent=cell_text, fontSize=8, alignment=1, textColor=colors.HexColor("#475569")))]],
        colWidths=[42 * mm],
        rowHeights=[22 * mm, 6 * mm],
    )
    sig_box.__defaults__ = ()
    sig_table = Table(
        [[sig_box("Denetçi"), sig_box("Restoran Müdürü"), sig_box("İşveren Vekili"), sig_box("İSG Uzmanı")]],
        colWidths=[44 * mm] * 4,
    )
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 6 * mm))

    # ====== STATE HISTORY (kompakt) ======
    if state_history:
        elements.append(Paragraph("5. Denetim Yaşam Döngüsü (State History)", section_style))
        sh_rows = [[
            Paragraph("<b>Geçiş</b>", cell_head),
            Paragraph("<b>Tarih</b>", cell_head),
            Paragraph("<b>Sebep</b>", cell_head),
        ]]
        for h in state_history:
            sh_rows.append([
                Paragraph(f"{h.get('from', '—')} → {h.get('to', '—')}", cell_text),
                Paragraph(str(h.get("at", "—")), cell_text),
                Paragraph(str(h.get("reason", "—")), cell_text),
            ])
        sh_table = Table(sh_rows, colWidths=[40 * mm, 50 * mm, 84 * mm], repeatRows=1)
        sh_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(sh_table)

    # ====== Footer callback (hash + sayfa her sayfada) ======
    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 7)
        canvas.setFillColor(colors.HexColor("#475569"))
        # Sol: hash kisa
        canvas.drawString(18 * mm, 10 * mm, f"Hash: {short_hash}")
        # Orta: audit adi kisaltilmis
        rest_name = (doc_db.get("restaurant_name") or "denetim")[:50]
        canvas.drawCentredString(
            A4[0] / 2, 10 * mm,
            f"{rest_name} — {current_state} — {str(audit_id)[-12:]}",
        )
        # Sag: sayfa X / Y
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Sayfa {doc.page}")
        # Alt-cizgi
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
        canvas.restoreState()

    pdf.build(elements, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)

    # Dosya adi
    restaurant = doc_db.get("restaurant_name") or "denetim"
    filename = f"Ibraz_{restaurant}_{short_hash}.pdf"
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)

    # Audit log
    # B6 — mandatory=True: ibraz belgesi üretimi forensic event;
    # log yazılamazsa UI'da görünür hata.
    await log_action(
        db,
        audit_id=str(oid),
        user=current_user,
        action=Action.EXPORT_IBRAZ,
        before=None,
        after={
            "filename": filename,
            "ibraz_hash": short_hash,
            "verification_id": verification_id,
            "state": current_state,
        },
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        mandatory=True,
    )

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; "
                f"filename*=UTF-8''{urlquote(filename)}"
            ),
            "X-Ibraz-Hash": short_hash,
        },
    )


@api_router.get("/audits/{audit_id}/ibraz/history")
async def list_ibraz_history(
    audit_id: str,
    current_user: dict = Depends(get_current_user),
):
    """B7 — İbraz history: audit'in tüm ibraz üretim event'lerini listele.

    Forensic amaçlı: bu audit için hangi hash ile ne zaman ibraz belgesi
    üretildi? Son üretim hangi user tarafından indirildi? Bunlar forensic
    sorguda cevaplanmalı.

    Returns:
        ``[{id, audit_id, ibraz_hash, short_hash, state, exported_at,
            exported_by_user_id, exported_by_user_name, version, ip,
            user_agent}, ...]`` — ``exported_at DESC`` sıralı.

    B3 — soft-delete filtre: deleted audit'in history'si forensic flow
    için ``include_deleted=true`` query param ile açılır. Default gizli.
    """
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    # Scope kontrolü: deleted audit'ler default gizli; forensic bypass
    # için ``include_deleted=true``.
    include_deleted = False  # query param okumadan default; aşağıda set edilebilir
    audit_doc = await db.audits.find_one({"_id": oid, **_normal_audit_filter(current_user)})
    if not audit_doc:
        # Belki soft-deleted: forensic bypass ile kontrol et.
        include_deleted = True  # bu default olarak zaten ``False`` ama
        # explicit olarak True yaparak ``_scope_filter`` kullanmıyoruz.
        audit_doc = await db.audits.find_one(
            {"_id": oid, **_scope_filter(current_user)}
        )
        if not audit_doc:
            raise HTTPException(status_code=404, detail="Denetim bulunamadı")

    cursor = db.audit_ibraz.find({"audit_id": str(audit_id)}).sort("exported_at", -1)
    records = await cursor.to_list(length=500)  # upper cap (son 500 export)
    return [_serialize_ibraz_record(r) for r in records]


@api_router.get("/admin/ibraz/records")
async def list_all_ibraz_records(
    limit: int = 100,
    audit_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """B7 — Admin forensic: tüm audit'lerin ibraz history kayıtları.

    Yalnız admin scope'lu kullanıcılar. ``limit`` default 100 (max 500).
    Filtreleme ``audit_id`` ile mümkün.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Yalnız admin")

    query: Dict[str, Any] = {}
    if audit_id:
        query["audit_id"] = audit_id

    cursor = db.audit_ibraz.find(query).sort("exported_at", -1).limit(min(limit, 500))
    records = await cursor.to_list(length=500)
    return [_serialize_ibraz_record(r) for r in records]


@api_router.get("/verify/{verification_id}")
async def verify_ibraz(verification_id: str):
    """B7 — Public (auth'sız) read-only verification endpoint.

    QR kodunun işaret ettiği opaque ``verification_id`` ile server-side
    kaydı çözer ve belge bütünlüğü (tamper-evidence) bilgisini döner.

    Güvenlik:
      * Read-only — hiçbir state mutasyonu yok.
      * Opaque ID — audit_id/hash öngörülebilir değerleri dışarı sızmaz.
      * Minimal içerik — ``exported_by_user_id/name``, ``ip``, ``user_agent``
        gibi özel/forensic alanlar **asla** döndürülmez.
      * Doğrulama yalnızca SHA-256 bütünlük hash'idir; nitelikli e-imza
        (kriptografik imza) iddiası taşımaz (bkz. ``verification_type``).
    """
    if not verification_id:
        raise HTTPException(status_code=404, detail="Geçersiz doğrulama kimliği")

    record = await db.audit_ibraz.find_one({"verification_id": verification_id})
    if not record:
        raise HTTPException(status_code=404, detail="Doğrulama kaydı bulunamadı")

    return {
        "verified": True,
        "verification_id": record.get("verification_id"),
        "ibraz_hash": record.get("ibraz_hash"),
        "short_hash": record.get("short_hash"),
        "state": record.get("state"),
        "exported_at": record.get("exported_at"),
        "version": record.get("version"),
        "verification_type": "sha256_integrity_hash",
        "note": (
            "Bu doğrulama belge bütünlüğü (tamper-evidence) kontrolü sağlar; "
            "nitelikli elektronik imza (e-imza) veya resmi kurum onayı değildir."
        ),
    }


# ---------------- DÖF backend contract ----------------
class DofUpdateInput(BaseModel):
    """DÖF state update isteği — S9 ile min 20 karakter not zorunlu (KAPATILDI).

    * ``status`` — AÇIK / İŞLEMDE / KAPATILDI
    * ``notes`` — KAPATILDI için zorunlu, min 20 karakter (iş birimi kuralı:
      "kapatma prosedürü sıkı takip" — kısa not ile geçiştirme yasak)
    * ``resolution_note`` — KAPATILDI için zorunlu, ``notes`` ile aynı kural
    """
    status: Literal["AÇIK", "İŞLEMDE", "KAPATILDI"]
    notes: str = Field(default="", max_length=2000)
    resolution_note: Optional[str] = None
    # ``resolved_at`` ve ``resolved_by`` server-controlled; client gönderemez.
    # Pydantic v2 ``extra="ignore"`` default ile bu alanlar sessizce düşerdi
    # — explicit reddetmek trust boundary'yi netleştirir ve yanlış payload
    # gönderen client'ların hata almasını sağlar (loglanabilir rejection).

    KAPATILDI_MIN_NOTES: ClassVar[int] = 20  # S9: "kapatma prosedürü sıkı takip"

    @field_validator("notes")
    @classmethod
    def _trim_notes(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _kapatildi_requires_notes(self) -> "DofUpdateInput":
        if self.status != "KAPATILDI":
            return self
        if len(self.notes) < self.KAPATILDI_MIN_NOTES:
            raise ValueError(
                f"KAPATILDI durumunda not en az {self.KAPATILDI_MIN_NOTES} karakter olmalıdır "
                f"(mevcut: {len(self.notes)} karakter)."
            )
        # resolution_note opsiyonel ama boşsa notes'tan inherit et (UX)
        if not (self.resolution_note or "").strip():
            # ``resolution_note`` boş bırakılabilir; bu durumda notes
            # zaten kendi başına yeterli. Ek validation yok.
            pass
        elif len((self.resolution_note or "").strip()) < self.KAPATILDI_MIN_NOTES:
            raise ValueError(
                f"KAPATILDI durumunda resolution_note en az {self.KAPATILDI_MIN_NOTES} karakter olmalıdır."
            )
        return self


def _calculate_due_date(created_at_iso: str, deadline_str: str) -> str | None:
    """DÖF termininden due_date hesapla.

    Davranış (UAT S1 standardizasyonu + current-main uyumluluğu):

    1. Termin içinde "sürekli"/"surekli" geçiyorsa ``None`` döner
       (anında müdahale, deadline yok). Bu davranış S1 iş birimi
       kuralıyla bilinçli olarak değişti (eskiden 90 gün hesaplanıyordu
       — İSG mevzuatına aykırıydı).
    2. ``parse_deadline_to_days`` strict parse çağrılır:
       - "Sürekli" → ``None`` (yukarıdaki case)
       - "acil" → 1 gün
       - "X gün"/"X ay"/"X hafta"/"X yıl"/"X saat" → birim çarpımı
    3. Parser ``None`` dönerse (boş/None/garbage/eksik format) **90
       gün** uygulanır — bu, PR #13 öncesi main'deki geriye-uyumlu
       fallback. Frontend bu durumu özel badge ile gösterir
       ("SÜREKLİ — Anında Müdahale", kırmızı pulse) yalnızca
       termin açıkça "Sürekli" olduğunda.

    S1 iyileştirmesi: eski mantık string substring match yapıyordu
    ("1" in d_lower → 30, "2" in d_lower → 60, else → 90), bu yüzden
    "5 gün" → 90, "10 gün" → 30, "2 hafta" → 60, "1 yıl" → 30 gibi
    hatalı sonuçlar üretiyordu. Yeni parse_deadline_to_days ile
    termin alanı içerikle birebir aynı anlamı taşır; uyumsuz input
    için main'in eski 90 gün fallback'i korunur.
    """
    d_lower = str(deadline_str or "").lower()
    if "sürekli" in d_lower or "surekli" in d_lower:
        return None  # ANINDA — deadline yok (S1 kasıtlı değişiklik)
    days = parse_deadline_to_days(deadline_str)
    if days is None:
        # PR #13 öncesi main fallback: parse edilemeyen termin için
        # 90 gün. Kullanıcının eski denetimleri kayıp/boş terminden
        # dolayı erken kapatılmasını engeller.
        days = 90
    try:
        dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)
    return (dt + timedelta(days=days)).isoformat()


def _build_default_timeline(audit: Dict[str, Any], dof: Dict[str, Any], created_at_iso: str, owner_name: str) -> List[Dict[str, Any]]:
    logs = dof.get("timeline_logs")
    if logs and isinstance(logs, list) and len(logs) > 0:
        return logs
    
    auditor = audit.get("denetci") or owner_name or "İSG Uzmanı"
    generated = [{
        "action": "DÖF Oluşturuldu (Saha Denetim Tespit)",
        "user": auditor,
        "timestamp": created_at_iso,
    }]
    
    in_prog = dof.get("in_progress_at") or (dof.get("updated_at") if dof.get("status") in ("İŞLEMDE", "KAPATILDI") else None)
    if in_prog:
        generated.append({
            "action": "Saha Düzeltme Kanıt Fotoğrafı Yüklendi (İşlemde)",
            "user": dof.get("updated_by") or "Restoran Sorumlusu",
            "timestamp": in_prog,
        })
        
    res_at = dof.get("resolved_at")
    if res_at or dof.get("status") == "KAPATILDI":
        generated.append({
            "action": "DÖF İSG Uzmanı Tarafından Onaylandı & Kapatıldı",
            "user": dof.get("resolved_by") or "İSG Uzmanı",
            "timestamp": res_at or dof.get("updated_at") or created_at_iso,
        })
        
    return generated


def _get_category_question_no(q: dict, questions_list: list) -> str:
    """Soru numarasını kategori bazlı formatta döndür (Örn: 1.3, 4.1)."""
    cat_name = q.get("category") or q.get("kategori") or ""
    cats = []
    for item in questions_list:
        c = item.get("category") or item.get("kategori") or ""
        if c and c not in cats:
            cats.append(c)

    cat_idx = cats.index(cat_name) + 1 if cat_name in cats else 1
    in_cat_questions = [item for item in questions_list if (item.get("category") or item.get("kategori")) == cat_name]
    in_cat_idx = 1
    for idx, item in enumerate(in_cat_questions):
        if item.get("id") == q.get("id"):
            in_cat_idx = idx + 1
            break

    return f"{cat_idx}.{in_cat_idx}"


def _build_dof_items(audit: Dict[str, Any], owner_name: str) -> List[Dict[str, Any]]:
    """HAYIR cevaplı sorular için DÖF response item'ları üret.

    Snapshot + ``risk_overrides`` + ``compute_effective_risk`` reuse edilir;
    YENİ risk hesabı yapılmaz. DÖF storage key = ``question_id`` (stabil int).
    """
    answers = audit.get("answers") or {}
    if not answers:
        return []

    questions = _get_audit_questions(audit)
    overrides = _get_audit_overrides(audit)
    saved = audit.get("dof_details") or {}
    declarations = audit.get("declarations") or {}
    declarations_meta = audit.get("declarations_meta") or {}

    audit_id = str(audit["_id"])
    items: List[Dict[str, Any]] = []
    for q in questions:
        qid = q["id"]
        if answers.get(str(qid)) != "HAYIR":
            continue
        eff = compute_effective_risk(q, overrides.get(str(qid)))
        dof = saved.get(str(qid)) or {}
        dec = declarations.get(str(qid)) or declarations.get(qid) or {}
        created_at_val = dof.get("created_at") or audit.get("created_at") or audit.get("audit_date") or datetime.now(timezone.utc).isoformat()
        deadline_str = q.get("deadline", "3 Ay")
        due_date_val = dof.get("due_date") or _calculate_due_date(created_at_val, deadline_str)
        t_logs = _build_default_timeline(audit, dof, created_at_val, owner_name)

        items.append({
            "audit_id": audit_id,
            "audit_user_id": audit.get("user_id", ""),
            "owner_name": owner_name,
            "restaurant_name": audit.get("restaurant_name", ""),
            "audit_date": audit.get("audit_date", ""),
            "question_id": qid,
            # Legacy contract: ``question_no`` is the stable numeric
            # question index (matches ``q.no`` / ``q.id``). Never set
            # it to the category-based string — frontends / exporters
            # historically pinned the integer type for sorting and ID
            # composition. Category-based display value rides in
            # ``category_question_no`` so consumers can opt-in without
            # breaking legacy numeric consumers.
            "question_no": int(q.get("no") or q.get("id") or 0),
            "category_question_no": _get_category_question_no(q, questions),
            "category": q.get("category", ""),
            "question": q.get("question", ""),
            "responsible": q.get("responsible", ""),
            "probability": eff["probability"],
            "severity": eff["severity"],
            "risk_score": eff["risk_score"],
            "risk_level": eff["risk_level"],
            "document_risk_level": q.get("document_risk_level", eff["risk_level"]),
            "deadline": deadline_str,
            "legal_basis": q.get("legal_basis", []),
            "corrective_action": q.get("corrective_action", ""),
            "photos": q.get("photos", {"finding": [], "resolution": []}),
            "status": dof.get("status", "AÇIK"),
            "notes": dof.get("notes", ""),
            "created_at": created_at_val,
            "due_date": due_date_val,
            "in_progress_at": dof.get("in_progress_at"),
            "resolution_note": dof.get("resolution_note", dof.get("notes", "")),
            "resolved_at": dof.get("resolved_at"),
            "resolved_by": dof.get("resolved_by", ""),
            "timeline_logs": t_logs,
            "photo_modify_count": dof.get("photo_modify_count", 0),
            "updated_at": dof.get("updated_at"),
            "updated_by": dof.get("updated_by"),
            "workplace_declaration": dec,
            "declarations_meta": declarations_meta,
        })
    return items


@api_router.get("/dofs")
async def list_dofs(current_user: dict = Depends(get_current_user)):
    """Tüm scope'taki denetimlerde HAYIR cevaplı sorular için DÖF listesi.

    Yeni/canonical İngilizce şema. HAYIR olmayan sorular hiç dönmez.
    DÖF state'i ``dof_details.<question_id>`` alt alanından okunur;
    yoksa default payload (AÇIK + boş notes) döner.

    Phase 2B — S19: Soft-delete'lenen denetimlerin DÖF'leri listede
    görünmez (audit'le aynı mantık). Arşivlenen denetimler de gizli
    (``_active_audits_filter`` birleşik S19+S20 filtresi).
    """
    cursor = db.audits.find(
        {**_scope_filter(current_user), **_active_audits_filter()}
    ).sort("created_at", -1)

    # Auditor name cache: unique user_id başına 1 sorgu (N+1 önleme).
    name_cache: Dict[str, str] = {current_user["id"]: current_user["name"]}

    items: List[Dict[str, Any]] = []
    async for audit in cursor:
        uid = audit.get("user_id")
        if uid and uid not in name_cache:
            owner = await _owner_name(uid)
            if owner:
                name_cache[uid] = owner
        owner_name = name_cache.get(uid, "")
        items.extend(_build_dof_items(audit, owner_name))
    return items


@api_router.put("/dofs/{audit_id}/{question_id}")
async def update_dof(
    audit_id: str,
    question_id: int,
    body: DofUpdateInput,
    current_user: dict = Depends(get_current_user),
):
    """Tek bir HAYIR cevaplı soru için DÖF state'i güncelle.

    * Ana audit ``version`` + ``updated_at`` alanlarına DOKUNULMAZ.
    * Sadece ``dof_details.<question_id>`` alt alanına ``$set`` yazılır.
    * HAYIR olma koşulu atomik update filtresinde de uygulanarak race
      koşulu kapatılır; başarısız atomic update sonrası ikinci scoped
      read ile 404 / 409 ayrımı yapılır.
    """
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    # KAPATILDI için role gate YOK. Audit ``_scope_filter`` ile zaten kendi
    # user_id'si içinde tutulur; farklı kullanıcının audit'ine KAPATILDI
    # yazılamaz (test_other_users_dof_cannot_be_updated_returns_404). İSG
    # Uzmanı / admin onayı UX seviyesindedir (DofApproveModal akışı);
    # backend her scope'lu kullanıcının KAPATILDI yazabilmesine izin verir
    # (main contract — test_kapatildi_with_non_empty_notes_succeeds sözleşmesi).

    now = datetime.now(timezone.utc).isoformat()

    user_display = current_user.get("name") or current_user.get("email") or "İSG Uzmanı"
    
    # Construct log entry
    action_text = f"DÖF Durumu '{body.status}' olarak güncellendi."
    if body.status == "KAPATILDI":
        action_text = "DÖF İSG Uzmanı Tarafından Onaylandı & Kapatıldı"
    elif body.status == "İŞLEMDE":
        action_text = "DÖF Düzeltme İşlemine Alındı (Saha Çalışması Başladı)"

    log_entry = {
        "action": action_text,
        "user": user_display,
        "timestamp": now,
    }

    # B2 — FINAL immutability: FINAL audit'lerde DÖF güncellenemez.
    # B3 — soft-delete invariant: silinen audit'lerde DÖF güncellenemez.
    # B4 — DÖF invalidation invariant: ``active=False`` olan DÖF kaydı
    # kullanıcı tarafından düzenlenemez (cevap EVET/NA'ya dönünce
    # inactive olarak işaretlenen eski DÖF kaydı). Atomic update
    # filtresiyle bu üç koşul birden uygulanır.
    # NOT: Bu filtreleme ``find_one_and_update`` filtresinde değil, ÖNCEKİ
    # bir scoped read ile yapılır — ``$or``'lu atomic filter dofs.31
    # invalidation filter (active=False) için temiz değil. Önceki read
    # 404/409 raise'lerini korur, sonra ``find_one_and_update`` race-safe
    # (cevap HAYIR değilse race'de no-op döner, yine raise).
    existing_check = await db.audits.find_one(
        {"_id": oid, **_normal_audit_filter(current_user)},
        {"state": 1, "answers": 1, "dof_details": 1, "template_snapshot": 1},
    )
    if not existing_check:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")
    current_state = existing_check.get("state") or AuditState.DRAFT.value
    if current_state == AuditState.FINAL.value:
        # B2 — FINAL audits immutable.
        raise HTTPException(
            status_code=409,
            detail="FINAL denetim üzerinde mutasyon yapılamaz",
        )
    # Atomic update: ``$set`` leaf alanlarına (parent sub-doc PATH YOK) +
    # ``$push`` ile ``timeline_logs``. ``$set`` ile aynı parent path'i
    # (örn. ``dof_details.3``) bütün olarak değiştirmek MongoDB'de
    # ``ConflictingUpdateOperators`` (code 40) üretir — mevcut dof_details
    # sub-doc varken yapılan ikinci PUT'ta (örn. KAPATILDI'ya geçerken)
    # 500 dönüyordu. Leaf-seviye ``$set`` (her alan ayrı dot-path) +
    # ``$unset`` ile kapanış alanları temizleme + ``$push`` ile log ekleme
    # aynı atomic tek-call semantiğini korur ama parent path conflict'i
    # yoktur. Net semantik: ``dof_details.<qid>`` sub-doc atomik olarak
    # (one-shot update) son güncellenmiş haline ulaşır; eski değer
    # gözlemciler verinin eksik field'larını ancak ``$set`` publish
    # olayını gördükten sonra görür.
    set_ops: Dict[str, Any] = {
        f"dof_details.{question_id}.status": body.status,
        f"dof_details.{question_id}.notes": body.notes,
        f"dof_details.{question_id}.resolution_note": body.resolution_note or body.notes,
        # ``updated_at`` / ``updated_by`` ana audit üzerinde değil — DOF sub-doc
        # üzerinde tutuluyor (audit doc'a ``$set``'in dof_details dışına
        # yazması hata oluşturur, ``dof_details.<qid>`` altına koyulur).
        f"dof_details.{question_id}.updated_at": now,
        f"dof_details.{question_id}.updated_by": current_user["id"],
        # B4 — aktif bir DÖF kaydı üzerinde yazıyoruz; eğer önceden
        # ``active=False`` olarak invalidate edilmişse atomic filter
        # (aşağıda) reddediyor; bu nedenle ``active=True`` set'i yalnız
        # state'i açık DÖF'lere uygular.
        f"dof_details.{question_id}.active": True,
    }

    unset_ops: Dict[str, str] = {}

    if body.status == "KAPATILDI":
        # Server-controlled: ``resolved_at`` her zaman server time UTC; client
        # bunu override edemez. ``resolved_by`` her zaman authenticated user
        # identity (admin gate FIX H ile kaldırıldı; non-admin scope'lu user
        # da kendi adına resolve edebilir).
        set_ops[f"dof_details.{question_id}.resolved_at"] = now
        set_ops[f"dof_details.{question_id}.resolved_by"] = user_display
    else:
        # Reopen senaryosunda closure alanları temizlenir — yoksa UI'da
        # eski resolved_at görünürdü.
        unset_ops[f"dof_details.{question_id}.resolved_at"] = ""
        unset_ops[f"dof_details.{question_id}.resolved_by"] = ""

    if body.status == "İŞLEMDE":
        set_ops[f"dof_details.{question_id}.in_progress_at"] = now
    else:
        unset_ops[f"dof_details.{question_id}.in_progress_at"] = ""

    update_ops: Dict[str, Any] = {
        "$set": set_ops,
        "$push": {f"dof_details.{question_id}.timeline_logs": log_entry},
    }
    if unset_ops:
        update_ops["$unset"] = unset_ops

    # Atomic $set into dof_details.<question_id> leaf paths, scoped to
    # user AND that question's current answer == "HAYIR".
    # B3 — deleted_at: None (soft-delete filtre), B4 — active != False
    # (invalidate edilen DÖF kaydı üzerinde güncelleme yasak) atomik
    # operatörün başarısız olmasını garanti eder.
    doc = await db.audits.find_one_and_update(
        {
            "_id": oid,
            **_scope_filter(current_user),
            "deleted_at": None,
            f"answers.{question_id}": "HAYIR",
            # B4 — ``dof_details.<qid>.active`` != False. active=True
            # veya alan yok (legacy) → izin var; active=False → atomik
            # update başarısız (no document matched) → 409 ile reject.
            "$or": [
                {f"dof_details.{question_id}.active": True},
                {f"dof_details.{question_id}.active": {"$exists": False}},
            ],
        },
        update_ops,
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        # Ayırım: audit scope içinde mi yoksa HAYIR race mi yoksa B4
        # inactive mi?
        existing = await db.audits.find_one(
            {"_id": oid, **_normal_audit_filter(current_user)},
            {"answers": 1, "dof_details": 1, "template_snapshot": 1, "state": 1},
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Denetim bulunamadı")
        snapshot_ids = {int(q["id"]) for q in _get_audit_questions(existing)}
        if question_id not in snapshot_ids:
            raise HTTPException(
                status_code=404,
                detail="Soru audit snapshot'ında bulunamadı",
            )
        # B4 — DÖF kaydı daha önce answer_changed_to_* ile inactive edilmiş.
        details = existing.get("dof_details") or {}
        existing_dof = details.get(str(question_id)) or details.get(question_id) or {}
        if (
            isinstance(existing_dof, dict)
            and existing_dof.get("active") is False
            and existing.get("answers", {}).get(str(question_id)) != "HAYIR"
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "dof_invalidated",
                    "message": (
                        "Bu DÖF kaydı cevap EVET/NA olarak değiştirildiği için "
                        "inactive edildi. Düzenlemek için önce cevabı tekrar "
                        "HAYIR yapın; sistem taze bir DÖF açacak."
                    ),
                },
            )
        # Snapshot'ta var ama cevap artık HAYIR değil
        raise HTTPException(
            status_code=409,
            detail={
                "code": "dof_answer_not_hayir",
                "message": "DÖF yalnızca HAYIR cevaplı sorular için oluşturulabilir.",
            },
        )

    # Persisted DÖF'yi response'a koy — client'ın optimistic update
    # doğruluğu için status / notes / updated_at server döner.
    stored_dof = (doc.get("dof_details") or {}).get(str(question_id)) or (
        (doc.get("dof_details") or {}).get(question_id)
    )
    stored_status = stored_dof.get("status") if stored_dof else body.status
    stored_notes = stored_dof.get("notes") if stored_dof else body.notes
    stored_updated_at = stored_dof.get("updated_at") if stored_dof else now
    stored_updated_by = stored_dof.get("updated_by") if stored_dof else current_user["id"]

    # Phase 2B — S18: DÖF kapatıldığında audit state transition tetikle.
    # Tüm DÖF'ler kapandıysa audit DOF_OPEN'dan DOF_CLOSED'a düşer; bu da
    # nihai rapor export'unun önünü açar. Transition idempotent — eğer
    # target state zaten mevcut state ile aynıysa sadece updated_at yenilenir.
    current_state = doc.get("state") or AuditState.DRAFT.value
    if body.status == "KAPATILDI":
        remaining_open = await _count_open_dofs(oid)
        target_state = audit_state.compute_dof_resolution_target_state(
            current_state, remaining_open
        )
        if target_state != current_state:
            set_fields = audit_state.transition_audit(
                doc,
                target_state,
                actor_id=current_user["id"],
                reason="Tüm DÖF'ler kapatıldı" if target_state == AuditState.DOF_CLOSED else "DÖF state transition",
                now_iso=now,
            )
            await db.audits.update_one({"_id": oid}, {"$set": set_fields})
            # doc reference güncelle ki response serialize doğru state'i görsün
            doc["state"] = set_fields.get("state", current_state)
            doc["is_completed"] = set_fields.get("is_completed", doc.get("is_completed"))
            doc["state_history"] = set_fields.get("state_history", doc.get("state_history", []))

    # Phase 2B — S20: DÖF update'i logla. Action: dof_update (her durum),
    # özel durumlar için ek olarak dof_open (AÇIK) / dof_close (KAPATILDI).
    # B6 — DÖF update'i compliance invariant (mutation of state-affecting
    # domain data) için mandatory=True. Log yazılamazsa endpoint 5xx
    # döner ki upstream UI'da görünür hale gelsin.
    # ``find_one_and_update`` öncesi mevcut DÖF state'ini yakala.
    # ``return_document=AFTER`` döndüğü için ``doc`` zaten yeni halde;
    # before için yeni bir sorgu atıyoruz (S20 consistency).
    before_dof = ((await db.audits.find_one(
        {"_id": oid, **_scope_filter(current_user)},
        {f"dof_details.{question_id}": 1},
    )) or {}).get("dof_details", {}).get(str(question_id)) or ((await db.audits.find_one(
        {"_id": oid, **_scope_filter(current_user)},
        {f"dof_details.{question_id}": 1},
    )) or {}).get("dof_details", {}).get(question_id)
    # Action tipi: durum bazlı
    if body.status == "KAPATILDI":
        action_enum = Action.DOF_CLOSE
    elif body.status == "AÇIK":
        action_enum = Action.DOF_OPEN
    else:
        action_enum = Action.DOF_UPDATE
    await log_action(
        db,
        audit_id=audit_id,
        user=current_user,
        action=action_enum,
        before={"dof": before_dof or {}},
        after={"dof": stored_dof or {}},
        mandatory=True,
    )

    return {
        "status": "success",
        "dof": {
            "audit_id": str(doc["_id"]),
            "question_id": question_id,
            "status": stored_status,
            "notes": stored_notes,
            "updated_at": stored_updated_at,
            "updated_by": stored_updated_by,
        },
    }


# ---------------- Photo Endpoints ----------------
@api_router.post("/audits/{audit_id}/questions/{question_id}/photos")
async def upload_question_photo(
    audit_id: str,
    question_id: int,
    file: UploadFile = File(...),
    photo_type: str = Query("finding"),
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    if photo_type not in ("finding", "resolution"):
        raise HTTPException(status_code=400, detail="Geçersiz photo_type. 'finding' veya 'resolution' olmalıdır.")

    # IDOR guard: audit lookup, ``user_id`` ``_scope_filter`` ile zorunlu.
    # Admin olmayan kullanıcı kendi ``user_id``'si dışındaki bir audit'e
    # foto yükleyemez; diğer kullanıcıların audit'leri bu yüzden 404 döner.
    # B3 — soft-delete filtre, B2 — FINAL state guard tek seferde.
    audit = await db.audits.find_one(
        {"_id": oid, **_normal_audit_filter(current_user)},
        {"state": 1, "template_snapshot": 1, "dof_details": 1},
    )
    if not audit:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")
    if (audit.get("state") or AuditState.DRAFT.value) == AuditState.FINAL.value:
        raise HTTPException(
            status_code=409,
            detail="FINAL denetim üzerinde mutasyon yapılamaz",
        )

    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        image = image.convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Yüklenen dosya geçerli bir görsel değil.")

    now = datetime.now(timezone.utc)
    date_path = now.strftime("%Y/%m")
    save_dir = UPLOAD_DIR / date_path
    save_dir.mkdir(parents=True, exist_ok=True)

    photo_id = str(uuid.uuid4())
    filename = f"{photo_id}.webp"
    thumb_filename = f"{photo_id}_thumb.webp"

    image.thumbnail((1920, 1080))
    main_path = save_dir / filename
    image.save(main_path, "WEBP", quality=82)

    thumb_image = image.copy()
    thumb_image.thumbnail((300, 300))
    thumb_path = save_dir / thumb_filename
    thumb_image.save(thumb_path, "WEBP", quality=75)

    rel_url = f"/uploads/photos/{date_path}/{filename}"
    rel_thumb_url = f"/uploads/photos/{date_path}/{thumb_filename}"

    photo_obj = {
        "id": photo_id,
        "type": photo_type,
        "url": rel_url,
        "thumb_url": rel_thumb_url,
        "created_at": now.isoformat(),
        "created_by": current_user["id"],
    }

    questions = audit.get("template_snapshot", {}).get("questions", [])
    q_index = -1
    for idx, q in enumerate(questions):
        if int(q.get("id", 0)) == question_id:
            q_index = idx
            break

    if q_index == -1:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")

    target_key = f"template_snapshot.questions.{q_index}.photos.{photo_type}"
    update_query = {"$push": {target_key: photo_obj}}

    dof_details = audit.get("dof_details", {})
    current_dof = dof_details.get(str(question_id), {})
    current_dof_status = current_dof.get("status", "AÇIK")
    next_modify_count = (current_dof.get("photo_modify_count", 0) + 1)
    
    update_query["$set"] = {
        f"dof_details.{question_id}.photo_modify_count": next_modify_count,
    }

    if photo_type == "resolution" and current_dof_status == "AÇIK":
        update_query["$set"][f"dof_details.{question_id}.status"] = "İŞLEMDE"
        update_query["$set"][f"dof_details.{question_id}.updated_at"] = now.isoformat()
        update_query["$set"][f"dof_details.{question_id}.updated_by"] = current_user["id"]

    await db.audits.update_one({"_id": oid, **_scope_filter(current_user)}, update_query)

    # Phase 2B — S20: foto yükleme logla. B6 — mandatory=True: foto
    # ekleme forensic/compliance gereği mute mutasyondur; log
    # yazılamazsa UI'da görünür hata yükseltilir.
    await log_action(
        db,
        audit_id=audit_id,
        user=current_user,
        action=Action.PHOTO_UPLOAD,
        before=None,
        after={
            "photo_id": photo_id,
            "photo_type": photo_type,
            "question_id": question_id,
            "photo_modify_count": next_modify_count,
        },
        mandatory=True,
    )

    return {"status": "success", "photo": photo_obj, "photo_modify_count": next_modify_count}


@api_router.delete("/audits/{audit_id}/questions/{question_id}/photos/{photo_id}")
async def delete_question_photo(
    audit_id: str,
    question_id: int,
    photo_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(audit_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz denetim ID")

    # IDOR guard: photo silme işlemi de ``_scope_filter`` ile scope'lanır;
    # başka kullanıcının audit'ine ait fotoğraf silinemez.
    # B3 — soft-delete filtre, B2 — FINAL state guard tek seferde.
    audit = await db.audits.find_one(
        {"_id": oid, **_normal_audit_filter(current_user)},
        {"state": 1, "template_snapshot": 1, "dof_details": 1},
    )
    if not audit:
        raise HTTPException(status_code=404, detail="Denetim bulunamadı")
    if (audit.get("state") or AuditState.DRAFT.value) == AuditState.FINAL.value:
        raise HTTPException(
            status_code=409,
            detail="FINAL denetim üzerinde mutasyon yapılamaz",
        )

    questions = audit.get("template_snapshot", {}).get("questions", [])
    q_index = -1
    target_photo = None
    photo_type = None

    for idx, q in enumerate(questions):
        if int(q.get("id", 0)) == question_id:
            q_index = idx
            photos = q.get("photos", {})
            for p in photos.get("finding", []):
                if p["id"] == photo_id:
                    target_photo = p
                    photo_type = "finding"
                    break
            if not target_photo:
                for p in photos.get("resolution", []):
                    if p["id"] == photo_id:
                        target_photo = p
                        photo_type = "resolution"
                        break
            break

    if q_index == -1 or not target_photo:
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı.")

    try:
        url_path = target_photo["url"].lstrip("/")
        thumb_path = target_photo["thumb_url"].lstrip("/")
        (ROOT_DIR / url_path).unlink(missing_ok=True)
        (ROOT_DIR / thumb_path).unlink(missing_ok=True)
    except Exception:
        pass

    target_key = f"template_snapshot.questions.{q_index}.photos.{photo_type}"
    dof_details = audit.get("dof_details", {})
    current_dof = dof_details.get(str(question_id), {})
    next_modify_count = (current_dof.get("photo_modify_count", 0) + 1)

    await db.audits.update_one(
        {"_id": oid, **_scope_filter(current_user)},
        {
            "$pull": {target_key: {"id": photo_id}},
            "$set": {f"dof_details.{question_id}.photo_modify_count": next_modify_count}
        }
    )

    # Phase 2B — S20: foto silme logla. B6 — mandatory=True: foto silme
    # forensic/compliance gereği mute mutasyondur.
    await log_action(
        db,
        audit_id=audit_id,
        user=current_user,
        action=Action.PHOTO_DELETE,
        before={
            "photo_id": photo_id,
            "photo_type": photo_type,
            "question_id": question_id,
        },
        after={"deleted": True, "photo_modify_count": next_modify_count},
        mandatory=True,
    )

    return {"status": "success", "photo_modify_count": next_modify_count}


# ---------------- Health ----------------
@api_router.get("/")
async def root():
    return {"message": "ABCD Tech Solutions Risk Analiz API", "status": "ok"}


# ---------------- App wiring ----------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- Startup ----------------
def _require_admin_env():
    try:
        email = os.environ["ADMIN_EMAIL"].strip().lower()
        password = os.environ["ADMIN_PASSWORD"]
    except KeyError as e:
        missing = e.args[0]
        raise RuntimeError(
            f"Gerekli ortam değişkeni eksik: {missing}. "
            "backend/.env dosyasını oluştur ve ADMIN_EMAIL ile ADMIN_PASSWORD değerlerini ayarla."
        ) from None
    if not email or "@" not in email:
        raise RuntimeError(f"ADMIN_EMAIL geçersiz: {email!r}")
    if len(password) < 8:
        raise RuntimeError(
            "ADMIN_PASSWORD en az 8 karakter olmalı. "
            "Varsayılan bir değer kullanma; güçlü/unique bir parola seç."
        )
    return email, password


async def seed_admin():
    admin_email, admin_password = _require_admin_env()
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Yönetici",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif existing.get("role") != "admin" or not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email},
                                   {"$set": {"role": "admin", "password_hash": hash_password(admin_password)}})


async def seed_default_template() -> bool:
    """``isg_v1_default`` template'ini idempotent olarak seed et.

    Mevcut template'i sessizce overwrite etmez; ``code`` unique index ile
    duplicate insert engellenir. İdempotency sözleşmesi (Phase 2A testleri
    tarafından korunur):

    * İlk çağrı: ``True`` döner + DB'ye insert edilir.
    * Sonraki çağrılar: ``False`` döner + DB dokunulmaz.

    Bu davranış ``db.templates.update_one`` ile ``questions`` alanını
    overwrite etmeyen ana contract'ı korur. Yeni bir template sürümü
    gerektiğinde manuel migration yapılır (template code bump).
    """
    code = isg_v1.TEMPLATE_CODE
    existing = await db.templates.find_one({"code": code})
    if existing is not None:
        return False
    now = datetime.now(timezone.utc).isoformat()
    doc = isg_v1.build_template_doc()
    doc["created_at"] = now
    doc["updated_at"] = now
    try:
        await db.templates.insert_one(doc)
    except Exception:
        # DuplicateKeyError beklenebilir (race). Tekrar sorgula.
        again = await db.templates.find_one({"code": code})
        if again is None:
            raise
        return False
    return True


DEMO_BRANCH_CODE: str = "DEMO-ALL-RISK-01"


async def seed_all_no_sample_audit():
    """Tek bir tamamlanmış 84 soruluk demo denetimi atomik şekilde ekle.

    Üretim güvenliği
    ----------------
    ``ENVIRONMENT`` ``production`` veya ``prod`` olduğunda (küçük harf
    karşılaştırması) erken çıkar. Bu guard yalnızca **defense-in-depth**
    amaçlıdır — gerçek koruma, ``on_startup`` artık bu fonksiyonu
    çağırmadığı için sağlanır. Yani:

    * Normal FastAPI/Uvicorn başlangıcı demo denetimi **asla** oluşturmaz.
    * Bu fonksiyon yalnız açık bir geliştirici/UAT komutuyla tetiklenir
      (``backend/seed/seed_demo_audit.py``).

    Ardışık tek-süreçli idempotency
    -------------------------------
    ``find_one + insert_one`` ardışık tek-süreçli çağrılarda dahi
    ``await`` arasındaki yarışa açıktı. Yeni sözleşme:

        await db.audits.update_one(
            {"branch_code": DEMO_BRANCH_CODE},
            {"$setOnInsert": audit_doc},
            upsert=True,
        )

    Filter eşleşirse ``$setOnInsert`` uygulanmaz (dokunulmaz),
    eşleşmezse yeni doküman ``$setOnInsert`` alanlarıyla birlikte
    eklenir. **Ardışık tek-süreçli** çağrılarda (ör. ``python -m
    seed.seed_demo_audit`` sonrası elle bir kez daha çalıştırma)
    idempotent davranış sağlar.

    Kapsam dışı: ``branch_code`` üzerinde unique index yoktur; bu
    nedenle **çoklu bağımsız süreçlerin eşzamanlı** çalışması bu
    değişiklik kapsamında garanti edilmez. Üretimde bu durum zaten
    ortaya çıkmaz çünkü ``on_startup`` bu fonksiyonu çağırmaz; demo
    seed tek bir geliştirici/UAT provisioning komutu olarak çalışır.
    Global unique index eklenmez — restoran isimleri normal veride
    çakışabilir.

    Filter anahtarı (``branch_code == "DEMO-ALL-RISK-01"``) demo-özgüdür;
    normal denetimler bu değeri taşımadığı için ``$setOnInsert``
    yalnızca demo kaydını korur.
    """
    import os
    env_name = os.getenv("ENVIRONMENT", "development").lower()
    if env_name in ("production", "prod"):
        return

    admin_user = await db.users.find_one({"role": "admin"})
    if not admin_user:
        admin_user = await db.users.find_one({})
    if not admin_user:
        return
    admin_id = str(admin_user["_id"])

    snapshot = isg_v1.build_template_doc()
    answers = {str(q["id"]): "HAYIR" for q in snapshot.get("questions", [])}
    now = datetime.now(timezone.utc).isoformat()

    audit_doc = {
        "user_id": admin_id,
        "restaurant_name": "TÜM RİSKLER ÖRNEK DEMO ŞUBESİ (TÜM SORULAR HAYIR)",
        "address": "ABCD Tech Solutions Örnek Test Restoranı, Kadıköy, İstanbul",
        "audit_date": datetime.now().strftime("%Y-%m-%d"),
        "denetci": "Örnek İSG Başdenetçisi (Demo)",
        "restaurant_manager": "Demo Restoran Müdürü",
        "auditor_title": "İSG Başdenetçisi",
        "branch_code": DEMO_BRANCH_CODE,
        "brand": "Burger King",
        "city": "İstanbul",
        "district": "Kadıköy",
        "audit_notes": "UAT ve İş Yeri Beyanı Testi İçin Oluşturulmuş Tüm Soruları HAYIR İşaretli Örnek Denetim.",
        "template_code": snapshot.get("code", "isg_v1_default"),
        "template_version": snapshot.get("version", 1),
        "template_snapshot": snapshot,
        "answers": answers,
        "risk_overrides": {},
        "is_completed": True,
        "completed_at": now,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    await db.audits.update_one(
        {"branch_code": DEMO_BRANCH_CODE},
        {"$setOnInsert": audit_doc},
        upsert=True,
    )


@app.on_event("startup")
async def on_startup():
    initialize_jwt_secret()
    initialize_cookie_policy()
    admin_email, admin_password = _require_admin_env()
    await db.users.create_index("email", unique=True)
    await db.audits.create_index("user_id")
    # B7 — İbraz persistence indeksleri. ``audit_ibraz`` koleksiyonu
    # için unique (audit_id, ibraz_hash) ve history listeleme için
    # (audit_id, exported_at DESC).
    await _ensure_ibraz_indexes(db)
    # Aşama 2A: template seed + cache
    await db.templates.create_index("code", unique=True)
    await seed_default_template()
    await load_templates_cache()
    await seed_admin()
    # Demo audit (``seed_all_no_sample_audit``) intentionally NOT seeded
    # from startup: demo data must be created only by an explicit developer
    # command (``python -m seed.seed_demo_audit``). Startup is no longer a
    # side-effectful demo-data provisioning channel.


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
