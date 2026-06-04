from __future__ import annotations

# Queue worker placeholder.
# Production responsibilities:
# 1. Load GenerationJob from DB.
# 2. Resolve assets and provider credentials.
# 3. Call ImageProvider.generate/edit.
# 4. Store outputs in object storage.
# 5. Write GenerationOutput rows.
# 6. Emit SSE/WebSocket events.

from app.repositories import repository


async def run_image_job(job_id: str) -> None:
    job = repository.get_job(job_id)
    if not job:
        raise ValueError(f"Image job not found: {job_id}")
    if job.job_type != "image":
        raise ValueError(f"Job is not an image job: {job_id}")
