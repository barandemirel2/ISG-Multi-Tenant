// Test IDs for the photo evidence feature (PhotoUploader + PhotoLightbox).
// The lightbox chrome is intentionally stable so contract tests can
// target specific nodes without depending on Tailwind class strings.

export const PHOTO = {
  // Lightbox overlay / structure
  lightboxOverlay: "photo-lightbox-overlay",
  lightboxViewer: "photo-lightbox-viewer",
  lightboxToolbar: "photo-lightbox-toolbar",
  lightboxImageWrap: "photo-lightbox-image-wrap",
  lightboxImage: "photo-lightbox-image",

  // Toolbar buttons
  lightboxClose: "photo-lightbox-close",
  lightboxDownload: "photo-lightbox-download",
  lightboxDelete: "photo-lightbox-delete",

  // Footer meta
  lightboxFooter: "photo-lightbox-footer",

  // Type badge
  lightboxBadge: "photo-lightbox-badge",
};
