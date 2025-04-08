import discord
import asyncio
import sounddevice as sd
import numpy as np
import time
import json
import os
import random
from config import TOKEN, CHANNEL_ID, USER_ID_TO_MONITOR, GUILD_ID


# ========== CONFIG ==========

VOLUME_THRESHOLD = 97
DBFS_TO_SPL_OFFSET = 73.6
COOLDOWN_SECONDS = 5
COST_PER_VIOLATION = 1
COUNT_FILE = "volume_count.json"

# =============================

intents = discord.Intents.default()
client = discord.Client(intents=intents)

volume_exceed_count = 0
dollars_owed = 0
last_sent_time = 0
monitoring_enabled = False
audio_task = None


def random_line():
    try:
        with open("funnylines.txt", 'r') as file:
            lines = file.readlines()
            if lines:
                return random.choice(lines).strip()  # Remove trailing newline
            else:
                return ""
    except FileNotFoundError:
        return "File not found."
    # try:
    #     with open('funnylines.txt').read().splitlines() as lines:
    #         print(lines)
    #         line = random.choice(lines)
    #         return line
    # except Exception as e:
    #     print(f"⚠️ Failed to get a funny line: {e}")
    
# Load the count from a file
def load_count():
    global volume_exceed_count, dollars_owed
    if os.path.exists(COUNT_FILE):
        try:
            with open(COUNT_FILE, "r") as f:
                data = json.load(f)
                volume_exceed_count = data.get("count", 0)
                dollars_owed = data.get("cost", 0)
                print(f"📂 Loaded count: {volume_exceed_count}")
        except Exception as e:
            print(f"⚠️ Failed to load counts: {e}")

# Save the count to a file
def save_count():
    try:
        with open(COUNT_FILE, "w") as f:
            dict = {
                "count" : volume_exceed_count,
                "cost" : dollars_owed}
            json.dump(dict, f)
            
    except Exception as e:
        print(f"⚠️ Failed to save count: {e}")

# Send alert to channel
async def send_volume_alert(volume_norm, volume_dbfs, estimated_spl, count, price):
    channel = client.get_channel(CHANNEL_ID)
    
    if channel:
        await channel.send(
            f"⚠️ Loud input detected!\n"
            f"🔊 Volume Norm: `{volume_norm:.5f}`, "
            f"📉 dBFS: `{volume_dbfs:.2f}`,"
            f"📢 Estimated dB SPL: `~{estimated_spl:.2f}`\n"
            f"Total spikes: {count} ,"
            f"<@{USER_ID_TO_MONITOR}> ,  now owes ${price} to the Republican Party- "
            f"{random_line()}"
        )

# Send alert to channel
async def send_volume_alert_no_record(volume):
    channel = client.get_channel(CHANNEL_ID)
    
    if channel:
        await channel.send(
            f"⚠️ SUS input detected!\n"
            f"Volume: {volume:.3f} dB\n"
            # f"Total spikes: {count} \n"
            # f"J.R. now owes ${price} to the Republican Party- "
            # f"{random_line()}"
        )

# Microphone monitoring
async def volume_monitor():
    global volume_exceed_count, last_sent_time, dollars_owed, monitoring_enabled

    def callback(indata, frames, time_info, status):
        global volume_exceed_count, last_sent_time, dollars_owed
        volume_norm = np.linalg.norm(indata)    
        # 🔊 Print the volume live to the console
        print(f"Current volume: {volume_norm:.5f}", end="\r")
        if volume_norm > 0:
            db = 20 * np.log10(volume_norm)
            estimated_spl = db + DBFS_TO_SPL_OFFSET
            print(f"Volume: {volume_norm:.5f} | {db:.2f} dBFS | ~{estimated_spl:.2f} dB SPL", end="\r")

            if monitoring_enabled and estimated_spl > VOLUME_THRESHOLD:
                now = time.time()

                if now - last_sent_time >= COOLDOWN_SECONDS:
                    volume_exceed_count += 1
                    dollars_owed += COST_PER_VIOLATION
                    save_count()
                    last_sent_time = now
                    asyncio.run_coroutine_threadsafe(
                        send_volume_alert(volume_norm, db, estimated_spl, volume_exceed_count, dollars_owed),
                        client.loop
                    )
                        

    while True:
        if monitoring_enabled:
            with sd.InputStream(callback=callback):
                print("🎙️ Monitoring volume...")
                await asyncio.sleep(9999)  # Keeps the stream open
        else:
            await asyncio.sleep(1)

@client.event
async def on_ready():
    global monitoring_enabled
    print(f"{random_line()}")
    print(f"✅ Bot logged in as {client.user}")
    load_count()

    guild = client.get_guild(GUILD_ID)
    member = guild.get_member(USER_ID_TO_MONITOR)

    if member:
        if member.voice:
             monitoring_enabled = True
             print(f"👤 {member.name} is already in a voice channel. Starting volume monitor.")

    asyncio.create_task(volume_monitor())

@client.event
async def on_voice_state_update(member, before, after):
    global monitoring_enabled, audio_task

    if member.id != USER_ID_TO_MONITOR:
        return

    if after.channel is not None and before.channel != after.channel:
        # User joined a voice channel
        monitoring_enabled = True
        print(f"👤 {member.name} joined a voice channel. Starting volume monitor.")
        
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f"🎧 {member.name} is here! Time to listen for LOUD NOISES.")

        # Start the monitor task if it’s not already running
        if not audio_task:
            audio_task = asyncio.create_task(volume_monitor())

    elif after.channel is None:
        # User left all voice channels
        monitoring_enabled = False
        print(f"👤 {member.name} left the voice channel. Stopping volume monitor.")
        
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f"👋 {member.name} left. Monitoring paused.")

client.run(TOKEN)