import bson
import pandas as pd
import zipfile
import subprocess
import sys
import os
from pathlib import Path
import pyarrow.feather as feather

# Ensure repository root is on sys.path so `app` package is importable
# when running this script from the `data/` folder directly.
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
	sys.path.insert(0, str(repo_root))
from app.dashboard.parser import parser_iridium



def raw_parser(path_to_zip: Path, output_folder: Path) -> None:
    """
    function to parse raw leocommon file
    input: parsed_input_file; output.bits file from leocommon system
    output: 
    """

    py = sys.executable  # python executable to use (default: current interpreter)
    # root folder to search for .bits files (default: repo `ideas/`)
    # data_root: Path = Path(__file__).resolve().parents[1]
    # path to iridium-parser.py (default: repo `iridium-toolkit-master/iridium-parser.py`)
    parser_path: Path = Path(__file__).resolve().parents[2] / "iridium-toolkit-master" / "iridium-parser.py"

    # job_folder_name = path_to_zip.name.replace('.zip', '')
    job_folder_name = os.path.basename(path_to_zip).replace('.zip', '')

    tmp_dir = output_folder / job_folder_name
    tmp_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path_to_zip, 'r') as zip_ref:
        zip_ref.extractall(tmp_dir)


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


    cwd = tmp_dir
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
        rename_path.replace(tmp_dir / "output.parsed")

    # TODO: At Some point, delete tmp folder?

def metadata_parser(zip_folder_name: str, output_folder: Path) -> None:
    frames, time_lower, time_upper = parser_iridium.read_parsed_output(output_folder / zip_folder_name)

	# print(f"Time lower: {time_lower}")
	# print(f"Time upper: {time_upper}")
	# print(f"Time difference (s): {(time_upper - time_lower)}")
	
    if len(frames) != 0:
        type_dict = {'time': float, 'frame_type': str, 'signal_level': float, 'background_noise': float,
					 'snr': float}
    else:
        return

    df = pd.DataFrame(data=frames)
    df = df.astype(dtype=type_dict)
    df = df.sort_values(by="time").reset_index()

    df.to_feather(output_folder / zip_folder_name / "output_df.feather")



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
            signal_strength, noise_strenth, snr = map(float, splitted[5].split("|"))
            length = int(splitted[6])
            direction = splitted[7]
            satid = splitted[8].removeprefix("sat:")
            beamid = splitted[9].removeprefix("beam:")
            sat_pos = [float(x) for x in splitted[10].removeprefix("xyz=(").removesuffix(")").split(",")]
            sat_pos_latlon = [float(x) for x in splitted[11].removeprefix("pos=(").removesuffix(")").split("/")]
            sat_alt = int(splitted[12].removeprefix("alt="))
            rai = splitted[13].removeprefix("RAI:")
            #skip unknown field
            bc_sb = splitted[15].split(":")[-1]
            parsers_field = [x for x in splitted[16:] if x !=  "{OK}" and not x.startswith(("FILL"))]  #format parser list and ignore last filler element

            iras.append([frame_type, record_start_timestamp_s, offset_ms, timestamp_ms, freq, confidence, signal_strength, noise_strenth, snr, length, direction, satid, beamid, sat_pos, sat_pos_latlon, sat_alt, rai, bc_sb, parsers_field])
    
    df_ira = pd.DataFrame(iras, columns=['frame_type', 'record_start_timestamp_s', 'offset_ms', 'timestamp_ms', 'freq', 'confidence', 'signal_strength', 'noise_strenth', 'snr', 'length', 'direction','sat_id', 'beam_id', 'sat_pos', 'sat_pos_latlon', 'sat_alt', 'rai', 'bc_sb', 'pages'])
    return df_ira

def tdoa_filter(ira_df):
    reduced_df = ira_df[['timestamp_ms', 'freq', 'sat_id', 'beam_id','sat_pos_latlon','sat_alt']]
    print(reduced_df)


def create_network_stats(parsed_folder: Path) -> pd.DataFrame:

    # Find all .feather files in all subfolders of parsed_path and concatenate them
    feather_files = list(parsed_folder.glob("**/*.feather"))

    # Ingore ira.feather (as those are all ring alerts from all jobs combined)
    ingore_files = [f for f in feather_files if
                    f.name == "ira.feather" or
                    f.name == "network_stats.feather" or
                    f.name == "df_packets.feather" or
                    f.name == "clients_stats.feather"]
    feather_files = [f for f in feather_files if f not in ingore_files]

    print(f"Found {len(feather_files)} feather files under {parsed_folder}")

    dfs = []
    for f in sorted(feather_files):
        # Split on 'parsed\' and take the part after
        if 'parsed\\' in str(f):
            after_parsed = str(f).split('parsed\\')[1]
        else:
            after_parsed = str(f)
        
        # Split on '_sensor_' and take the job name (part before)
        parts = after_parsed.split('_sensor_')
        job_name = parts[0] if len(parts) > 0 else ""
        sensor_name = parts[1].split('\\')[0] if len(parts) > 1 else ""

        try:
            df = feather.read_feather(f)
            # keep a provenance column so we know which file a row came from
            # df["_source_feather"] = str(f)
            # dfs.append(df)
            df["job_name"] = job_name
            df["sensor_name"] = sensor_name
            dfs.append(df)
        except Exception as e:
            print(f"Failed to read {f}: {e}")

    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        # print(f"Combined dataframe shape: {combined.shape}")
        # display(combined.head())
    else:
        combined = pd.DataFrame()
        print("No feather files found or all reads failed.")

    df_combined = pd.concat([combined], ignore_index=True)

    return df_combined


def create_packets_over_time(parsed_folder: Path):
    """Create a DataFrame counting packets over time (by year and month) from network_stats.feather."""
    
    df = pd.read_feather(parsed_folder / "network_stats.feather")

    # Group df by year and month and count datapoints per month
    # Ensure timestamp column exists
    if "timestamp" not in df.columns:
        df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)

    # Create year and month columns (integers)
    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.month

    # Aggregate: count rows per year/month
    df_packets_over_time = (
        df.groupby(["year", "month"])  
        .size()
        .reset_index(name="count")
        .sort_values(["year", "month"])  
        .reset_index(drop=True)
    )

    # Also add an ISO-like year-month column for easier plotting/labeling
    df_packets_over_time["year_month"] = df_packets_over_time["year"].astype(str) + "-" + df_packets_over_time["month"].astype(str).str.zfill(2)

    return df_packets_over_time


def create_number_of_packets(parsed_folder: Path) -> pd.DataFrame:
    """Create a DataFrame counting total number of packets from network_stats.feather."""
    
    df = pd.read_feather(parsed_folder / "network_stats.feather")

    # Group df by number of packets
    df_packets = df.groupby("frame_type").size().reset_index(name="count").sort_values(by="count", ascending=False).reset_index(drop=True)

    return df_packets

def create_number_of_jobs_per_month(parsed_folder: Path) -> pd.DataFrame:
    """Create a DataFrame counting unique jobs per month from network_stats.feather."""

    feather_path = os.path.join(parsed_folder, "network_stats.feather")
    df = pd.read_feather(feather_path)

    # Ensure timestamp column exists
    if "timestamp" not in df.columns:
        df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)

    # Create year and month columns (integers)
    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.month

    # Aggregate: count unique jobs per year/month
    df_jobs_per_month = (
        df.groupby(["year", "month"])["job_name"]  
        .nunique()  
        .reset_index(name="unique_job_count")
        .sort_values(["year", "month"])  
        .reset_index(drop=True)
    )

    return df_jobs_per_month


def create_clients_stats(clients_bson_path: Path) -> pd.DataFrame:
    """"Create a client DataFrame from a BSON file input in the parsed folder."""

    with open(clients_bson_path, 'rb') as fh:
        raw = fh.read()

    # iterate concatenated BSON documents manually
    docs = []
    offset = 0
    length = len(raw)

    while offset < length:
        # first 4 bytes: little-endian int32 size of document
        size = int.from_bytes(raw[offset:offset+4], 'little')
        doc_bytes = raw[offset:offset+size]

        obj = bson.loads(doc_bytes)
        
        docs.append(obj)
        offset += size

    return pd.DataFrame(docs)



input_path = Path("ideas/data")
parsed_folder = Path("ideas/data/parsed/")


# pd.DataFrame(create_network_stats(parsed_folder)).to_feather(parsed_folder / "network_stats.feather")
# pd.DataFrame(create_packets_over_time(parsed_folder)).to_feather(parsed_folder / "df_packets_over_time.feather")
# pd.DataFrame(create_number_of_packets(parsed_folder)).to_feather(parsed_folder / "df_packets.feather")
pd.DataFrame(create_number_of_jobs_per_month(parsed_folder)).to_feather(parsed_folder / "df_jobs_per_month.feather")
# pd.DataFrame(create_clients_stats(parsed_folder / "clients.bson")).to_feather(parsed_folder / "clients_stats.feather")

# dfs = []

# for zip_file in input_path.glob("*.zip"):

#     job_folder_name = zip_file.name.replace('.zip', '')
    
#     print(zip_file)

#     raw_parser(zip_file,parsed_folder)

#     metadata_parser(job_folder_name, parsed_folder)

#     df = ira_parser(open(parsed_folder / job_folder_name / "output.parsed","r")) 


#     # Sensor and Job info
#     df['job_name'] = job_folder_name.split('_sensor_')[0]
#     df['sensor_name'] = job_folder_name.split('_sensor_')[1]

#     print(df.head(1))

    

#     dfs.append(df)
    
# pd.concat(dfs, ignore_index=True).to_feather(parsed_folder / "ira.feather")









# for file in parsed_folder.iterdir():
#     if file.is_file():          # ignore subfolders
#         with open(file,"r") as input_file:
#             df_iras = ira_parser(input_file)
#             print(df_iras)
#             #df_iras['rec_id'] = 'test'
#             #df_iras['rec_lat'] = 123
#             #df_iras['rec_lon'] = 123
#             dfs.append(df_iras)

# final_df = pd.concat(dfs, ignore_index=True)
# final_df.to_csv("out.csv",float_format="%.8f",index=False)
# #final_df.to_feather("out.feather")
# tdoa_filter(final_df)
