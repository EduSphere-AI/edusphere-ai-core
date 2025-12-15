import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from models.database import Base, DATABASE_URL

async def reset_database():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Database reset successfully.")

if __name__ == "__main__":
    asyncio.run(reset_database())
