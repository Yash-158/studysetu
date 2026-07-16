"""LocalStorageProvider -> writes under storage.upload_dir (uploads_data volume in prod).
Includes retention cleanup task: WHERE expires_at < now() AND deleted_at IS NULL -> delete file, soft-delete row.
TODO(M1 startup wiring; M7 submissions/materials)."""
