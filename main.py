import os
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

client = discord.Client()

@client.event
async def on_ready():
  print(f'{client.user.name} has connected to Discord!')

@client.event
async def on_message(message):
  if message.author == client.user:
      return

  if message.content == 'Test':
    response = 'Test complete'
    await message.channel.send(response)
  else:
    response = message.content
    await message.channel.send(response)

client.run(TOKEN)
