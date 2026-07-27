from datetime import datetime, timedelta
from sqlalchemy import Integer, String, Float, JSON, BigInteger, DateTime, Index, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class UserFilter(Base):
    __tablename__ = "filters"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    filter_data: Mapped[dict] = mapped_column(JSON, default={})

class Order(Base):
    __tablename__ = "orders"
    id = mapped_column(String(100), primary_key=True)
    platform = mapped_column(String(50))
    user_id = mapped_column(BigInteger)
    origin_country = mapped_column(String(10))
    origin_city = mapped_column(String(100))
    dest_country = mapped_column(String(10))
    dest_city = mapped_column(String(100))
    weight_kg = mapped_column(Float, nullable=True)
    volume_m3 = mapped_column(Float, nullable=True)
    pallets = mapped_column(Integer, nullable=True)
    price_eur = mapped_column(Float, nullable=True)
    raw_data = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    expires_at = mapped_column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=7))
    deadline = mapped_column(DateTime, nullable=True)  # срок доставки
    
    __table_args__ = (
        Index('idx_order_user_created', 'user_id', 'created_at'),
    )

class Favorite(Base):
    __tablename__ = "favorites"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(BigInteger)
    order_id = mapped_column(String(100))
    platform = mapped_column(String(50))
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_favorite_user_order', 'user_id', 'order_id', unique=True),
    )

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    paused: Mapped[bool] = mapped_column(default=False)  # <-- НОВОЕ ПОЛЕ

class AcceptedOrder(Base):
    __tablename__ = "accepted_orders"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(BigInteger)
    order_id = mapped_column(String(100))
    platform = mapped_column(String(50))
    accepted_at = mapped_column(DateTime, default=datetime.utcnow)
    # можно добавить ещё поля по желанию


# ---------- Сохранение заказа ----------
async def save_order(user_id: int, order_data: dict):
    async with async_session() as session:
        stmt = select(Order).where(
            Order.id == order_data["id"],
            Order.platform == order_data["platform"],
            Order.user_id == user_id
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.created_at = datetime.utcnow()
            existing.expires_at = datetime.utcnow() + timedelta(days=7)
        else:
            order = Order(
                id=order_data["id"],
                platform=order_data["platform"],
                user_id=user_id,
                origin_country=order_data.get("origin_country"),
                origin_city=order_data.get("origin_city"),
                dest_country=order_data.get("dest_country"),
                dest_city=order_data.get("dest_city"),
                weight_kg=order_data.get("weight_kg"),
                volume_m3=order_data.get("volume_m3"),
                pallets=order_data.get("pallets"),
                price_eur=order_data.get("price_eur"),
                raw_data=order_data.get("raw"),
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            session.add(order)
        await session.commit()

async def accept_order(user_id: int, order_id: str, platform: str):
    """Сохраняет заказ как принятый и удаляет из избранного"""
    async with async_session() as session:
        # Добавляем в принятые
        accepted = AcceptedOrder(user_id=user_id, order_id=order_id, platform=platform)
        session.add(accepted)
        # Удаляем из избранного (если там есть)
        stmt = select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.order_id == order_id,
            Favorite.platform == platform
        )
        result = await session.execute(stmt)
        fav = result.scalar_one_or_none()
        if fav:
            await session.delete(fav)
        await session.commit()
        return True

# ---------- Получение заказов за N дней ----------
async def get_orders_for_user(user_id: int, days: int = 2):
    cutoff = datetime.utcnow() - timedelta(days=days)
    async with async_session() as session:
        stmt = select(Order).where(
            Order.user_id == user_id,
            Order.created_at >= cutoff
        ).order_by(Order.created_at.desc())
        result = await session.execute(stmt)
        return result.scalars().all()

# ---------- Избранное ----------
async def add_favorite(user_id: int, order_id: str, platform: str):
    async with async_session() as session:
        stmt = select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.order_id == order_id,
            Favorite.platform == platform
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is None:
            fav = Favorite(user_id=user_id, order_id=order_id, platform=platform)
            session.add(fav)
            await session.commit()
            return True
        return False

async def remove_favorite(user_id: int, order_id: str, platform: str):
    async with async_session() as session:
        stmt = select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.order_id == order_id,
            Favorite.platform == platform
        )
        result = await session.execute(stmt)
        fav = result.scalar_one_or_none()
        if fav:
            await session.delete(fav)
            await session.commit()
            return True
        return False

async def get_favorites(user_id: int):
    async with async_session() as session:
        stmt = select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc())
        result = await session.execute(stmt)
        return result.scalars().all()

# ---------- Настройка БД ----------
engine = create_async_engine(
    "sqlite+aiosqlite:///./data.db",
    echo=False,
    future=True,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)