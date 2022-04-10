import os
import sys
import datetime
import logging
import traceback
from contextlib import suppress
import discord
import youtube_dl
import asyncio
import db
import constants

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

log.info('=============================')
log.info(f'{NAME} v{VERSION} start')

try:
  params = db.init('params')
  serverdb = db.init('serverdb')

  TOKEN = params['discord_token']
  if not TOKEN:
    log.error('Discord token is empty')
    sys.exit(2)
  client = discord.Client()
except Exception as e:
  log.error((traceback.format_exc()))

help_message = '''Bot commands
!p, !з - play/pause
!s, !ы, !skip - skip current song
!q, !й, !queue - show queue
!c, !с, !clear - clear queue
!d, !в, !disconnect - disconnects bot from a voice channel
!music-reg - register channel for music
!music-unreg - unregister channel for music
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
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
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
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
    voice_client = message.guild.voice_client
    if voice_client and voice_client.is_connected():
      await voice_client.disconnect()
    else:
      response = f'{client.user.name} is not connected to a voice channel'
      await message.channel.send(response)

def after_song(message):
  server_id = str(message.guild.id)
  queue = serverdb[server_id]['music_queue']
  try:
    if len(queue) > 1:
      next_url = serverdb[server_id]['music_queue'][1]['url']
      voice_client = message.guild.voice_client
      voice_client.play(discord.FFmpegPCMAudio(source=next_url), after=lambda e: after_song(message))
      serverdb[server_id]['music_queue'].pop(0)
      db.write('serverdb', serverdb)
    else:
      next_url, next_title = serverdb[server_id]['music_queue'].pop(0)
      db.write('serverdb', serverdb)
  except IndexError:
    pass

@client.event
async def play(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  queue = serverdb[server_id]['music_queue']
  if in_music_channel(server_id, channel_id):
    search = message.content
    url, title = await YTDLSource.from_url(search)
    serverdb[server_id]['music_queue'].append({'url':url, 'title':title})
    db.write('serverdb', serverdb)
    voice_client = message.guild.voice_client
    if voice_client and voice_client.is_playing():
      await message.channel.send(f'**Added to queue:** {title}')
    else:
      await join(message)
      voice_client = message.guild.voice_client
      if voice_client and voice_client.is_connected():
        voice_client.play(discord.FFmpegPCMAudio(source=url), after=lambda e:after_song(message))
        await message.channel.send(f'**Now playing:** {title}')

@client.event
async def skip(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
    server = message.guild
    voice_client = server.voice_client
    if voice_client and voice_client.is_playing():
      voice_client.stop()
      after_song(message)
    else:
      response = f'Nothing is playing right now'
      await message.channel.send(response)

@client.event
async def toggle_playback(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
    server = message.guild
    voice_client = server.voice_client
    if voice_client:
      if voice_client.is_playing():
        voice_client.pause()
      elif voice_client.is_paused():
        voice_client.resume()
      else:
        response = f'Nothing is playing right now'
        await message.channel.send(response)
    else:
      response = f'Nothing is playing right now'
      await message.channel.send(response)

@client.event
async def show_queue(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  queue = serverdb[server_id]['music_queue']
  if queue:
    response = f'***Current queue***'
    response += f'\n**Now playing**: {queue[0]["title"]}'
    n = 0
    for song in queue:
      if n > 0:
        response += f'\n{n}: {song["title"]}'
      n += 1
  else:
    response = f'Queue is empty'
  await message.channel.send(response)

@client.event
async def clear_queue(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  serverdb[server_id]['music_queue'] = []
  db.write('serverdb', serverdb)
  response = f'Queue has been cleared'
  await message.channel.send(response)

@client.event
async def music_register(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  serverdb[server_id]['music_channel'] = channel_id
  db.write('serverdb', serverdb)
  response = f'Channel "{message.channel.name}" is now a music channel'
  await message.channel.send(response)

@client.event
async def music_unregister(message):
  server_id = str(message.guild.id)
  serverdb[server_id]['music_channel'] = None
  db.write('serverdb', serverdb)
  response = f'Channel "{message.channel.name}" is no longer a music channel'
  await message.channel.send(response)

@client.event
async def on_message(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  check_serverdb(server_id)
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
  elif message.content.lower() in ['!q', '!й', '!queue']:
    await show_queue(message)
  elif message.content.lower() in ['!c', '!с', '!clear']:
    await clear_queue(message)
  elif message.content.lower() == '!music-reg':
    await music_register(message)
  elif message.content.lower() == '!music-unreg':
    await music_unregister(message)
  else:
    if in_music_channel(server_id, channel_id):
      await play(message)

@client.event
async def on_error(event, *args, **kwargs):
  log.error((traceback.format_exc()))

def check_serverdb(server_id):
  if str(server_id) not in serverdb:
    serverdb.update({str(server_id):constants.get_default_server()})
    db.write('serverdb', serverdb)

def in_music_channel(server_id, channel_id):
  return str(channel_id) == serverdb[str(server_id)]['music_channel']

if __name__ == '__main__':
  try:
    client.run(TOKEN)
  except Exception as e:
    log.error((traceback.format_exc()))
