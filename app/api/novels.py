# SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
# SPDX-License-Identifier: AGPL-3.0-only

from fastapi import APIRouter

from . import novel_support
from .novel_chapters import router as novel_chapter_router
from .novel_continuations import router as novel_continuation_router
from .novel_status import router as novel_status_router
from .novel_uploads import router as novel_upload_router

router = APIRouter()
router.include_router(novel_upload_router)
router.include_router(novel_status_router)
router.include_router(novel_chapter_router)
router.include_router(novel_continuation_router)

UPLOAD_DIR = novel_support.UPLOAD_DIR
UPLOAD_CONSENT_VERSION = novel_support.UPLOAD_CONSENT_VERSION
STREAMING_RESPONSE_HEADERS = novel_support.STREAMING_RESPONSE_HEADERS
_safe_delete_where = novel_support.safe_delete_where
_verify_novel_access = novel_support.verify_novel_access
