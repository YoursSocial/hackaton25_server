import pandas as pd
from pathlib import Path
import networkx as nx
import datetime
import numpy as np


def match_receiver_runs(
    ira_df,
    number_consecutive_meas,
    inter_receiver_difference,
    intra_receiver_difference,
    number_of_receivers):
    """
    Finds timestamp-level overlaps between receivers observing the same sat-beam.
    Produces clusters of receivers and timestamp pairs suitable for TDOA.
    input: df containing ira messages
    output: list of df, each df contains infos to calculate a tdoa signature
    """

    # ---------------------------------------------------------
    # 1) Prepare DataFrame
    # ---------------------------------------------------------
    df = ira_df[["sensor_name", "sat_id", "beam_id","timestamp_ms", "signal_strength"]].copy()
    df["datetime"] = pd.to_datetime(df["timestamp_ms"], unit="ms")
    #df["rec-sat-beam_id"] = df.groupby(["sensor_name","sat_id","beam_id"]).ngroup() # rec-sat-beam unique ID
    df = df.sort_values(["sensor_name","sat_id","beam_id","timestamp_ms"])

    # ---------------------------------------------------------
    # 2) Build identify long-enough runs per receiver
    # ---------------------------------------------------------
    df["prev_ts"] = df.groupby(["sensor_name", "sat_id", "beam_id"])["datetime"].shift()
    df["intra_rec_time_diff"] = (df["datetime"] - df["prev_ts"]).dt.total_seconds()
    df["run_id"] = (
        df.assign(new_run=lambda d: d["intra_rec_time_diff"].isna() | (d["intra_rec_time_diff"] >= intra_receiver_difference)).groupby(["sensor_name","sat_id","beam_id"])["new_run"].cumsum())

    # keep only runs with enough consecutive measurements
    run_sizes = df.groupby(["sensor_name","sat_id","beam_id","run_id"]).size()
    valid_runs = run_sizes[run_sizes >= number_consecutive_meas].index

    df_valid = (df.set_index(["sensor_name","sat_id","beam_id","run_id"]).loc[valid_runs].reset_index())

    # ---------------------------------------------------------
    # 3) Run-level summary table (no timestamps lost)
    # ---------------------------------------------------------
    RUN_KEYS = ["sensor_name","sat_id","beam_id", "run_id"]

    df_valid["global_run_id"] = df_valid.groupby(RUN_KEYS).ngroup()
    #print(df_valid[["sensor_name","sat_id","beam_id", "run_id", "global_run_id"]])

    run_summaries = (
        df_valid.groupby(["sensor_name","sat_id","beam_id", "run_id","global_run_id"])["datetime"]
        .agg(['min','max','count'])
        .reset_index()
        .rename(columns={'min':'run_start','max':'run_end'})
    )
    #shape sensor_name, sat_id,beam_id, run_id, run_start, run_end, count
    #print(run_summaries)
    # ---------------------------------------------------------
    # 4) Candidate overlapping runs across receivers
    # ---------------------------------------------------------
    run_overlaps = (
        run_summaries.merge(
            run_summaries,
            on=["sat_id", "beam_id"],
            suffixes=("_A","_B")
        )
        .query("sensor_name_A != sensor_name_B")
        .query("run_start_A <= run_end_B and run_start_B <= run_end_A")
    )
    #shape sensor_name_A, sat_id,beam_id, run_id_A, run_start_A, run_end_A, count_A, sensor_name_B, run_id_B, run_start_B, run_end_B, count_B

    #print(run_overlaps.head)

    G = nx.Graph()
    for _, row in run_overlaps.iterrows():
        G.add_edge(row["global_run_id_A"], row["global_run_id_B"])

    components = [list(c) for c in nx.connected_components(G)]

    # keep only those with number of desired receivers
    multirec = [c for c in components if len(c) >= number_of_receivers]
    print(multirec)
    usable = []
    counter = 0
    for cluster in multirec:
        cluster_df = df_valid[df_valid['global_run_id'].isin(cluster)]

        #only keep messages within (max_start-2; min_start+2 seconds)
        max_start = run_summaries[run_summaries['global_run_id'].isin(cluster)]["run_start"].max() - datetime.timedelta(0,2)
        min_end = run_summaries[run_summaries['global_run_id'].isin(cluster)]["run_end"].min() + datetime.timedelta(0,2)

        cluster_df = cluster_df[(cluster_df["datetime"] >= max_start) &(cluster_df["datetime"] <= min_end)]

        
        if not cluster_df.empty:
            if cluster_df["sensor_name"].nunique() >= number_of_receivers:
                if (cluster_df.groupby(["sensor_name"]).size() >= number_consecutive_meas).all():
                    usable.append(cluster_df)
                    counter += 1
                

    print(usable)
    print(f"found {counter} clusters with {number_consecutive_meas} consecutive measurements across {number_of_receivers} receivers")
    return usable

def calculate_tdoa(batch,signature_kind):
    print(batch)
    toas = np.array([x["timestamp_ms"] for x in batch])
    print(toas)
    if signature_kind == 0:
        return toas - toas[0] 
    elif signature_kind == 1:
        return toas - np.roll(toas, shift=1)
    elif signature_kind == 2:
        return (toas - toas[:,None])
    else:
        return []
     
   

def calculate_signature(matched_df):
    satellite = matched_df["sat_id"][0]
    groups = [g.sort_values("datetime") for _, g in matched_df.groupby('sensor_name')]
    #print(groups)
    tdoas1 = []
    tdoas2 = []
    tdoas3 = []
    for i in range(len(groups[0])):
        batch = [g.iloc[i] for g in groups if i < len(g)]
        batch = [x[["sensor_name","datetime", "timestamp_ms"]] for x in batch]
        tdoa1 = calculate_tdoa(batch,0)
        tdoa2 = calculate_tdoa(batch,1)
        tdoa3 = calculate_tdoa(batch,2)

        tdoas1.append(tdoa1)
        tdoas2.append(tdoa2)
        tdoas3.append(tdoa3)
    
    print(f'{tdoas1}\n{tdoas2}\n{tdoas3}\n\n')
    
    return



#parsed_folder = Path("../data/parsed/")
#ira_df =  pd.read_feather(parsed_folder/"ira.feather")
ira_df = pd.read_feather("ira.feather")
number_consecutive_meas = 6
inter_receiver_difference = 2 #s
intra_receiver_difference = 5 #s, should be about 4s
number_of_receivers = 3

"""usables = match_receiver_runs(ira_df,number_consecutive_meas,inter_receiver_difference,intra_receiver_difference,number_of_receivers)
for i in range(len(usables)):
    usables[i].to_csv(f"data/usables/cluster{i}.csv")"""

usable = pd.read_csv("data/usables/cluster0.csv")
calculate_signature(usable)
