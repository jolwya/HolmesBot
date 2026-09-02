import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN          = os.getenv("DISCORD_TOKEN")
TICKETS_CATEGORY_ID    = int(os.getenv("TICKETS_CATEGORY_ID", 0))
MOD_ROLE_ID            = int(os.getenv("MOD_ROLE_ID", 0))
DATABASE_CHANNEL_ID    = int(os.getenv("DATABASE_CHANNEL_ID", 0))
