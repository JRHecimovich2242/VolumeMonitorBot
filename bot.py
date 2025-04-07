import discord
import asyncio
import sounddevice as sd
import numpy as np
import time
import json
import os
from config import TOKEN, CHANNEL_ID, USER_TO_MONITOR


# ========== CONFIG ==========

VOLUME_THRESHOLD = 0.05
COOLDOWN_SECONDS = 10
COUNT_FILE = "volume_count.json"

# =============================

intents = discord.Intents.default()
client = discord.Client(intents=intents)

volume_exceed_count = 0
last_sent_time = 0

# Load the count from a file
def load_count():
    global volume_exceed_count
    if os.path.exists(COUNT_FILE):
        try:
            with open(COUNT_FILE, "r") as f:
                data = json.load(f)
                volume_exceed_count = data.get("count", 0)
                print(f"📂 Loaded count: {volume_exceed_count}")
        except Exception as e:
            print(f"⚠️ Failed to load count: {e}")

# Save the count to a file
def save_count():
    try:
        with open(COUNT_FILE, "w") as f:
            json.dump({"count": volume_exceed_count}, f)
    except Exception as e:
        print(f"⚠️ Failed to save count: {e}")

# Send alert to channel
async def send_volume_alert(volume, count):
    channel = client.get_channel(CHANNEL_ID)
    
    if channel:
        await channel.send(
            f"⚠️ Loud input detected!\n"
            f"Volume: {volume:.3f}\n"
            f"Total spikes: {count}"
        )

# Microphone monitoring
async def volume_monitor():
    global volume_exceed_count, last_sent_time

    def callback(indata, frames, time_info, status):
        global volume_exceed_count, last_sent_time
        volume_norm = np.linalg.norm(indata)
    
        # 🔊 Print the volume live to the console
        print(f"Current volume: {volume_norm:.5f}", end="\r")
        if volume_norm > 0:
            db = 20 * np.log10(volume_norm)
            print(f"Volume: {volume_norm:.5f} | {db:.2f} dB", end="\r")
        else:
            print("Volume: 0.00000 | -inf dB         ", end="\r")

        if volume_norm > VOLUME_THRESHOLD:
            now = time.time()

            if now - last_sent_time >= COOLDOWN_SECONDS:
                volume_exceed_count += 1
                save_count()
                last_sent_time = now
                asyncio.run_coroutine_threadsafe(
                    send_volume_alert(volume_norm, volume_exceed_count),
                    client.loop
                )

    with sd.InputStream(callback=callback):
        await asyncio.Event().wait()

@client.event
async def on_ready():
    print(f"✅ Bot logged in as {client.user}")
    load_count()
    asyncio.create_task(volume_monitor())

client.run(TOKEN)