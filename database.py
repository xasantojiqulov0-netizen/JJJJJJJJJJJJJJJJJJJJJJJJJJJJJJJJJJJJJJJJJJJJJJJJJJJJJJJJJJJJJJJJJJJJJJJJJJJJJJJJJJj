from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import (
    BigInteger, String, DateTime, Boolean, Integer, Text,
    select, func, ForeignKey
)
from config import DATABASE_URL, DEFAULT_TARIFFS


engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    decoy_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tariff_id: Mapped[int] = mapped_column(Integer, nullable=False)   # Tariff.id
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    months: Mapped[int] = mapped_column(Integer, nullable=False)
    receipt_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|approved|rejected
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AdminCard(Base):
    __tablename__ = "admin_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_number: Mapped[str] = mapped_column(String(32), nullable=False)
    card_owner: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Tariff(Base):
    """Admin botdan boshqaradigan tariflar."""
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)   # "1 oylik"
    months: Mapped[int] = mapped_column(Integer, nullable=False)     # 1
    price: Mapped[int] = mapped_column(Integer, nullable=False)      # 30000
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)      # tartib


class TrapLog(Base):
    __tablename__ = "trap_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visitor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visitor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    visitor_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# ─── DB yordamchi funksiyalari ────────────────────────────────────────────────

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Default tariflarni seed qilamiz (faqat bo'sh bo'lsa)
    await _seed_tariffs()


async def _seed_tariffs():
    """Tariffs jadvali bo'sh bo'lsa default tariflarni qo'shadi."""
    async with SessionLocal() as session:
        count = (await session.execute(select(func.count(Tariff.id)))).scalar() or 0
        if count == 0:
            for i, t in enumerate(DEFAULT_TARIFFS):
                session.add(Tariff(
                    label=t["label"],
                    months=t["months"],
                    price=t["price"],
                    is_active=True,
                    sort_order=i,
                ))
            await session.commit()


async def get_tariffs(session: AsyncSession) -> list[Tariff]:
    """Faol tariflarni tartiblangan holda qaytaradi."""
    result = await session.execute(
        select(Tariff)
        .where(Tariff.is_active == True)
        .order_by(Tariff.sort_order, Tariff.months)
    )
    return result.scalars().all()


async def get_all_tariffs(session: AsyncSession) -> list[Tariff]:
    """Barcha tariflar (faol + nofaol)."""
    result = await session.execute(
        select(Tariff).order_by(Tariff.sort_order, Tariff.months)
    )
    return result.scalars().all()


async def get_tariff_by_id(session: AsyncSession, tariff_id: int) -> Tariff | None:
    result = await session.execute(select(Tariff).where(Tariff.id == tariff_id))
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: str | None,
    referred_by: int | None = None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        import secrets
        from sqlalchemy.exc import IntegrityError
        code = secrets.token_urlsafe(6)
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            referral_code=code,
            referred_by=referred_by,
        )
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
        except IntegrityError:
            await session.rollback()
            result2 = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result2.scalar_one()
    else:
        user.full_name = full_name
        user.username = username
        await session.commit()
    return user


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_active_card(session: AsyncSession) -> AdminCard | None:
    result = await session.execute(
        select(AdminCard).where(AdminCard.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


async def get_trap_logs(session: AsyncSession, owner_id: int, limit: int = 20) -> list[TrapLog]:
    result = await session.execute(
        select(TrapLog)
        .where(TrapLog.owner_id == owner_id)
        .order_by(TrapLog.clicked_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_trap_count(session: AsyncSession, owner_id: int) -> int:
    result = await session.execute(
        select(func.count(TrapLog.id)).where(TrapLog.owner_id == owner_id)
    )
    return result.scalar() or 0


async def get_stats(session: AsyncSession) -> dict:
    total_users = (await session.execute(
        select(func.count(User.id))
    )).scalar() or 0

    subscribed = (await session.execute(
        select(func.count(User.id)).where(User.is_subscribed == True)
    )).scalar() or 0

    today = datetime.now(timezone.utc).date()
    today_payments = (await session.execute(
        select(func.count(Payment.id)).where(
            Payment.status == "approved",
            func.date(Payment.created_at) == today,
        )
    )).scalar() or 0

    total_income = (await session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "approved")
    )).scalar() or 0

    return {
        "total_users": total_users,
        "subscribed": subscribed,
        "today_payments": today_payments,
        "total_income": total_income,
    }
