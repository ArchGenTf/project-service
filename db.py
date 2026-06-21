import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("project_service_database_manager")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "archgen_db")

class DatabaseManager:
    client: AsyncIOMotorClient = None
    db = None

    async def connect_to_database(self):
        """Creates an asynchronous connection to MongoDB database for project service."""
        import asyncio
        logger.info(f"Connecting to MongoDB at: {MONGO_URI}")
        try:
            self.client = AsyncIOMotorClient(
                MONGO_URI,
                maxPoolSize=50,
                minPoolSize=10,
                serverSelectionTimeoutMS=2000,
                socketTimeoutMS=30000,
            )
            self.db = self.client[DATABASE_NAME]
            
            retries = 5
            for i in range(retries):
                try:
                    await self.client.admin.command('ping')
                    logger.info("Successfully established connection with MongoDB.")
                    return
                except Exception as ping_err:
                    if i < retries - 1:
                        logger.warning(f"Failed to connect to MongoDB on attempt {i+1}/{retries}: {ping_err}. Retrying in 2 seconds...")
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"Failed to connect to MongoDB after {retries} attempts: {ping_err}. Project persistence disabled (Offline Mock Mode).")
                        self.client = None
                        self.db = None
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB client: {e}. Project persistence disabled (Offline Mock Mode).")
            self.client = None
            self.db = None

    async def close_database_connection(self):
        """Closes connection to MongoDB for project service."""
        if self.client:
            self.client.close()
            logger.info("MongoDB client connection closed.")

# Export a singleton instance
db_manager = DatabaseManager()

def get_database():
    """Dependency resolver returning the database context for project service."""
    return db_manager.db
