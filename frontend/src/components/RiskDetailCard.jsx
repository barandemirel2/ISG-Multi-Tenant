import React from "react";
import { AlertTriangle, Clock, FileText, ShieldAlert } from "lucide-react";

export function RiskDetailCard({ question }) {
  if (!question) return null;

  const olasilik = question.olasilik || question.o || 3;
  const siddet = question.siddet || question.s || 3;
  const riskSkoru = olasilik * siddet;

  // Canonical Aşama 1 eşikleri (backend ``classify_risk`` ile aynı):
  //   1–4 Kabul Edilebilir, 5–12 Dikkate Değer, 13–25 Kabul Edilemez.
  // Eski ``>= 15`` fallback'i 13 ve 14 skorlu soruları "Dikkate Değer" gibi
  // gösteriyordu — backend ``risk_seviyesi`` zaten canonical dönüyor,
  // yine de defensive fallback eşikleri tutarlı olmalı.
  const isKabulEdilemez = question.risk_seviyesi === "Kabul Edilemez" || riskSkoru >= 13;
  const riskColor = isKabulEdilemez 
    ? "text-red-400 bg-red-500/10 border-red-500/30" 
    : "text-amber-400 bg-amber-500/10 border-amber-500/30";

  const tedbirMetni = question.tedbir || question.alinmasi_gereken_tedbir || question.dof_aksiyonu || 
    "İlgili alanda mevzuata uygun düzeltici/önleyici aksiyon (DÖF) derhal planlanmalı ve risk ortadan kaldırılmalıdır.";

  const terminSuresi = question.termin || question.termin_suresi || (isKabulEdilemez ? "Derhal / 24 Saat" : "7 İş Günü");

  return (
    <div className="rounded-card border border-slate-800 bg-slate-950/80 p-4 space-y-4 shadow-inner mt-3">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        
        {/* 1. RİSK MATRİSİ KUTUSU */}
        <div className={`p-3.5 rounded-card border flex flex-col justify-between ${riskColor}`}>
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5" />
              RİSK MATRİSİ [{olasilik} × {siddet}]
            </span>
            <AlertTriangle className="w-4 h-4 shrink-0" />
          </div>

          <div className="my-3 flex items-baseline justify-between">
            <div>
              <span className="text-2xl font-black font-mono">{riskSkoru}</span>
              <span className="text-[10px] font-mono ml-1 opacity-80">PUAN</span>
            </div>
            <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-black/40 border border-current">
              {question.risk_seviyesi || (isKabulEdilemez ? "Kabul Edilemez" : "Dikkate Değer")}
            </span>
          </div>

          <p className="text-[10px] font-mono opacity-75">
            (Olasılık: {olasilik} / Şiddet: {siddet})
          </p>
        </div>

        {/* 2. ALINMASI GEREKEN TEDBİR (DÖF) */}
        <div className="md:col-span-2 p-3.5 rounded-card border border-slate-800 bg-slate-900/90 flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono font-semibold text-slate-300 mb-2">
              <FileText className="w-4 h-4 text-red-400" />
              ALINMASI GEREKEN TEDBİR (DÖF)
            </div>
            <div className="text-xs text-amber-300 leading-relaxed font-mono bg-amber-500/10 p-3 rounded-lg border border-amber-500/20">
              {tedbirMetni}
            </div>
          </div>

          {/* UYGULAMA TERMİNİ */}
          <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs font-mono">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              UYGULAMA TERMİNİ:
            </span>
            <span className="font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 rounded-md">
              {terminSuresi}
            </span>
          </div>
        </div>

      </div>
    </div>
  );
}

export default RiskDetailCard;
