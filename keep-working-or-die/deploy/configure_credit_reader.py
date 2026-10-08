"""Protect a separate OpenRouter management key. No API request or birth."""
import getpass
import os
from pathlib import Path
from kwod.store import atomic_write

if __name__=='__main__':
    if os.geteuid()!=0: raise ValueError('sudo_required')
    key=getpass.getpass('OpenRouter-Management-Key für Kontostandsabfrage (verdeckte Eingabe): ').strip()
    if not key or len(key)>1024 or any(ord(char)<33 or ord(char)>126 for char in key): raise ValueError('invalid_key')
    directory=Path('/etc/kwod-openrouter')
    if directory.is_symlink() or directory.stat().st_uid!=0: raise ValueError('unsafe_key_directory')
    atomic_write(directory/'credits.key',key.encode(),0o600)
    print('Management-Key geschützt gespeichert. Nicht an den Agenten weitergegeben; keine API-Anfrage und keine Birth.')
