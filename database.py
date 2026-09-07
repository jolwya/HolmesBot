import aiosqlite
import asyncio
from datetime import datetime

DB_PATH = "scambot.db"

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id             BIGINT PRIMARY KEY,
    database_channel_id  BIGINT,
    database_webhook_url TEXT,
    archive_category_id  BIGINT,
    archive_channel_id   BIGINT
);

CREATE TABLE IF NOT EXISTS guild_staff_roles (
    guild_id BIGINT NOT NULL,
    role_id  BIGINT NOT NULL,
    PRIMARY KEY (guild_id, role_id)
);

CREATE TABLE IF NOT EXISTS tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id  BIGINT NOT NULL,
    reporter_id BIGINT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'awaiting_template',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id         INTEGER REFERENCES tickets(id),
    reporter_id       BIGINT,
    roblox_username   TEXT NOT NULL,
    discord_username  TEXT NOT NULL,
    discord_id        TEXT,
    reason            TEXT,
    proof_link        TEXT NOT NULL,
    reviewed_by       BIGINT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scammer_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    roblox_username  TEXT,
    discord_username TEXT,
    report_count     INTEGER NOT NULL DEFAULT 1,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vouches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_id     BIGINT NOT NULL,
    vouched_for_id BIGINT NOT NULL,
    reason         TEXT,
    proof_url      TEXT,
    points         INTEGER NOT NULL DEFAULT 1,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(voucher_id, vouched_for_id)
);

CREATE TABLE IF NOT EXISTS channel_vouches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id       BIGINT NOT NULL,
    channel_id     BIGINT NOT NULL,
    message_id     BIGINT NOT NULL UNIQUE,
    voucher_id     BIGINT NOT NULL,
    vouched_for_id BIGINT NOT NULL,
    vouch_type     TEXT NOT NULL DEFAULT 'normal',
    proof_url      TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auction_manager_roles (
    guild_id BIGINT NOT NULL,
    role_id  BIGINT NOT NULL,
    PRIMARY KEY (guild_id, role_id)
);

CREATE TABLE IF NOT EXISTS auction_blacklist (
    guild_id   BIGINT NOT NULL,
    user_id    BIGINT NOT NULL,
    reason     TEXT,
    added_by   BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS auctions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id             BIGINT NOT NULL,
    channel_id           BIGINT NOT NULL,
    message_id           BIGINT NOT NULL,
    item_name            TEXT NOT NULL,
    description          TEXT,
    starting_bid         INTEGER NOT NULL DEFAULT 0,
    min_increment        INTEGER NOT NULL DEFAULT 1,
    highest_bid          INTEGER NOT NULL DEFAULT 0,
    highest_bidder_id    BIGINT,
    is_highest_anonymous INTEGER NOT NULL DEFAULT 0,
    allow_anonymous      INTEGER NOT NULL DEFAULT 1,
    end_time             TIMESTAMP NOT NULL,
    status               TEXT NOT NULL DEFAULT 'active',
    created_by           BIGINT NOT NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auction_bids (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_id   INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
    bidder_id    BIGINT NOT NULL,
    amount       INTEGER NOT NULL,
    is_anonymous INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES)
        await db.commit()

        # Schema migrations
        async with db.execute("PRAGMA table_info(guild_config)") as cur:
            cols = [row[1] for row in await cur.fetchall()]
            if "archive_channel_id" not in cols:
                await db.execute("ALTER TABLE guild_config ADD COLUMN archive_channel_id BIGINT")

        async with db.execute("PRAGMA table_info(reports)") as cur:
            cols = [row[1] for row in await cur.fetchall()]
            if "reporter_id" not in cols:
                await db.execute("ALTER TABLE reports ADD COLUMN reporter_id BIGINT")
            if "reason" not in cols:
                await db.execute("ALTER TABLE reports ADD COLUMN reason TEXT")

        async with db.execute("PRAGMA table_info(scammer_entries)") as cur:
            cols = [row[1] for row in await cur.fetchall()]
            if "created_at" not in cols:
                await db.execute("ALTER TABLE scammer_entries ADD COLUMN created_at TIMESTAMP")
                await db.execute("UPDATE scammer_entries SET created_at = last_updated WHERE created_at IS NULL")

        async with db.execute("PRAGMA table_info(vouches)") as cur:
            cols = [row[1] for row in await cur.fetchall()]
            if "proof_url" not in cols:
                await db.execute("ALTER TABLE vouches ADD COLUMN proof_url TEXT")

        await db.commit()


# ── Guild Config Helpers ───────────────────────────────────────────────────────

async def get_guild_config(guild_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def set_database_config(guild_id: int, channel_id: int, webhook_url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO guild_config (guild_id, database_channel_id, database_webhook_url) 
               VALUES (?, ?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET 
               database_channel_id=excluded.database_channel_id, 
               database_webhook_url=excluded.database_webhook_url""",
            (guild_id, channel_id, webhook_url)
        )
        await db.commit()


async def set_archive_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO guild_config (guild_id, archive_channel_id) 
               VALUES (?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET 
               archive_channel_id=excluded.archive_channel_id""",
            (guild_id, channel_id)
        )
        await db.commit()


# ── Staff Roles Helpers ────────────────────────────────────────────────────────

async def add_staff_role(guild_id: int, role_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO guild_staff_roles (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id)
        )
        await db.commit()


async def remove_staff_role(guild_id: int, role_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM guild_staff_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id)
        )
        await db.commit()


async def get_staff_roles(guild_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT role_id FROM guild_staff_roles WHERE guild_id = ?", (guild_id,)) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


# ── Ticket Helpers ─────────────────────────────────────────────────────────────

async def create_ticket(channel_id: int, reporter_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO tickets (channel_id, reporter_id) VALUES (?, ?)",
            (channel_id, reporter_id),
        )
        await db.commit()
        return cursor.lastrowid


async def get_ticket_by_channel(channel_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_ticket_status(ticket_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        await db.commit()


# ── Report Helpers ─────────────────────────────────────────────────────────────

async def save_report(ticket_id: int, reporter_id: int, roblox: str, discord_user: str, discord_id: str, reason: str, proof: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO reports (ticket_id, reporter_id, roblox_username, discord_username, discord_id, reason, proof_link) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, reporter_id, roblox, discord_user, discord_id, reason, proof),
        )
        await db.commit()
        return cursor.lastrowid


async def get_report(report_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def approve_report(report_id: int, reviewed_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reports SET reviewed_by = ? WHERE id = ?", (reviewed_by, report_id))
        await db.commit()


# ── Scammer Entry Helpers ──────────────────────────────────────────────────────

async def upsert_scammer(roblox: str, discord_user: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM scammer_entries WHERE roblox_username = ? OR discord_username = ?", 
            (roblox, discord_user)
        )
        existing = await cur.fetchone()
        
        if existing:
            await db.execute(
                "UPDATE scammer_entries SET report_count = report_count + 1, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                (existing["id"],)
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM scammer_entries WHERE id = ?", (existing["id"],))
            return dict(await cur.fetchone())
        else:
            cur = await db.execute(
                """INSERT INTO scammer_entries (roblox_username, discord_username, report_count, created_at, last_updated) 
                   VALUES (?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (roblox, discord_user)
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM scammer_entries WHERE id = ?", (cur.lastrowid,))
            return dict(await cur.fetchone())


async def lookup_scammer(query: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM scammer_entries WHERE roblox_username LIKE ? OR discord_username LIKE ?", 
            (f"%{query}%", f"%{query}%")
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_all_scammers() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM scammer_entries ORDER BY report_count DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── Vouch Helpers ──────────────────────────────────────────────────────────────

async def add_vouch(voucher_id: int, vouched_for_id: int, reason: str, proof_url: str = None) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO vouches (voucher_id, vouched_for_id, reason, proof_url) VALUES (?, ?, ?, ?)",
                (voucher_id, vouched_for_id, reason, proof_url),
            )
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def get_vouches(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM vouches WHERE vouched_for_id = ? ORDER BY created_at DESC", (user_id,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_vouch_total(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COALESCE(SUM(points), 0) FROM vouches WHERE vouched_for_id = ?", (user_id,)) as cur:
            return (await cur.fetchone())[0]


async def remove_vouch(vouched_for_id: int, voucher_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM vouches WHERE voucher_id = ? AND vouched_for_id = ?",
            (voucher_id, vouched_for_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def clear_all_vouches(vouched_for_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM vouches WHERE vouched_for_id = ?",
            (vouched_for_id,),
        )
        await db.commit()
        return cursor.rowcount


# ── Channel Vouch & Reputation Helpers ─────────────────────────────────────────

async def add_channel_vouch(guild_id: int, channel_id: int, message_id: int, voucher_id: int, vouched_for_id: int, vouch_type: str, proof_url: str = None) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO channel_vouches (guild_id, channel_id, message_id, voucher_id, vouched_for_id, vouch_type, proof_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (guild_id, channel_id, message_id, voucher_id, vouched_for_id, vouch_type, proof_url)
            )
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def get_user_reputation(guild_id: int, user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        # Channel normal vouches
        async with db.execute(
            "SELECT COUNT(*) FROM channel_vouches WHERE guild_id = ? AND vouched_for_id = ? AND vouch_type = 'normal'",
            (guild_id, user_id)
        ) as cur:
            normal_cnt = (await cur.fetchone())[0]

        # Channel middleman vouches
        async with db.execute(
            "SELECT COUNT(*) FROM channel_vouches WHERE guild_id = ? AND vouched_for_id = ? AND vouch_type = 'middleman'",
            (guild_id, user_id)
        ) as cur:
            mm_cnt = (await cur.fetchone())[0]

        # Slash command vouches
        async with db.execute(
            "SELECT COALESCE(SUM(points), 0) FROM vouches WHERE vouched_for_id = ?",
            (user_id,)
        ) as cur:
            slash_cnt = (await cur.fetchone())[0]

        total = normal_cnt + mm_cnt + slash_cnt
        return {
            "normal": normal_cnt,
            "middleman": mm_cnt,
            "slash": slash_cnt,
            "total": total
        }


async def get_reputation_leaderboard(guild_id: int, leaderboard_type: str = "total", limit: int = 10) -> list[dict]:
    """Get top users by reputation (total, normal, middleman, slash)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if leaderboard_type == "middleman":
            query = """
                SELECT vouched_for_id as user_id, COUNT(*) as score 
                FROM channel_vouches 
                WHERE guild_id = ? AND vouch_type = 'middleman'
                GROUP BY vouched_for_id 
                ORDER BY score DESC 
                LIMIT ?
            """
            async with db.execute(query, (guild_id, limit)) as cur:
                return [dict(r) for r in await cur.fetchall()]

        elif leaderboard_type == "normal":
            query = """
                SELECT vouched_for_id as user_id, COUNT(*) as score 
                FROM channel_vouches 
                WHERE guild_id = ? AND vouch_type = 'normal'
                GROUP BY vouched_for_id 
                ORDER BY score DESC 
                LIMIT ?
            """
            async with db.execute(query, (guild_id, limit)) as cur:
                return [dict(r) for r in await cur.fetchall()]

        elif leaderboard_type == "slash":
            query = """
                SELECT vouched_for_id as user_id, SUM(points) as score 
                FROM vouches 
                GROUP BY vouched_for_id 
                ORDER BY score DESC 
                LIMIT ?
            """
            async with db.execute(query, (limit,)) as cur:
                return [dict(r) for r in await cur.fetchall()]

        else: # Total combines channel_vouches and slash vouches
            query = """
                SELECT user_id, SUM(score) as score FROM (
                    SELECT vouched_for_id as user_id, COUNT(*) as score FROM channel_vouches WHERE guild_id = ? GROUP BY vouched_for_id
                    UNION ALL
                    SELECT vouched_for_id as user_id, SUM(points) as score FROM vouches GROUP BY vouched_for_id
                )
                GROUP BY user_id
                ORDER BY score DESC
                LIMIT ?
            """
            async with db.execute(query, (guild_id, limit)) as cur:
                return [dict(r) for r in await cur.fetchall()]


# ── Auction Helpers ────────────────────────────────────────────────────────────

async def add_auction_manager_role(guild_id: int, role_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO auction_manager_roles (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id)
        )
        await db.commit()


async def remove_auction_manager_role(guild_id: int, role_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM auction_manager_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id)
        )
        await db.commit()


async def get_auction_manager_roles(guild_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT role_id FROM auction_manager_roles WHERE guild_id = ?", (guild_id,)) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def add_auction_blacklist(guild_id: int, user_id: int, reason: str, added_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO auction_blacklist (guild_id, user_id, reason, added_by) 
               VALUES (?, ?, ?, ?)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET reason=excluded.reason, added_by=excluded.added_by""",
            (guild_id, user_id, reason, added_by)
        )
        await db.commit()


async def remove_auction_blacklist(guild_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM auction_blacklist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()
        return cur.rowcount > 0


async def is_auction_blacklisted(guild_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM auction_blacklist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)) as cur:
            return (await cur.fetchone()) is not None


async def get_auction_blacklist(guild_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM auction_blacklist WHERE guild_id = ? ORDER BY created_at DESC", (guild_id,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def create_auction(guild_id: int, channel_id: int, message_id: int, item_name: str, description: str, starting_bid: int, min_increment: int, allow_anonymous: bool, duration_seconds: int, created_by: int) -> int:
    end_time_str = datetime.utcfromtimestamp(datetime.utcnow().timestamp() + duration_seconds).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO auctions (guild_id, channel_id, message_id, item_name, description, starting_bid, min_increment, highest_bid, allow_anonymous, end_time, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, channel_id, message_id, item_name, description, starting_bid, min_increment, starting_bid, 1 if allow_anonymous else 0, end_time_str, created_by)
        )
        await db.commit()
        return cur.lastrowid


async def get_auction(auction_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_active_auctions() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM auctions WHERE status = 'active'") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def place_auction_bid(auction_id: int, bidder_id: int, amount: int, is_anonymous: bool) -> tuple[bool, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM auctions WHERE id = ?", (auction_id,)) as cur:
            auc = await cur.fetchone()
            if not auc:
                return False, "Auction not found."
            if auc["status"] != "active":
                return False, "This auction is no longer active."

            min_required = auc["highest_bid"] + (auc["min_increment"] if auc["highest_bidder_id"] else 0)
            if amount < min_required:
                return False, f"Bid must be at least R$ {min_required:,}."

            # Update highest bid
            await db.execute(
                """UPDATE auctions SET highest_bid = ?, highest_bidder_id = ?, is_highest_anonymous = ? WHERE id = ?""",
                (amount, bidder_id, 1 if is_anonymous else 0, auction_id)
            )

            # Record bid history
            await db.execute(
                """INSERT INTO auction_bids (auction_id, bidder_id, amount, is_anonymous) VALUES (?, ?, ?, ?)""",
                (auction_id, bidder_id, amount, 1 if is_anonymous else 0)
            )

            await db.commit()
            return True, "Bid placed successfully!"


async def get_auction_bid_history(auction_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM auction_bids WHERE auction_id = ? ORDER BY amount DESC, created_at DESC LIMIT ?", (auction_id, limit)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def update_auction_message_id(auction_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE auctions SET message_id = ? WHERE id = ?", (message_id, auction_id))
        await db.commit()


async def set_auction_status(auction_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE auctions SET status = ? WHERE id = ?", (status, auction_id))
        await db.commit()
