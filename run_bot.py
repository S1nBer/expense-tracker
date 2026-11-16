import asyncio
from dotenv import load_dotenv

load_dotenv()

from app.bot import main

if __name__ == "__main__":
    asyncio.run(main())