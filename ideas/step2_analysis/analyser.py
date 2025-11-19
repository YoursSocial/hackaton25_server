import pandas as pd
import zipfile
import subprocess
import sys
from pathlib import Path

# Ensure repository root is on sys.path so `app` package is importable
# when running this script from the `data/` folder directly.
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.dashboard.parser import parser_iridium


def raw_parser(path_to_zip: str) -> None:
    """
    function to parse raw leocommon file
    input: parsed_input_file; output.bits file from leocommon system
    output: 
    """

    py = sys.executable  # python executable to use (default: current interpreter)
    # root folder to search for .bits files (default: repo `data/`)
    data_root: Path = Path(__file__).resolve().parents[1] / "data"
    # path to iridium-parser.py (default: repo `iridium-toolkit-master/iridium-parser.py`)
    parser_path: Path = Path(__file__).resolve().parents[1] / "iridium-toolkit-master" / "iridium-parser.py"

    job_folder_name = path_to_zip.replace('.zip', '')

    tmp_dir = data_root / "tmp" / job_folder_name
    tmp_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(data_root / path_to_zip, 'r') as zip_ref:
        zip_ref.extractall(tmp_dir)

    cwd: Path = tmp_dir


    bits_files = list(tmp_dir.glob("*.bits"))
    agg = False

    print(f"Found {len(bits_files)} .bits files")

    if len(bits_files) > 1:
        # Aggregate all .bits files into one
        agg = True

        output_path = tmp_dir / "tmp_output.bits"
        with open(output_path, "wb") as outfile:
            for bits_file in sorted(bits_files):
                with open(bits_file, "rb") as infile:
                    outfile.write(infile.read())
        print(f"Aggregated {len(bits_files)} files into {output_path}")
    else:
        print("Only 0 or 1 file found, no aggregation needed")



    cmd = [py, str(parser_path)]
    if agg:
        cmd.extend(["-p", (tmp_dir / "tmp_output.bits").name])
    else:
        cmd.extend(["-p", (cwd / "output.bits").name])

    print(f"Running: {cmd}  (cwd={cwd})")
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)

    if agg:
        # Remove temporary aggregated file
        remove_path = tmp_dir / "tmp_output.bits"
        remove_path.unlink()
        rename_path = tmp_dir / "tmp_output.parsed"
        rename_path.rename(tmp_dir / "output.parsed")

    # At Some point, delete tmp folder?

def metadata_parser(zip_folder_name: str) -> None:
    frames, time_lower, time_upper = parser_iridium.read_parsed_output(Path(f"data/tmp/{zip_folder_name}/"))

	# print(f"Time lower: {time_lower}")
	# print(f"Time upper: {time_upper}")
	# print(f"Time difference (s): {(time_upper - time_lower)}")
	
    if len(frames) != 0:
        type_dict = {'time': float, 'frame_type': str, 'signal_level': float, 'background_noise': float,
					 'snr': float}

    df = pd.DataFrame(data=frames)
    df = df.astype(dtype=type_dict)
    df = df.sort_values(by="time").reset_index()

    df.to_feather(f"data/tmp/{zip_folder_name}/output_df.feather")



def ira_parser(parsed_input_file):
    """
    function to parse ira alterts
    input: parsed_input_file; output.bits file from leocommon system after run through raw_parser function
    output: pandas dataframe containing IRA messages
    """
    iras = []
    for line in parsed_input_file:
        # filtering Iridium Ring Alerts (IRAs) and parse
        if line.startswith("IRA"):
            splitted = line.split()

            # extract and format fields
            # infos on iridium messages: https://github.com/muccc/iridium-toolkit/blob/master/FORMAT.md
            frame_type = splitted[0].strip(":")
            record_start_timestamp_s = int(splitted[1].removeprefix("p-"))
            offset_ms = float(splitted[2])
            timestamp_ms = record_start_timestamp_s * 1000 + offset_ms
            freq = int(splitted[3])
            confidence = int(splitted[4].strip("%"))
            signal_lvls = [float(x) for x in splitted[5].split("|")]
            length = splitted[6]
            direction = splitted[7]
            satid = splitted[8].removeprefix("sat:")
            beamid = splitted[9].removeprefix("beam:")
            sat_pos = [float(x) for x in splitted[10].removeprefix("xyz=(").removesuffix(")").split(",")]
            sat_pos_latlon = [float(x) for x in splitted[11].removeprefix("pos=(").removesuffix(")").split("/")]
            sat_alt = splitted[12].removeprefix("alt=")
            rai = splitted[13].removeprefix("RAI:")
            #skip unknown field
            bc_sb = splitted[15].split(":")[-1]
            parsers_field = [x for x in splitted[16:] if x !=  "{OK}" and not x.startswith(("FILL"))]  #format parser list and ignore last filler element

            iras.append([frame_type, record_start_timestamp_s, offset_ms, timestamp_ms, freq, confidence, signal_lvls, length, direction, satid, beamid, sat_pos, sat_pos_latlon, sat_alt, rai, bc_sb, parsers_field])
    
    df_ira = pd.DataFrame(iras, columns=['frame_type', 'record_start_timestamp_s', 'offset_ms', 'timestamp_ms', 'freq', 'confidence', 'signal_lvls', 'length', 'direction','sat_id', 'beam_id', 'sat_pos', 'sat_pos_latlon', 'sat_alt', 'rai', 'bc_sb', 'pages'])
    return df_ira

def tdoa_filter(ira_df):
    reduced_df = ira_df[['timestamp_ms', 'freq', 'sat_id', 'beam_id','sat_pos_latlon','sat_alt']]
    print(reduced_df)

dfs = []
parsed_input_folder = Path("data/parsed/")
for file in parsed_input_folder.iterdir():
    if file.is_file():          # ignore subfolders
        with open(file,"r") as input_file:
            df_iras = ira_parser(input_file)
            print(df_iras)
            #df_iras['rec_id'] = 'test'
            #df_iras['rec_lat'] = 123
            #df_iras['rec_lon'] = 123
            dfs.append(df_iras)

final_df = pd.concat(dfs, ignore_index=True)
final_df.to_csv("out.csv",float_format="%.8f",index=False)
tdoa_filter(final_df)
