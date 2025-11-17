import pandas as pd  
import csv
import skyfield
from skyfield.api import EarthSatellite, load, wgs84, utc
import datetime

#adjust
all_satellites_tle = "active_2025_07_23.tle" #file to filter the celestrak tle file containing all active satellites
tle_date = datetime.datetime(2025,7,23, tzinfo=utc) #timestamp of tle_file for freshness check


#process all entries and generate respective tle files
with open(all_satellites_tle, "r") as file_in:
    with open('../LEO_active.tle','w') as leo_active:
    #process 1 TLE entry (3 lines) at a time
        while True: 
            try: 
                line_name = file_in.readline()
                line1 = file_in.readline()
                line2 = file_in.readline()
                if not line_name or not line1 or not line2: break

                ts = skyfield.api.load.timescale()

                #parse satellite data
                satellite = skyfield.api.EarthSatellite(line1,line2,line_name,ts)
                sat_epoch = satellite.epoch         #get epoch i.e. point in time where TLE is most accurate
                days = ts.from_datetime(tle_date) - satellite.epoch_2_jDay #for freshness check

                position = satellite.at(sat_epoch)  #calculate position at epoch time point
                altitude = wgs84.height_of(position).km

                #ignoring satellites that are de-orbiting (old data and/or descending)
                if days > 2 or altitude < 250:
                    continue
                
                #only consider LEO satellites (below 2000km altitude)
                if altitude < 2000:
                    #place into general LEO file:
                    leo_active.write(line_name)
                    leo_active.write(line1)
                    leo_active.write(line2)

            except Exception as e:
                print("Unable to decode TLE data. Make the sure TLE data is formatted correctly." + str(e))
                exit(1)