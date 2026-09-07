import React, { useRef, useState } from "react";
import { Camera, Upload, Loader2, Image as ImageIcon, Trash2, Plus, Eye, Lock } from "lucide-react";
import api, { BACKEND_ORIGIN } from "@/lib/api";
import { toast } from "sonner";
import PhotoLightbox from "./PhotoLightbox";

export function PhotoUploader({
  auditId,
  questionId,
  photoType = "finding", // "finding" or "resolution"
  photos = [],
  onPhotosChange,
  modifyCount = 0,
  maxModifyRights = 3,
  isAdmin = false,
  maxPhotos = 3,
  disabled = false,
  label = "Fotoğraf Ekle",
}) {
  const [uploading, setUploading] = useState(false);
  const [activePhoto, setActivePhoto] = useState(null);
  const fileInputRef = useRef(null);

  const safePhotos = Array.isArray(photos) ? photos : [];
  const isModifyLocked = modifyCount >= maxModifyRights && !isAdmin;

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    if (isModifyLocked) {
      toast.error(
        "Bu DÖF için maksimum fotoğraf değiştirme limitine (3/3) ulaşıldı. Değişiklik yetkisi kilitlenmiştir, işlem için Yöneticiniz ile iletişime geçiniz."
      );
      return;
    }

    if (safePhotos.length >= maxPhotos) {
      toast.error(`En fazla ${maxPhotos} adet fotoğraf ekleyebilirsiniz.`);
      return;
    }

    const file = files[0];
    if (!file.type.startsWith("image/")) {
      toast.error("Lütfen geçerli bir görsel dosyası seçin (JPG, PNG, WEBP).");
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await api.post(
        `/audits/${auditId}/questions/${questionId}/photos?photo_type=${photoType}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );

      const newPhoto = res?.data?.photo;
      if (newPhoto) {
        const nextModifyCount = (res?.data?.photo_modify_count ?? modifyCount + 1);
        toast.success(
          photoType === "resolution"
            ? "Saha düzeltme kanıtı başarıyla sisteme işlendi. DÖF durumunuz İŞLEMDE olarak güncellendi ve denetçi onayına sunuldu."
            : "Tespit fotoğrafı başarıyla yüklendi."
        );
        if (onPhotosChange) {
          onPhotosChange([...safePhotos, newPhoto], photoType, nextModifyCount);
        }
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || "Fotoğraf yüklenemedi.";
      toast.error(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDeletePhoto = async (photo) => {
    if (isModifyLocked) {
      toast.error(
        "Bu DÖF için maksimum fotoğraf değiştirme limitine (3/3) ulaşıldı. Değişiklik yetkisi kilitlenmiştir, işlem için Yöneticiniz ile iletişime geçiniz."
      );
      return;
    }

    try {
      const res = await api.delete(`/audits/${auditId}/questions/${questionId}/photos/${photo.id}`);
      const nextModifyCount = (res?.data?.photo_modify_count ?? modifyCount + 1);
      toast.success("Fotoğraf silindi.");
      const updated = safePhotos.filter((p) => p.id !== photo.id);
      if (onPhotosChange) {
        onPhotosChange(updated, photoType, nextModifyCount);
      }
      if (activePhoto?.id === photo.id) {
        setActivePhoto(null);
      }
    } catch (err) {
      toast.error("Fotoğraf silinemedi.");
    }
  };

  return (
    <div className="space-y-2 font-sans">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold text-slate-700 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5 font-sans">
          <ImageIcon className="w-3.5 h-3.5 text-slate-600 dark:text-slate-400" />
          {label} ({safePhotos.length}/{maxPhotos})
          {photoType === "resolution" && (
            <span className="text-[10px] text-amber-700 dark:text-amber-400 font-mono font-normal">
              [Hak: {Math.min(modifyCount, maxModifyRights)}/{maxModifyRights}]
            </span>
          )}
        </span>

        {safePhotos.length < maxPhotos && !isModifyLocked && (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
disabled={uploading || disabled}
            className={`px-3 py-1 rounded-card text-xs font-sans font-semibold flex items-center gap-1.5 transition-all duration-200 active:scale-95 cursor-pointer border disabled:cursor-not-allowed disabled:opacity-60 ${
              photoType === "resolution"
                ? "bg-emerald-100 hover:bg-emerald-200 text-emerald-800 border-emerald-300 dark:bg-emerald-500/10 dark:hover:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/30"
                : "bg-red-100 hover:bg-red-200 text-red-800 border-red-300 dark:bg-red-500/10 dark:hover:bg-red-500/20 dark:text-red-300 dark:border-red-500/30"
            }`}
          >
            {uploading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Plus className="w-3.5 h-3.5" />
            )}
            <span>{uploading ? "Yükleniyor…" : "Fotoğraf Seç"}</span>
          </button>
        )}
      </div>

      {/* 3/3 MODIFY LIMIT LOCK NOTICE */}
      {isModifyLocked && photoType === "resolution" && (
        <div className="p-2.5 rounded-card border border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300 text-[11px] flex items-center gap-2 font-sans font-medium">
          <Lock className="w-4 h-4 text-amber-700 dark:text-amber-400 shrink-0" />
          <span>
            Bu DÖF için maksimum fotoğraf değiştirme limitine (3/3) ulaşıldı. Değişiklik yetkisi kilitlenmiştir, işlem için Yöneticiniz ile iletişime geçiniz.
          </span>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* THUMBNAIL GRID */}
      {safePhotos.length > 0 && (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 pt-1">
          {safePhotos.map((p) => {
            const thumbUrl = p.thumb_url
              ? p.thumb_url.startsWith("http")
                ? p.thumb_url
                : `${BACKEND_ORIGIN}${p.thumb_url}`
              : p.url;

            return (
              <div
                key={p.id}
                className="group relative aspect-square rounded-card overflow-hidden border border-slate-200 bg-slate-100 dark:border-white/10 dark:bg-slate-900 shadow-md transition-all hover:border-slate-300 dark:hover:border-white/30"
              >
                <img
                  src={thumbUrl}
                  alt="Thumbnail"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />

                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2 p-1">
                  <button
                    type="button"
                    onClick={() => setActivePhoto(p)}
                    className="p-1.5 rounded-lg bg-white/20 hover:bg-white/30 text-white transition-colors"
                    title="Büyüt"
                  >
                    <Eye className="w-3.5 h-3.5" />
                  </button>

                  {!disabled && !isModifyLocked && (
                    <button
                      type="button"
                      onClick={() => handleDeletePhoto(p)}
                      className="p-1.5 rounded-lg bg-red-500/40 hover:bg-red-500/60 text-white transition-colors"
                      title="Sil"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* LIGHTBOX MODAL */}
      {activePhoto && (
        <PhotoLightbox
          photo={activePhoto}
          onClose={() => setActivePhoto(null)}
          onDelete={handleDeletePhoto}
          canDelete={!disabled && !isModifyLocked}
        />
      )}
    </div>
  );
}

export default PhotoUploader;
