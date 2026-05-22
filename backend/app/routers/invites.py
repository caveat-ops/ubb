from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import InviteToken
from app.schemas import InviteCreate, InviteOut, InviteValidate

router = APIRouter()


@router.post("/", response_model=InviteOut)
async def create_invite(
    body: InviteCreate,
    db: AsyncSession = Depends(get_db),
):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)
    invite = InviteToken(
        token=token,
        expires_at=expires_at,
        usage_limit=body.usage_limit,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return InviteOut(token=invite.token, expires_at=invite.expires_at, active=invite.active)


@router.post("/validate", response_model=InviteOut)
async def validate_invite(
    body: InviteValidate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InviteToken).where(InviteToken.token == body.token)
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invalid token")
    if not invite.active:
        raise HTTPException(status_code=400, detail="Token is inactive")
    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token has expired")
    if invite.times_used >= invite.usage_limit:
        raise HTTPException(status_code=400, detail="Token usage limit reached")
    return InviteOut(token=invite.token, expires_at=invite.expires_at, active=invite.active)
