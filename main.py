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

VERSION = '0.2.0'
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

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
  'logger': log,
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
    return data['url'], data['title'], data['duration'], data['is_live']

@client.event
async def on_ready():
  log.info(f'{client.user.name} has connected to Discord!')

@client.event
async def get_help(message):
  bot_name = client.user.name
  server_id = str(message.guild.id)
  music_channel_id = serverdb[server_id]['music_channel']
  if music_channel_id:
    music_channel_name = client.get_channel(int(music_channel_id))
  else:
    music_channel_name = 'Not registered'
  help_message = f'''**{bot_name} v{VERSION}**
Paste a link or a name of the song in music channel to add it to queue
Registered music channel: *{music_channel_name}*
***Bot commands***
!p, !з - play/pause
!s, !ы, !skip - skip current song
!q, !й, !queue - show queue
!c, !с, !clear - clear queue
!r, !к, !remove <track_number> - remove track from queue
!u, !г, !undo - remove last track from queue
!d, !в, !disconnect - disconnects bot from a voice channel
!music-reg - register channel for music
!music-unreg - unregister channel for music
'''

  response = help_message
  await message.channel.send(response)

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
  if len(queue) > 1:
    next_url = serverdb[server_id]['music_queue'][1]['url']
    voice_client = message.guild.voice_client
    if voice_client:
      voice_client.play(discord.FFmpegPCMAudio(source=next_url), after=lambda e: after_song(message))
      serverdb[server_id]['music_queue'].pop(0)
      db.write('serverdb', serverdb)
  elif len(queue) == 1:
    serverdb[server_id]['music_queue'].pop(0)
    db.write('serverdb', serverdb)

@client.event
async def add_to_queue(message):
  server_id = str(message.guild.id)
  queue = serverdb[server_id]['music_queue']
  search = message.content
  url, title, duration, is_live = await YTDLSource.from_url(search)
  if is_live:
    duration = 'Livestream'
  else:
    duration = str(datetime.timedelta(seconds=duration))
  serverdb[server_id]['music_queue'].append({'url':url, 'title':title, 'duration':duration})
  db.write('serverdb', serverdb)
  track_number = len(queue) - 1
  await message.channel.send(f'**Added to queue:** ***{track_number}*** {title} | ***{duration}***')

@client.event
async def remove_from_queue(message, track_number):
  server_id = str(message.guild.id)
  queue = serverdb[server_id]['music_queue']
  if queue:
    if track_number > 0:
      try:
        track = serverdb[server_id]['music_queue'].pop(track_number)
        db.write('serverdb', serverdb)
        await message.channel.send(
            f'**Removed from queue:** ***{track_number}*** {track["title"]} | ***{track["duration"]}***'
            )
      except IndexError:
        await message.channel.send(f'**Wrong track number: {track_number}**')
    else:
      await message.channel.send(f'**Track number can\'t be "{track_number}"**')
  else:
    await message.channel.send(f'**Queue is empty**')

@client.event
async def start_playing(message):
  server_id = str(message.guild.id)
  queue = serverdb[server_id]['music_queue']
  if queue:
    url = queue[0]['url']
    title = queue[0]['title']
    duration = queue[0]['duration']
    voice_client = message.guild.voice_client
    voice_client.play(discord.FFmpegPCMAudio(source=url), after=lambda e: after_song(message))
    await message.channel.send(f'**Now playing:** {title} | ***{duration}***')
  else:
    await message.channel.send(f'**Queue is empty**')

@client.event
async def play(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
    await add_to_queue(message)
    queue = serverdb[server_id]['music_queue']
    if len(queue) == 1:
      await join(message)
      await start_playing(message)

@client.event
async def skip(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
    queue = serverdb[server_id]['music_queue']
    if queue:
      current_song_title = queue[0]['title']
      response = f'**Skipped**: {current_song_title}'
      try:
        next_song_title = queue[1]['title']
        next_song_duration = queue[1]['duration']
        next_response = f'**Now playing:** {next_song_title} | ***{next_song_duration}***'
      except IndexError:
        next_response = f'**Queue is empty**'
      voice_client = message.guild.voice_client
      if voice_client:
        voice_client.stop() # executes after_song(message)
      else:
        serverdb[server_id]['music_queue'].pop(0)
        db.write('serverdb', serverdb)
      await message.channel.send(response)
      await message.channel.send(next_response)
    else:
      response = f'Queue is empty'
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
        await message.channel.send('Playback paused')
      elif voice_client.is_paused():
        voice_client.resume()
        await message.channel.send('Playback resumed')
      else:
        await start_playing(message)
    else:
      await join(message)
      await start_playing(message)

@client.event
async def show_queue(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
    queue = serverdb[server_id]['music_queue']
    if queue:
      response = f'***Current queue***'
      response += f'\n**Now playing**: {queue[0]["title"]} | ***{queue[0]["duration"]}***'
      n = 0
      for song in queue:
        if n > 0:
          response += f'\n***{n}***: {song["title"]} | ***{song["duration"]}***'
        n += 1
    else:
      response = f'Queue is empty'
    await message.channel.send(response)

@client.event
async def clear_queue(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
    serverdb[server_id]['music_queue'] = []
    db.write('serverdb', serverdb)
    response = f'Queue has been cleared'
    await message.channel.send(response)

@client.event
async def remove(message, track_number):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
    try:
      track_number = int(track_number)
      await remove_from_queue(message, track_number)
    except ValueError:
      await message.channel.send(f'**Wrong track number: {track_number}**')

async def undo(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  if in_music_channel(server_id, channel_id):
    queue = serverdb[server_id]['music_queue']
    if queue and len(queue) > 1:
      await remove_from_queue(message, len(queue)-1)
    else:
      await message.channel.send('Queue is empty')

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
  current_channel_id = serverdb[server_id]['music_channel']
  if current_channel_id:
    current_channel_name = client.get_channel(int(current_channel_id))
    serverdb[server_id]['music_channel'] = None
    db.write('serverdb', serverdb)
    response = f'Channel "{current_channel_name}" is no longer a music channel'
  else:
    response = f'Music channel is not registered'
  await message.channel.send(response)

@client.event
async def command_handler(prefix, message):
  if message.content[:1] == prefix:
    try:
      command, argument = message.content[1:].lower().split(' ')
    except ValueError:
      command = message.content[1:].lower()
      argument = None
    if command in ['h', 'help']:
      await get_help(message)
    # elif message.content.lower() in ['!j', '!о', '!join']:
    #   await join(message)
    elif command in ['d', 'в','disconnect']:
      await disconnect(message)
    elif command in ['s', 'ы', 'skip']:
      await skip(message)
    elif command in ['p', 'з']:
      await toggle_playback(message)
    elif command in ['q', 'й', 'queue']:
      await show_queue(message)
    elif command in ['c', 'с', 'clear']:
      await clear_queue(message)
    elif command in ['r', 'к', 'remove']:
      await remove(message, argument)
    elif command in ['u', 'г', 'undo']:
      await undo(message)
    elif command == 'music-reg':
      await music_register(message)
    elif command == 'music-unreg':
      await music_unregister(message)
    else:
      response = f'Unknown command "{command}"\nSee {prefix}h for help'
      await message.channel.send(response)
    return True
  else:
    return False

@client.event
async def on_message(message):
  server_id = str(message.guild.id)
  channel_id = str(message.channel.id)
  check_serverdb(server_id)
  if message.author == client.user:
      return
  if not await command_handler('!', message):
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
