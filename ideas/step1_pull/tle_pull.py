import datetime
import requests
import json
from skyfield.api import EarthSatellite, load, wgs84

# get data
def pull_data():
    "pulling fresh tle data"
    tle_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
    data = requests.get(tle_url)
    return data.text.splitlines()

def filter_data(data, timestamp, output_file):
    """
    function to filter out non-LEO, no-contact and deorbiting satellites
    additionally get some stats on the processed dataset
    """
    stats = {
        "timestamp" : str(timestamp),
        "leo_satellites": 0,
        "iridium_satellites": 0,
        "starlink_satellites": 0,
        "oneweb_satellites": 0,
        "globalstar_satellites": 0,
        "orbcomm_satellites": 0,
    }
    
    
    for i in range(0, len(data)-3, 3):
        try: 
            #process 1 TLE entry (3 lines) at a time
            line_name = data[i]
            line1 = data[i+1]
            line2 = data[i+2]
            #check format of TLE
            if not line_name or not line1 or not line2: break
            #print(f"{line_name}\n{line1}\n{line2}\n\n")

            #parse satellite data
            ts = load.timescale()
            satellite = EarthSatellite(line1,line2,line_name,ts)
            sat_epoch = satellite.epoch                                         #get epoch i.e. point in time where TLE is most accurate
            days_since_last_contact = ts.from_datetime(timestamp) - sat_epoch   #for freshness check

            position = satellite.at(sat_epoch)                                  #calculate position at epoch time point
            altitude = wgs84.height_of(position).km

            #ignoring satellites that are de-orbiting (old data and/or descending)
            if days_since_last_contact > 3 or altitude < 250:
                continue
            
            #only consider LEO satellites (below 2000km altitude)
            if altitude < 2000:
                #store
                output_file.write(line_name+"\n")
                output_file.write(line1+"\n")
                output_file.write(line2+"\n")

                #stats
                stats["leo_satellites"] += 1
                if satellite.name.startswith("IRIDIUM"):
                    stats["iridium_satellites"] += 1
                elif satellite.name.startswith("STARLINK"):
                    stats["starlink_satellites"] += 1 
                elif satellite.name.startswith("ORBCOMM"):
                    stats["orbcomm_satellites"] += 1 
                elif satellite.name.startswith("GLOBALSTAR"):
                    stats["globalstar_satellites"] += 1 
                elif satellite.name.startswith("ONEWEB"):
                    stats["oneweb_satellites"] += 1

        except Exception as e:
            print("Unable to decode TLE data. Make the sure TLE data is formatted correctly." + str(e))
            exit(1)
        
    return stats


if __name__ == '__main__':
    output_path = "output/"
    output_tle = "active_leos.tle"
    with open(output_path+output_tle, "w") as output_file, open(output_path+"stats.json", "w") as f:
        tle_date = datetime.datetime.now(datetime.UTC) #timestamp for freshness check
        tle_data = pull_data()#open("local_copy.txt").read().splitlines()
        print("**fresh TLE data obtained")

        stats_data = filter_data(tle_data, tle_date, output_file)
        json.dump(stats_data, f, indent=2, sort_keys=False)
        print(f"**outputs stored in: {output_path}")