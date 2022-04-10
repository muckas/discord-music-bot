import os
import json
import logging
import shutil
import datetime
from contextlib import suppress

log = logging.getLogger('main')

def archive(filename='backup', folder='backup', max_backups=0):
  log.info('Backing up db...')
  with suppress(FileExistsError):
    os.makedirs(folder)
    log.info(f'Created {folder} folder')
  date = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
  path = os.path.join(folder, f'{filename}-{date}')
  shutil.make_archive(base_name=path, format='zip', base_dir='db', logger=log)
  log.info(f'Backup complete: {path}')
  if max_backups:
    while True: # Remove old files
      files = os.listdir(folder)
      files = [os.path.join(folder, f) for f in files] # add path to each file
      files.sort(key=lambda x: os.path.getmtime(x))
      for file in files:
        if os.path.isdir(file):
          files.remove(file)
      if len(files) > max_backups:
        log.info(f'Found more than {max_backups} backups, removing {files[0]}')
        os.remove(files[0])
      else:
        break

def init(name):
  with suppress(FileExistsError):
    os.makedirs('db')
    log.info('Created db folder')
  log.debug(f'Initializing {name}.json')
  if os.path.isfile(os.path.join('db', f'{name}.json')):
    log.debug(f'{name}.json exists')
    return read(name)
  else:
    defaults = read(f'{name}.defaults')
    if defaults:
      log.debug(f'Writing defaults to {name}.json')
      write(name, defaults)
      return defaults
    else:
      log.debug(f'Writing empty {name}.json')
      with open(os.path.join('db',f'{name}.json'), 'x') as f:
        json_obj = {}
        json_obj = json.dumps(defaults, indent=2)
        f.write(json_obj)
    return read(name)

def read(name):
  log.debug(f'Reading from {name}.json')
  try:
    with open(os.path.join('db',f'{name}.json'), 'r') as f:
      content = json.load(f)
    if content:
      return content
    else:
      return {}
  except FileNotFoundError:
    log.debug(f'{name}.json does not exist')
    return None

def write(name, content):
  log.debug(f'Writing to {name}.json')
  with open(os.path.join('db',f'{name}.json'), 'w') as f:
    json_obj = json.dumps(content, indent=2)
    f.write(json_obj)
