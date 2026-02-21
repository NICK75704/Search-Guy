import discord
import asyncio
import os
import json
from datetime import timezone
import time

TOKEN = "BOT_KEY"
EXPORT_DIR = "discord_exports"
STATE_FILE = "export_state.json"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

client = discord.Client(intents=intents)


def sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).rstrip()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


async def safe_fetch_history(channel, **kwargs):
    """Safely fetch message history with rate limit handling"""
    max_retries = 5
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            async for message in channel.history(**kwargs):
                yield message
            return  # Success, exit the retry loop
        except discord.RateLimited as e:
            print(f"Rate limited! Waiting {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        except discord.Forbidden:
            print(f"Access forbidden for channel {channel.name}")
            return
        except Exception as e:
            print(f"Unexpected error fetching history: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

    state = load_state()

    for guild in client.guilds:
        print(f"\nChecking server: {guild.name}")

        guild_dir = os.path.join(EXPORT_DIR, sanitize_filename(guild.name))
        os.makedirs(guild_dir, exist_ok=True)

        for channel in guild.text_channels:
            perms = channel.permissions_for(guild.me)
            if not perms.read_message_history:
                print(f"Skipping {channel.name} (no permission)")
                continue

            channel_key = f"{guild.id}-{channel.id}"
            last_id = state.get(channel_key)

            filename = os.path.join(
                guild_dir,
                f"{sanitize_filename(channel.name)}.txt"
            )

            print(f"Updating #{channel.name}")

            new_last_id = last_id
            message_count = 0

            with open(filename, "a", encoding="utf-8") as f:

                history_kwargs = {
                    "limit": None,
                    "oldest_first": True
                }

                if last_id:
                    history_kwargs["after"] = discord.Object(id=int(last_id))

                try:
                    async for message in safe_fetch_history(channel, **history_kwargs):
                        timestamp = message.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                        author = f"{message.author.name}#{message.author.discriminator}"
                        content = message.content.replace("\n", " ")

                    f.write(f"[{timestamp}] {author}: {content}\n")

                        if message.attachments:
                            for attachment in message.attachments:
                                f.write(f"    [Attachment] {attachment.url}\n")

                        if message.embeds:
                            f.write("    [Embed]\n")

                        new_last_id = message.id
                        message_count += 1
                        
                        # Add a small delay between messages to be respectful
                        await asyncio.sleep(0.05)

                except Exception as e:
                    print(f"Error fetching messages from {channel.name}: {e}")
                    continue

            if message_count > 0:
                state[channel_key] = str(new_last_id)
                save_state(state)
                print(f"  Added {message_count} new messages")
            else:
                print("  No new messages")

            # Polite delay between channels
            await asyncio.sleep(1)

    print("\nIncremental update complete.")
    await client.close()


client.run(TOKEN)
