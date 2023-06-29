import os
import sys

script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
expected_file_py = os.path.join(script_dir, 'savetitan.py')
expected_file_pyw = os.path.join(script_dir, 'savetitan.pyw')
portable_file = os.path.join(script_dir, 'portable.txt')
python_exe_path = sys.executable

if not (os.path.isfile(expected_file_py) or os.path.isfile(expected_file_pyw)):
    print(f"Expected to find savetitan.py or savetitan.pyw in directory: {script_dir}")
    sys.exit(1)

if sys.platform == "win32":
    if os.path.isfile(portable_file):
        user_config_file = os.path.join(script_dir, "user")
        global_config_file = os.path.join(script_dir, "global.json")
        game_overrides_config_file = os.path.join(script_dir, "game_overrides.json")
    else:
        user_config_file = os.path.join(os.getenv('APPDATA'), "SaveTitan/user")
        global_config_file = os.path.join(os.getenv('APPDATA'), "SaveTitan/global.json")
        game_overrides_config_file = os.path.join(os.getenv('APPDATA'), "SaveTitan/game_overrides.json")
else:
    user_config_file = os.path.join(script_dir, "user")
    global_config_file = os.path.join(script_dir, "global.json")
    game_overrides_config_file = os.path.join(script_dir, "game_overrides.json")
