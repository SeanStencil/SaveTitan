import os
import sys


script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
script_dir = parent_dir

expected_file = os.path.join(script_dir, 'savetitan.py')
portable_file = os.path.join(script_dir, 'portable.txt')

if not os.path.isfile(expected_file):
    print(f"Expected to find savetitan.py in directory: {script_dir}")
    sys.exit(1)

if sys.platform == "win32":
    if os.path.isfile(portable_file):
        user_config_file = os.path.join(script_dir, "user")
        global_config_file = os.path.join(script_dir, "global.json")
        game_overrides_config_file = os.path.join(script_dir, "game_overrides.json")
    else:
        user_config_file = os.path.join(os.getenv('APPDATA'), "SaveTitan/user")
        global_config_file = os.path.join(os.getenv('APPDATA'), "SaveTitan/global.json")
        game_overrides_config_file = os.path.join(script_dir, "game_overrides.json")
else:
    profiles_config_file = os.path.join(script_dir, "user/profiles")
    global_config_file = os.path.join(script_dir, "global.json")
    game_overrides_config_file = os.path.join(script_dir, "game_overrides.json")