import subprocess
import schedule
import time
import requests
import psycopg2 as ps
import json
from zipfile import ZipFile
import pandas as pd
from pathlib import Path
import app.dashboard.credentials as credentials
from parser_iridium import agg_to_df


# num of datapoints the signal data gets aggregated to
num_datapoints = 100
# path to temp folder, assume script gets run by startup.sh in root folder
temp_path = Path("./app/dashboard/parser/temp")
temp_path.mkdir(exist_ok=True)


# aggregate all data from DB.signal and DB.packets so public page has only num_datapoints many datapoints
def agg_all_data(conn, cur):
    cur.execute("""INSERT INTO jobs (name) VALUES (%s) ON CONFLICT DO NOTHING""", ("public_page", ))

    sql = ("""INSERT INTO sensor_job (job_name, sensor_name) 
           VALUES (%s, %s) 
           ON CONFLICT (job_name, sensor_name) 
           DO UPDATE SET job_name = EXCLUDED.job_name
           RETURNING id""")
    cur.execute(sql, ("public_page", "public_page"))
    # save returned id
    index = cur.fetchone()[0]

    # aggregate packets data
    sql = ("""SELECT p.type, SUM(p.count) 
            FROM packets as p, sensor_job as s 
            WHERE s.job_name != %s
            AND s.id = p.id
            GROUP BY p.type""")
    cur.execute(sql, ("public_page", ))
    data = cur.fetchall()
    
    if data:
        df_packets = pd.DataFrame(data=data, columns=["type", "count"])
        for i, r in df_packets.iterrows():
            sql = """INSERT INTO packets (id, type, count) 
                    VALUES (%s, %s, %s) 
                    ON CONFLICT ("id", "type") DO UPDATE SET
                    type = EXCLUDED.type, 
                    count = EXCLUDED.count"""
            cur.execute(sql, (index, r["type"], int(r["count"])))

    # aggregate signal data
    sql = ("SELECT s.timestamp AS time, s.signal_level, s.background_noise, s.snr, s.count AS counter "
           "FROM signal as s, sensor_job as j "
           "WHERE s.id = j.id "
           "AND j.job_name != %s "
           "ORDER BY s.timestamp")
    cur.execute(sql, ("public_page", ))

    rows = cur.fetchall()
    if rows:
        colnames = [desc[0] for desc in cur.description]
        # convert to list of dicts
        result = [dict(zip(colnames, row)) for row in rows]

        # get upper and lower bound for time
        time_lower = result[0]["time"]
        time_upper = result[len(result)-1]["time"]

        cols = ['signal_level', 'background_noise', 'snr']
        df_signal_agg = agg_to_df(result, num_datapoints, time_lower, time_upper, cols, None, ["counter"])

        for i, r in df_signal_agg.iterrows():
            cur.execute("""INSERT INTO signal (id, timestamp, "signal_level", "background_noise", snr, count) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT ("id", "timestamp") DO UPDATE SET 
                        "signal_level" = EXCLUDED."signal_level", 
                        "background_noise" = EXCLUDED."background_noise", 
                        snr = EXCLUDED.snr, 
                        count = EXCLUDED.count""",
                        (index, float(r['time']), float(r['signal_level']), float(r['background_noise']),
                         float(r['snr']), float(r['counter'])))
    conn.commit()


def check_for_new_data(session, conn, cur):
    # download metadata of all jobs
    response = session.get('http://127.0.0.1:8000/data/?just_metadata=1')
    # if download was successfull, write into df_data
    if response.status_code != 200:
        print("Server error ", response.status_code)
        return None
    data = response.json()
    df_data = pd.json_normalize(data.get("data", []), max_level=0)

    # download job data and write into df_jobs to get command
    response = session.get("http://127.0.0.1:8000/fixedjobs/")
    if response.status_code != 200:
        print("Server error ", response.status_code)
        return None
    data = response.json()
    df_jobs = pd.json_normalize(data.get("data", []), max_level=0)
    df_jobs = df_jobs.drop(columns=["arguments", "states"])

    # insert df_jobs into DB.jobs
    for i, r in df_jobs.iterrows():
        name = r["name"]
        cmd = r["command"]
        start = r["start_time"]
        end = r["end_time"]

        sql = "INSERT INTO jobs (name, command, start_time, end_time) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING"
        cur.execute(sql, (name, cmd, start, end))

    conn.commit()

    # find all sensor_name, job_name combinations which are not in DB.sensor_job and append to jobs_to_add
    jobs_to_add = []
    for i,r in df_data.iterrows():
        id = r["id"]
        sensor_name = r["sensor_name"]
        job_name = r["job_name"]

        sql = "SELECT * FROM sensor_job WHERE job_name = %s AND sensor_name = %s"
        cur.execute(sql, (job_name, sensor_name))
        res = cur.fetchone()
        if res is None:
            jobs_to_add.append({"id": id, "sensor_name": sensor_name, "job_name": job_name})
    return jobs_to_add


def handle_new_data(session, conn, cur, auth, jobs_to_add):
    # get command for job_to_add and download file if command is some kind of sniffing
    for job_to_add in jobs_to_add:
        id = job_to_add["id"]
        sensor_name = job_to_add["sensor_name"]
        job_name = job_to_add["job_name"]

        cur.execute("SELECT command FROM jobs WHERE name = %s", (job_name, ))
        res = cur.fetchone()
        print("Dashboard Parser: adding", job_name)
        # skip jobs without command
        if res is None:
            print("No command found for job: " + job_name)
            continue
        command = res[0]

        # if command is some kind of control, only insert into DB.sensor_job
        if any(i in command for i in ["log", "config", "restart", "reset", "reboot", "status"]):
            # add to DB.sensor_job
            sql = ("""INSERT INTO sensor_job (sensor_name, job_name) 
                   VALUES (%s, %s) 
                   ON CONFLICT DO NOTHING""")
            cur.execute(sql, (sensor_name, job_name))
            conn.commit()
            print("No relevant data to download for command", command)
        # download and extract files for sniffing jobs
        elif "sniff" in command:
            uri = 'http://127.0.0.1:8000/data/download/' + id
            response = session.get(uri)

            # if token expired while running, login and download file again
            if response.status_code == 401:
                session.post('http://127.0.0.1:8000/login/userlogin', auth)
                response = session.get(uri)

            # skip job if file couldn't be downloaded, so we can retry later
            if response.status_code != 200:
                print("Server error ", response.status_code)
                continue

            # fallback values
            index = None
            lat = None
            lon = None
            sample_rate = None
            center_freq = None
            bandwidth = None
            gain = None
            if_gain = None
            bb_gain = None
            decimation = None
            try:
                zip_path = Path(temp_path / 'temp.zip')
                # write file into ./temp/temp.zip
                with open(zip_path, 'wb') as file:
                    file.write(response.content)
                    file.close()

                # extract all files into ./temp
                with ZipFile(zip_path) as fileObject:
                    fileObject.extractall(temp_path)

                # get coordinates out of endStatus file
                status_file = Path(temp_path / str(job_name + "_endStatus.txt"))
                if status_file.exists():
                    with open(status_file, "r") as output:
                        data = output.readlines()
                    for line in data[:1]:
                        loc = json.loads(line.replace("'", '"'))
                        lat = loc['location_lat']
                        lon = loc['location_lon']

                # get configuration out of hackrf.conf file
                conf_file = Path(temp_path/ "hackrf.conf")
                if conf_file.exists():
                    with open(conf_file, "r") as output:
                        data = output.readlines()
                    conf_list = []
                    for line in data:
                        conf_list.append(line)
                    sample_rate = next((s for s in conf_list if "sample_rate" in s), "=0").split("=")[1]
                    center_freq = next((s for s in conf_list if "center_freq" in s), "=0").split("=")[1]
                    bandwidth = next((s for s in conf_list if "bandwidth" in s), "=0").split("=")[1]
                    gain = next((s for s in conf_list if "gain" in s), "=0").split("=")[1]
                    if_gain = next((s for s in conf_list if "if_gain" in s), "=0").split("=")[1]
                    bb_gain = next((s for s in conf_list if "bb_gain" in s), "=0").split("=")[1]
                    decimation = next((s for s in conf_list if "decimation" in s), "=0").split("=")[1]

                # only add to DB.sensor_job if file could be downloaded, so we can retry later
                sql = """INSERT INTO sensor_job (sensor_name, job_name, lat, lon, sample_rate, center_freq, bandwidth, 
                      gain, if_gain, bb_gain, decimation) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                      ON CONFLICT (sensor_name, job_name) DO UPDATE SET  
                      lat = EXCLUDED.lat, 
                      lon = EXCLUDED.lon, 
                      sample_rate = EXCLUDED.sample_rate, 
                      center_freq = EXCLUDED.center_freq, 
                      bandwidth = EXCLUDED.bandwidth, 
                      gain = EXCLUDED.gain, 
                      if_gain = EXCLUDED.if_gain, 
                      bb_gain = EXCLUDED.bb_gain, 
                      decimation = EXCLUDED.decimation 
                      RETURNING id"""
                cur.execute(sql, (sensor_name, job_name, lat, lon, sample_rate, center_freq, bandwidth,
                      gain, if_gain, bb_gain, decimation))
                # save returned id
                index = cur.fetchone()[0]
                # commit changes so the respective parser can insert
                conn.commit()

                # start respective parser through subprocess, so data_deamon is blocked and doesn't download next files
                if "iridium" in command:
                    #print("Iridium found")
                    #parser_iridium.start(index)
                    subprocess.run(["python3", "./app/dashboard/parser/parser_iridium.py", str(index)], check=True)
                elif "globestar" in command:
                    # parser_globestar.start(index)
                    print("Globestar found")
                elif "starlink" in command:
                    # parser_starlink.start(index)
                    print("Starlink found")
                else:
                    print("Sniffing command " + command + " unknown")

            # if exception occurred while handling files, delete from DB so we can retry later
            except Exception as e:
                if index is not None:
                    sql = "DELETE FROM packets WHERE id = %s"
                    cur.execute(sql, (index,))
                    sql = "DELETE FROM signal WHERE id = %s"
                    cur.execute(sql, (index,))
                    sql = "DELETE FROM stderr WHERE id = %s"
                    cur.execute(sql, (index,))
                    sql = "DELETE FROM sensor_job WHERE id = %s"
                    cur.execute(sql, (index,))
                print("Warning: An exception occurred while handling of files for job '" + job_name + "' with sensor '"
                      + sensor_name + "': " + str(e) + "\n\t\t Skipping extraction...")
            finally:
                # remove all files in ./temp
                for file in temp_path.iterdir():
                    if file.is_file():
                        file.unlink()
        else:
            print("Command " + command + " unknown")


def start():
    print("Dashboard parser: started")
    db_user, db_password, user, password = credentials.get()
    auth = ' {"username":"' + user + '"' + ', "password":"' + password + '"}'
    # Connect to postgres database
    conn = ps.connect(database="postgres",
                      user=db_user,
                      host="localhost",
                      password=db_password,
                      port=5432)
    cur = conn.cursor()

    with requests.sessions.Session() as session:
        # login to server
        session.post('http://127.0.0.1:8000/login/userlogin', auth)

        # check if there are new jobs to add
        jobs_to_add = check_for_new_data(session, conn, cur)
        # if there are, handle data (download, parse, agg, save in DB) and agg signal data for all jobs to display on
        # public page
        if jobs_to_add is not None:
            handle_new_data(session, conn, cur, auth, jobs_to_add)
            agg_all_data(conn, cur)

    print("Dashboard parser: finished")
    cur.close()
    conn.close()


def run():
    schedule.every().day.at("00:00").do(start)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    # run once on server restart but wait for everything to initialize
    time.sleep(10)
    start()
    # then run every day at midnight
    run()
