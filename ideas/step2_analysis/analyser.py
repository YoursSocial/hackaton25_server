import pandas as pd
from pathlib import Path

def raw_parser(raw_input_file):
    """
    function to parse raw leocommon file
    input: parsed_input_file; output.bits file from leocommon system
    output: 
    """
    #TODO insert markus raw parser
    pass

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
