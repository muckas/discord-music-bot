import os
import datetime
import logging
import traceback
from contextlib import suppress
import discord
from dotenv import load_dotenv

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

@client.event
async def on_ready():
  log.info(f'{client.user.name} has connected to Discord!')

@client.event
async def join(message):
  if not message.author.voice:
    response = f'{message.author.name} is not connected to a voice channel'
    await message.channel.send(response)
  else:
    channel = message.author.voice.channel
    await channel.connect()

@client.event
async def disconnect(message):
  voice_client = message.guild.voice_client
  if voice_client and voice_client.is_connected():
    await voice_client.disconnect()
  else:
    response = f'{client.user.name} is not connected to a voice channel'
    await message.channel.send(response)

@client.event
async def on_message(message):
  if message.author == client.user:
      return

  if message.content.lower() in ['!j', '!join',]:
    await join(message)
  elif message.content.lower() in ['!d', '!disconnect',]:
    await disconnect(message)
  else:
    response = message.content
    await message.channel.send(response)

@client.event
async def on_error(event, *args, **kwargs):
  log.error((traceback.format_exc()))

if __name__ == '__main__':
  log.info('=============================')
  log.info(f'{NAME} v{VERSION} start')
  client.run(TOKEN)
