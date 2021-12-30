#!/usr/bin/env python
"""
Copyright (C) 2022 David Vallee Delisle <me@dvd.dev>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

### Description:

This script will remove entries from the Home Assistant restore state.

This is meant to remove "hilo_energy" entities as some orphan states
might cause issues with the utility meters in Home Assistant.

A backup will be taken before writing anything to the file.

Make sure that Home Assistant is stopped before running the script

"""

from datetime import datetime
import json
from os import access, W_OK, R_OK
from os.path import isfile
from shutil import copy2
import sys

if len(sys.argv) < 2:
    print(f"{sys.argv[0]} <core.restore_state file path>")
    sys.exit(1)

state_file = sys.argv[1]
if (not isfile(state_file) or
    not access(state_file, R_OK) or
    not access(state_file, W_OK)):
    print(f"{state_file} must be read and writeable")
    sys.exit(1)

now = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_file = f"{state_file}.{now}"
print(f"Working on {state_file}, backuping as {backup_file}")
copy2(state_file, backup_file)

with open(state_file, "r") as f:
    states = json.loads(f.read())

data = states.get("data")
new_states = []

for k in data:
    if "hilo_energy" in k['state']['entity_id']:
        continue
    new_states.append(k)

states["data"] = new_states
with open(state_file, "w") as f:
    json.dump(states, f, indent=4)
