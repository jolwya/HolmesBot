import asyncio
import discord
from discord.ext import commands

import database
from config import DISCORD_TOKEN
from views.report_button import ReportButtonView
from views.review_view import ReviewView

COGS = [
    "cogs.tickets",
    "cogs.database_posts",
    "cogs.vouching",
    "cogs.help",
]

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    # Re-register persistent views so buttons survive restarts
    bot.add_view(ReportButtonView())

    # Re-register all open review views by scanning the DB
    # (We use a generic persistent view that decodes report/ticket IDs from custom_id)
    # This works because our buttons have fixed custom_ids and we handle logic in callbacks
    # For full per-report state, we'd need to store open review message IDs and restore them here.

    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"⚠️  Sync failed: {e}")

    print("🤖 Bot is ready.")


async def main():
    await database.init_db()
    print("🗄️  Database initialised.")

    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"  ✓ Loaded {cog}")
            except Exception as e:
                print(f"  ✗ Failed to load {cog}: {e}")

        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())