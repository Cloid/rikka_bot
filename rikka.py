from dotenv import load_dotenv
import os

import asyncio
import random
import requests

import discord
from discord.ext import commands

from collections import deque

import yt_dlp

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import re

# load env vars
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Spotify Developer App credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
redirect_uri = os.getenv("redirect_uri")

# define spotify scope
scope = "user-library-read user-read-playback-state user-modify-playback-state"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=SPOTIFY_CLIENT_ID,
                                                client_secret=SPOTIFY_CLIENT_SECRET,
                                                redirect_uri=redirect_uri,
                                                scope=scope))


# define cookies:
cookies = "cookies.txt"

description = '''WIP Music Bot for my server'''


# results = sp.search(q="Never Gonna Give You Up", type="track", limit=1)
# for track in results["tracks"]["items"]:
#     print(f"Track Name: {track['name']}")
#     print(f"Artist: {track['artists'][0]['name']}")
#     print(f"URL: {track['external_urls']['spotify']}")

# Bot Configuration
intents = discord.Intents.default()
intents.messages = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# storage programming
queue = deque()

# check to check if bot is playing
is_playing = False

@bot.event
async def on_ready():
    # Set bot status as a bio message
    activity = discord.Game("shitty music")  # You can customize the message here
    await bot.change_presence(activity=activity)


@bot.command()
async def join(ctx):
    await join_voice_channel(ctx)


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await clearQueue()
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I'm not in a voice channel!")

@bot.command()
async def play(ctx, url):
    if not await join_voice_channel(ctx):
        return

    url_type = await get_link_type(url)

    if url_type == "spotify":
        await ctx.send('spotify')
        await get_spotify_track_info(ctx, url)
        return

    if await check_youtubeurl(url) != False:

        # conditional for youtube videos link is valid
        # also conditional for spotify
        await addToQueue(ctx, url, True)

        if not is_playing:
                await play_next(ctx)
    else:
        await ctx.send("Invalid youtube url! Try a different url")

# @bot.command()
# async def test(ctx):
#     embed = discord.Embed(
#         color=discord.Color.dark_red(),
#         description="this is description",
#         title="this is title"
#     )
#     embed.set_footer(text="footer")
#     embed.set_author(name="author")
#
#     await ctx.send(embed=embed)

@bot.command()
async def skip(ctx):

    if ctx.voice_client and ctx.voice_client.is_playing():
        await ctx.send("Skipping current song.")
        ctx.voice_client.stop()
    else:
        await ctx.send("Not currently playing anything.")

@bot.command()
async def clear(ctx):
    await clearQueue()

@bot.command()
async def bump(ctx, url):
    if not await join_voice_channel(ctx):
        return

    await addToQueue(ctx, url, True)

    if not is_playing:
        await play_next(ctx)

@bot.command()
async def shuffle(ctx):
    global queue
    if queue:
        random.shuffle(queue)
        await ctx.send("Shuffled the queue!")
        # need to print queue
    else:
        await ctx.send("The queue is empty.")

# Helper functions

# Joins voice channel
async def join_voice_channel(ctx):
    if ctx.voice_client is None:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            await ctx.send(f"Joined {channel}!")
        else:
            await ctx.send("You need to be in voice channel to use this command!")
            return False
    return True

#  Plays the next available song
async  def play_next(ctx):
    global is_playing
    if queue:
        is_playing = True
        url = queue.popleft()
        await play_current_yt_song(ctx, url)
    else:
        is_playing = False
        await ctx.send("No more songs left in queue, leaving in 5 minutes.")

        await asyncio.sleep(10)

        if ctx.voice_client.is_connected() and is_playing is False:
            await ctx.voice_client.disconnect()

# plays current song via yt url
async def play_current_yt_song(ctx, url):


    ydl_opts = {
        "format" : "bestaudio/best",
        "noplaylist" : True, # Disable playlist
        "quiet": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info["url"]
            vc = ctx.voice_client

            def after_playing(error):
                asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop).result()

            # Play the audio with the after callback
            vc.play(
                discord.FFmpegPCMAudio(audio_url),
                after=after_playing,
            )
            vc.source = discord.PCMVolumeTransformer(vc.source)
            vc.source.volume = 0.5

            await ctx.send(f"Now playing: {info['title']}")

    except Exception as e:
        await ctx.send(f"An error occured: {e}")
        await ctx.send("Playing next song if available.")
        await play_next(ctx)

# handles whether to add on front or back of queue
async def addToQueue(ctx, url, addToBack):

    if addToBack is True:
        queue.append(url)
        await ctx.send(f"Added song to queue: {url}")
    else:
        queue.appendleft(url)
        await ctx.send(f"Bumped song to queue: {url}")

async def clearQueue():
    queue.clear()

async def check_youtubeurl(url):
    request = requests.get(url)
    return request.status_code == 200

async def get_link_type(url):
    # Regex patterns for spotify and youtube
    spotify_pattern = r"https?://open\.spotify\.com/.*"
    youtube_pattern = r"https?://(www\.)?(youtube\.com|youtu\.be)/.*"

    if re.match(spotify_pattern, url):
        return "spotify"
    elif re.match(youtube_pattern, url):
        return "youtube"
    else:
        return "unknown"

async def get_spotify_track_info(ctx, spotify_url):
    try:
        track_info = sp.track(spotify_url)
        track_name = track_info["name"]
        artists = [artist["name"] for artist in track_info["artists"]]
        artist_names_str = ", ".join(artists)
        search_query = f"{track_name} {artist_names_str}"

    # Search on YouTube
        ydl_opts = {'cookiefile': cookies,"format": "bestaudio/best", "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch:{search_query}", download=False)
            video_url = search_results["entries"][0]["url"]

        # Play the audio in Discord
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()
        ctx.voice_client.play(discord.FFmpegPCMAudio(video_url))
        await ctx.send(f"Now playing: {track_name} by {artist_names_str}")

    except Exception as e:
        await ctx.send(f"Error: {e}")

bot.run(DISCORD_TOKEN)