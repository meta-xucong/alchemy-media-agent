# 80 V3 Provider Reference Upload Compression Spec

## Purpose

V3 must reduce upstream image-edit failure caused by oversized multipart reference images without degrading the user-facing asset archive. Large user uploads, selected project outputs, generated identity anchors, and future template references all enter the same provider-reference preparation path before they are sent to the image provider.

## Rules

1. Preserve originals. Never overwrite uploaded images or generated `original.*` outputs.
2. Use one provider-reference service for every source type:
   - user uploaded reference images
   - selected project images
   - generated identity anchors
   - future ecommerce, photographer, and brand references
3. Prepare only the provider input copy:
   - max upload bytes: `OPENAI_IMAGE_REFERENCE_MAX_UPLOAD_BYTES`, default `1200000`
   - max long edge: `OPENAI_IMAGE_REFERENCE_MAX_EDGE`, default `1024`
   - JPEG quality: `OPENAI_IMAGE_REFERENCE_JPEG_QUALITY`, default `88`
4. Cache prepared files under `.media_storage/provider_reference_cache`.
5. Reuse cached files when source path, size, mtime, and compression settings are unchanged.
6. Do not use the frontend thumbnail as provider input. Frontend thumbnails are optimized for display speed, not visual reasoning. The provider-reference copy is the shared, quality-preserving upstream variant.

## Flow

```text
Project reference source
  -> asset_plan.storage_path
  -> reference_image_paths()
  -> prepare_provider_reference_images()
  -> provider_reference_cache/*.jpg when needed
  -> OpenAI-compatible images.edit
```

## Acceptance

- A large uploaded PNG is converted to an upstream-friendly JPEG before provider submission.
- A selected generated PNG follows the same path.
- Small supported image files are sent unchanged.
- The original source file remains byte-for-byte unchanged.
- Repeated use of the same large source reuses the cached provider-reference file.
- This does not change project history, frontend preview, download, or archive behavior.
