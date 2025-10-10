import sys
import math
import pandas as pd
import numpy as np
import psycopg2 as ps
from pathlib import Path
import subprocess
import app.dashboard.credentials as credentials


###
# Constant definitions
###

# number of datapoints to which the output and stderr data gets accumulated to
num_datapoints = 100
# path to temp folder, assume script gets run by data_deamon which is run in root folder
temp_path = Path("./app/dashboard/parser/temp")

current_path = Path(__file__)
server_path = current_path.parent.parent.parent.parent
python_path = server_path / "env/bin/python"
iridium_parser_path = server_path / "tools/iridium-toolkit/iridium-parser.py"

db_user, db_password, user, password = credentials.get()


###
# Function definitions
###

# returns dataframe [[attribute -> count], [packet type -> count]...]
def count_attribute(dataframe, attribute):
    dataframe = dataframe.groupby([attribute]).count()
    dataframe = dataframe.rename(columns={'time': 'count'}).reset_index()
    return dataframe


def run_external_parser(temp_path):
    # run iridium-toolkit/iridium-parser.py on every .bits file
    for file in temp_path.glob("*.bits"):
        print('Started iridium-parser for', file.name)
        subprocess.run([
            python_path, iridium_parser_path, "-p", str(file.name)
        ], cwd=temp_path)
        print('Iridium-parser finished for', file.name)


def read_parsed_output(temp_path):
    time_lower = math.inf
    time_upper = 0.0
    frames = []
    for file in temp_path.glob("*.parsed"):
        # turn every line of input file to string[]
        with open(file, "r") as output:
            data = output.readlines()

        # add every line into frames[]
        for line in data:
            try:
                # convert current line string to list
                currLine = line.split()

                # extract all relevant values out of line
                frame_type = currLine[0].split(':')[0]
                timestamp = currLine[1].split('p-')[1]
                time_in_rec = currLine[2]
                #frequency = currLine[3]
                #confidence = currLine[4].rstrip("%")
                signal_vars = currLine[5].split('|')
                signal_level = signal_vars[0]
                background_noise = signal_vars[1]
                snr = signal_vars[2]

                # store upper and lower bound of time
                time = int(timestamp) + (float(time_in_rec) / 1000)
                if float(time) <= time_lower:
                    time_lower = float(time)
                if float(time) >= time_upper:
                    time_upper = float(time)

                # add all rows into list first
                frames.append({"time": time, "frame_type": frame_type, "signal_level": signal_level,
                               "background_noise": background_noise, "snr": snr})
            except Exception as e:
                print(f"Warning: An exception occurred in line: {line} \t\t while parsing {str(file.name)}: "
                      f"{str(e)} \n\t\t Skipping line...")
                continue
    return frames, time_lower, time_upper


def read_stderr(stderr_path):
    # Turns every line of input file to string[]
    with open(stderr_path, "r") as output:
        data = output.readlines()

    time_lower = math.inf
    time_upper = 0.0
    stderr = []

    # add data for every line into stderr[]
    for line in data:
        try:
            # convert current line string to list
            currLine = line.split(' | ')
            firstElem = currLine[0].split()[0].lstrip("O")
            if firstElem not in ('gr-osmosdr', 'built-in', 'Using', '(RF)', 'IF', 'BB', 'Bandwidth:', 'Warning:',
                                 'WARNING:', 'Done.', 'Detector', 'Resetting'):
                # extract all relevant values out of line
                time = float(currLine[0].lstrip("O"))  # remove leading O's that appear sometimes

                # save lowest and highest timestamps
                if time <= time_lower:
                    time_lower = time
                if time >= time_upper:
                    time_upper = time

                # for data like 'name: value%' strip 'name:' and '%' and store 'value'
                i = currLine[1].split()[1].split('/')[0]
                # i_avg = currLine[2].split()[1].split('/')[0]
                # q_max = currLine[3].split()[1]
                # i_ok_p = currLine[4].split()[1].split('%')[0]
                o = currLine[5].split()[1].split('/')[0]
                # ok_p = currLine[6].split()[1].split('%')[0]
                ok_s = currLine[7].split()[1].split('/')[0]
                # ok_avg_p = currLine[8].split()[1].split('%')[0]
                ok = currLine[9].split()[1]
                # ok_avg = currLine[10].split()[1].split('/')[0]
                # d = currLine[11].split()[1]select * from sensor_job as j where j.sensor_name = 'Sim';

                stderr.append({"time": time, "i": i, "o": o, "ok_s": ok_s, "ok": ok, })
        except Exception as e:
            print(f"Warning: An exception occurred in line: {line} \t\t while parsing {str(stderr_path.name)}: "
                  f"{str(e)} \n\t\t Skipping line...")
    return stderr, time_lower, time_upper


def fill_df(data, dtype):
    # fill dataframe with list, set types and sort by time
    df = pd.DataFrame(data=data)
    df = df.astype(dtype=dtype)
    df = df.sort_values(by="time").reset_index()
    return df


# aggregates a list of dicts into a dataframe with num_datapoints many equally spaced timeslots between time_lower &
# time_upper
# keys to aggregate are in agg_cols
# if key max_cols is provided, these columns will not be aggregated but every slot is the max value
# if sum_cols is provided these columns are summed up
# if min_col provided these columns are min value
def agg_to_df(list, num_datapoints, time_lower, time_upper, agg_cols, max_cols=None, sum_cols=None, min_cols=None):
    # slice timeframe of recording into 100 equally spaced timeslots
    interval = np.linspace(time_lower, time_upper, num=num_datapoints, dtype=float)
    # number of seconds in one timeslot
    secs = (time_upper - time_lower) / num_datapoints
    zero_array = np.zeros(len(interval), dtype=float)
    # add time and count column for plotting and calculating the avg
    columns = agg_cols.copy()
    columns.append('time')
    columns.append('count')
    # fill time with interval, every other column with zeros
    d = {'time': interval, 'count': zero_array}
    for col in agg_cols:
        d[col] = zero_array
    if max_cols is not None:
        for col in max_cols:
            d[col] = zero_array
            columns.append(col)
    if sum_cols is not None:
        for col in sum_cols:
            d[col] = zero_array
            columns.append(col)
    if min_cols is not None:
        for col in min_cols:
            d[col] = zero_array
            columns.append(col)
    df = pd.DataFrame(columns=columns, data=d)

    # for every item: calculate the slot, increment the count and update value according to aggregation function
    for l in list:
        secs_in_rec = l['time'] - time_lower
        slot = int(secs_in_rec / secs)
        # bound the slot between 0 and num_datapoints - 1 to prevent index out of bounds error because of
        # floating-point rounding
        slot = max(0, min(slot, num_datapoints - 1))
        # increment count for slot
        df.loc[slot, 'count'] += 1
        # add up all values in a slot for all cols in agg_col
        for col in agg_cols:
            df.loc[slot, col] += float(l[col])
        # if max_col is provided, save max value in max_col
        if max_cols is not None:
            for col in max_cols:
                #df.loc[slot, col] = max(df.loc[slot, col], float(l[col]))
                df.loc[slot, col] = np.maximum(df.loc[slot, col], float(l[col]))
        # if sum_col is provided, save sum of value in sum_col
        if sum_cols is not None:
            for col in sum_cols:
                df.loc[slot, col] += float(l[col])
        # if min_col is provided, save min of value in min_col
        if min_cols is not None:
            for col in min_cols:
                #df.loc[slot, col] = min(df.loc[slot, col], float(l[col]))
                df.loc[slot, col] = np.minimum(df.loc[slot, col], float(l[col]))
    # divide all agg_cols by the package count of the respective timeslot, count column can be used for running_sum
    for col in agg_cols:
        df[col] = np.ceil(df[col] / df['count'])

    return df


def start(index):
    # Connect to postgres database
    conn = ps.connect(database="postgres",
                      user=db_user,
                      host="localhost",
                      password=db_password,
                      port=5432)
    cur = conn.cursor()
    print("parser_iridium called")

    ###
    # aggregate output.bits files and add to DB.signal, DB.packets
    ###

    # if any file with .bits ending exists
    if any(temp_path.glob("*.bits")):
        run_external_parser(temp_path)
        frames, time_lower, time_upper = read_parsed_output(temp_path)

        if len(frames) != 0:
            type_dict = {'time': float, 'frame_type': str, 'signal_level': float, 'background_noise': float,
                         'snr': float}
            df_frames = fill_df(frames, type_dict)

            # add Packet Type and Count into DB.packets
            df_packet_count = count_attribute(df_frames, 'frame_type')

            for i, r in df_packet_count.iterrows():
                cur.execute("""INSERT INTO packets (id, type, count) 
                            VALUES (%s, %s, %s)
                            ON CONFLICT ("id", "type") DO UPDATE
                            SET count = EXCLUDED.count""",
                            (index, r['frame_type'], r['count']))
            conn.commit()
            print("Finished inserting into DB.Packets")

            cols = ['signal_level', 'background_noise', 'snr']
            df_frames_agg = agg_to_df(frames, num_datapoints, time_lower, time_upper, cols)

            # add signal data into DB.signal
            for i, r in df_frames_agg.iterrows():
                cur.execute("""INSERT INTO signal (id, timestamp, "signal_level", "background_noise", snr, count) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT ("id", "timestamp") DO UPDATE SET 
                            "signal_level" = EXCLUDED."signal_level", 
                            "background_noise" = EXCLUDED."background_noise", 
                            snr = EXCLUDED.snr, 
                            count = EXCLUDED.count""",
                            (index, float(r['time']), float(r['signal_level']), float(r['background_noise']),
                             float(r['snr']), float(r['count']), ))
            conn.commit()
            print("Finished inserting into DB.Signal")
        else:
            print("output.bits file empty")
    else:
        print("No output.bits file found")

    ###
    # aggregate output.stderr and add to DB.stderr
    ###

    stderr_path = Path(temp_path / "output.stderr")

    if stderr_path.exists():
        stderr, time_lower, time_upper = read_stderr(stderr_path)

        if len(stderr) != 0:
            cols = ["i", "o", "ok_s"]
            df_stderr_agg = agg_to_df(stderr, num_datapoints, time_lower, time_upper, cols, ["ok"])

            # insert dataframe into DB.stderr
            for i, r in df_stderr_agg.iterrows():
                cur.execute("""INSERT INTO stderr (id, timestamp, i, o, ok_s, ok)
                                        VALUES (%s, %s, %s, %s, %s, %s)
                                        ON CONFLICT ("id", "timestamp") DO UPDATE SET
                                        i = EXCLUDED.i, 
                                        o = EXCLUDED.o, 
                                        ok_s = EXCLUDED.ok_s, 
                                        ok = EXCLUDED.ok""",
                            (index, float(r['time']), int(r['i']), int(r['o']), int(r['ok_s']), int(r['ok'])))
            print("Finished inserting into DB.Stderr")
            conn.commit()
        else:
            print("output.stderr file empty")
    else:
        print("No output.stderr file found")

    # Close communication with the database
    cur.close()
    conn.close()
    print("Data has been successfully extracted!")


if __name__ == "__main__":
    index = int(sys.argv[1])
    start(index)
