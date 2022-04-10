import os
import datetime
import logging
import traceback
from contextlib import suppress
import discord
from dotenv import load_dotenv
import youtube_dl
import asyncio

VERSION = '0.1.0'
NAME = 'Discord Bot'

# Logger setup
with suppress(FileExistsError):
  os.makedirs('logs')
  print('Created logs folder')

log = logging.getLogger('main')
log.setLevel(logging.DEBUG)

filename = datetime.datetime.now().strftime('%Y-%m-%d') + '.log'
file = logging.FileHandler(os.path.join('logs', filename))
file.setLevel(logging.DEBUG)
fileformat = logging.Formatter('%(asctime)s:%(levelname)s: %(message)s')
file.setFormatter(fileformat)
log.addHandler(file)

stream = logging.StreamHandler()
stream.setLevel(logging.DEBUG)
streamformat = logging.Formatter('%(asctime)s:%(levelname)s: %(message)s')
stream.setFormatter(fileformat)
log.addHandler(stream)
# End of logger setup

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
client = discord.Client()

help_message = '''Bot commands
!p, !з - play/pause
!s, !ы, !skip - skip current song
!d, !в, !disconnect - disconnects bot from a voice channel
'''

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
  'format': 'bestaudio/best',
  'restrictfilenames': True,
  'noplaylist': True,
  'nocheckcertificate': True,
  'ignoreerrors': False,
  'logtostderr': False,
  'quiet': True,
  'no_warnings': True,
  'default_search': 'auto',
  'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
  'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
  def __init__(self, source, *, data, volume=0.5):
    super().__init__(source, volume)
    self.data = data
    self.title = data.get('title')
    self.url = ""

  @classmethod
  async def from_url(cls, url, *, loop=None, stream=True):
    loop = loop or asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
    if 'entries' in data:
      # take first item from a playlist
      data = data['entries'][0]
    filename = data['title'] if stream else ytdl.prepare_filename(data)
    return data['url'], data['title']

@client.event
async def on_ready():
  log.info(f'{client.user.name} has connected to Discord!')

@client.event
async def join(message):
  voice_client = message.guild.voice_client
  if voice_client and voice_client.is_connected():
    return
  if message.author.voice:
    channel = message.author.voice.channel
    await channel.connect()
  else:
    response = f'{message.author.name} is not connected to a voice channel'
    await message.channel.send(response)

@client.event
async def disconnect(message):
  voice_client = message.guild.voice_client
  if voice_client and voice_client.is_connected():
    await voice_client.disconnect()
  else:
    response = f'{client.user.name} is not connected to a voice channel'
    await message.channel.send(response)

@client.event
async def play(message):
  await join(message)
  ffmpeg_exec_name = 'ffmpeg'
  url = message.content
  server = message.guild
  voice_client = server.voice_client
  if voice_client and voice_client.is_connected():
    url, title = await YTDLSource.from_url(url)
    voice_client.play(discord.FFmpegPCMAudio(executable=ffmpeg_exec_name, source=url))
    await message.channel.send(f'**Now playing:** {title}')

@client.event
async def skip(message):
  server = message.guild
  voice_client = server.voice_client
  if voice_client and voice_client.is_playing():
    voice_client.stop()
  else:
    response = f'Nothing is playing right now'
    await message.channel.send(response)

@client.event
async def toggle_playback(message):
  server = message.guild
  voice_client = server.voice_client
  if voice_client:
    if voice_client.is_playing():
      voice_client.pause()
    else:
      voice_client.resume()
  else:
    response = f'Nothing is playing right now'
    await message.channel.send(response)

@client.event
async def on_message(message):
  if message.author == client.user:
      return

  if message.content.lower() in ['!h', '!help']:
    response = help_message
    await message.channel.send(response)
  # elif message.content.lower() in ['!j', '!о', '!join']:
  #   await join(message)
  elif message.content.lower() in ['!d', '!в','!disconnect']:
    await disconnect(message)
  elif message.content.lower() in ['!s', '!ы', '!skip']:
    await skip(message)
  elif message.content.lower() in ['!p', '!з']:
    await toggle_playback(message)
  else:
    await play(message)

@client.event
async def on_error(event, *args, **kwargs):
  log.error((traceback.format_exc()))

if __name__ == '__main__':
  log.info('=============================')
  log.info(f'{NAME} v{VERSION} start')
  client.run(TOKEN)
