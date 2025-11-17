import sgp4.api
from sgp4.api import Satrec, SatrecArray, SGP4_ERRORS
from sgp4.api import days2mdhms, jday
import skyfield.sgp4lib as sgp4lib
from astropy import coordinates as coord
from astropy.time import Time
from datetime import datetime, timezone
from astropy import units as u


import numpy as np

# The SGP4 propagator returns raw x,y,z Cartesian coordinates in a “True Equator Mean Equinox” (TEME)
# reference frame that’s centered on the Earth but does not rotate with it — an “Earth centered inertial” (ECI)
# reference frame.
# The satellite deviate from the ideal orbits described in TLE files about 1–3 km/day.

# The purpose of this class is to load a set of satellites from TLEs and calculate their position at a given point in
# time. The returned positions are in TEME frame.
class TLEcalculator:
    def __init__(self, tleFile: str, warnings: bool=True, verbose: bool=True):
        self.tleFile = tleFile
        self.warnings = warnings
        self.verbose = verbose
        self.valid_days = 7
        self.__parseFile()
        self.one_sec_jDay = 1 / 86400  # one second in julian day

    def __parseFile(self):
        if self.tleFile is None:
            return
        file = open(self.tleFile, "r")
        lines = file.readlines()
        elements = int (len(lines) / 3)
        sat_list = []
        sat_names = []
        for i in range(elements):
            line_name = lines[i*3]
            line_one = lines[i*3 + 1]
            line_two = lines[i*3 + 2]
            if line_name[-1] == "\n":
                line_name = line_name[:-1]
                line_name = line_name.lstrip()
                line_name = line_name.rstrip()
            if line_one[-1] == "\n":
                line_one = line_one[:-1]
            if line_two[-1] == "\n":
                line_two = line_two[:-1]
            tempSat = Satrec.twoline2rv(line_one, line_two)
            sat_list.append(tempSat)
            sat_names.append(line_name)
        self.sat_names = sat_names
        self.satList = sat_list
        self.satrec = SatrecArray(sat_list)
        if self.verbose:
            print(f"INFO:TLEcalculator: {len(self.satList)} sats parsed")

    def get_min_max_epoch(self) -> ((int, float), (int, float)):
        minYr = 999
        minDay = 999
        maxYr = 000
        maxDay = 0
        for sat in self.satList:
            tempYr = sat.epochyr
            tempDay = sat.epochdays
            if tempYr < minYr:
                minYr = tempYr
                minDay = tempDay
            elif tempYr == minYr and tempDay < minDay:
                minDay = tempDay
            if tempYr > maxYr:
                maxYr = tempYr
                maxDay = tempDay
            elif tempYr == maxYr and tempDay > maxDay:
                maxDay = tempDay
        return (minYr, minDay), (maxYr, maxDay)

    #"calculate_one_position_single"
    def calculate_position_single(self, satellite: Satrec, jDay: float, jDayF: float):
        '''if self.warnings and abs(jDay+jDayF - self.satList[0].jdsatepoch) > self.valid_days:
            print(f"WARNING: TLEcalculator.calculate_position: Large difference between TLE-epoch and given time: given={jDay+jDayF}, epoch={self.satList[0].jdsatepoch}.")
        '''

        err, pos, vel = satellite.sgp4(jDay, jDayF)
        if err is not 0 and self.verbose:
            print(f"INFO:TLEcalculator.calc_pos_single: error {err}: '{SGP4_ERRORS.get(err)}'. pos:{pos}, "
                  f"sat_epoch:{satellite.jdsatepoch+satellite.jdsatepochF}, target_epoch:{jDay+jDayF}")
        return err, pos, vel

    #"calculate_one_position_all"
    def calculate_positions_all(self, jTimeDay: float, jTimeFr: float=0.0):
        '''if self.warnings and abs(jTimeDay - self.satList[0].jdsatepoch) > self.valid_days:
            print(f"WARNING: TLEcalculator.calculate_position: Large difference between TLE-epoch and given time.")
        '''
        jd = np.array([jTimeDay])
        fr = np.array([jTimeFr])
        err, pos, vel = self.satrec.sgp4(jd, fr)
        return pos, vel

    #"calculate_multi_positions_all"
    def calculate_multiple_positions_all(self, jTimeDay: np.ndarray, jTimeFr: np.ndarray):
        err, pos, vel = self.satrec.sgp4(np.array(jTimeDay), np.array(jTimeFr))
        return pos, vel

    #"utc_time_to_jDay"
    def abs_time_to_jDay(self, year: int, month: int, day: int, hour:int, minute: int, second: int) -> (float, float):
        return jday(year, month, day, hour, minute, second)

    def relative_time_to_jDay(self, seconds_to_add: float) -> (float, float):
        # The seconds are added to the first epoch-entry of the sat-list
        epochJday = self.satList[0].jdsatepoch
        epochjDayF = self.satList[0].jdsatepochF
        day2add = seconds_to_add / (24*3600)
        day2add += epochjDayF
        epochJday += int(day2add)
        epochjDayF = day2add - int(day2add)
        return epochJday, epochjDayF

    def epoch_2_jDay(self, epochYr: int, epochDay: float) -> (float, float):
        # epoch[month, day, hour, minute, second]
        epoch = days2mdhms(epochYr, epochDay)
        # add constant 2000 to the year. This is not the best solution (epoches before 2000 will be corrupted)
        jDate = jday(epochYr+2000, epoch[0], epoch[1], epoch[2], epoch[3], epoch[4])
        return jDate




    def TEME_2_ITRS(self, jDay: float, jDayF: float, pos_TEME: [float], vel_TEME: [float]):
        pos_TEME = np.array(pos_TEME)
        vel_TEME = np.array(vel_TEME)
        pos_ITRS = []
        vel_ITRS = []
        for sat_index in range(len(pos_TEME)):
            pos_temp, vel_temp = sgp4lib.TEME_to_ITRF(jDay + jDayF, np.asarray(pos_TEME[sat_index,:]), np.asarray(vel_TEME[sat_index,:]) * 86400)
            vel_temp = vel_temp / 86400
            pos_ITRS.append(pos_temp)
            vel_ITRS.append(vel_temp)
        return np.array(pos_ITRS), np.array(vel_ITRS)

    def epoch_to_utc(self, epochYr: int, epochDay: float)-> (int, int, int, int, int):
        # returns (month, day, hour, minute, second)
        return sgp4.api.days2mdhms(epochYr, epochDay)

    def utc_time_to_jDay(self, year: int, month: int, day: int, hour:int, minute: int, second: float) -> (float, float):
        return jday(year, month, day, hour, minute, second)

    def utc_timestamp_to_jDay(self, timestamp: int) -> (float, float):
        dt = datetime.utcfromtimestamp(timestamp)
        return self.utc_time_to_jDay(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)

    def update_sat_list(self, sat_names_new: [str], sat_list_new: [Satrec]):
        self.sat_names = sat_names_new
        self.satList = sat_list_new
        self.satrec = SatrecArray(sat_list_new)



    def find_visible_satellites(self, jd_time: Time, rec_ITRS: coord.ITRS):
        """Calculates a list of satellites that are above the horizon of the given terminal location/receiver at a given time.

        jd_time: stropy.time.Time jd-timestamp
        rec_ITRS: position of the receiver in ITRS format (i.e. centroid of the receivers)

        Returns: [satellite] with satellite=(sat_distance, sat_name, sat_pos_ITRS)"""
        #extract sgp4 jd,fr
            #astropy: jd = jd1.jd2 (integer & fractional part)
            #sgp4: offsets by 0.5 i.e. jd1 - 0.5; jd2 + 0.5
        jDay = jd_time.jd1 - 0.5
        jDayF = jd_time.jd2 + 0.5 #fractional part

        raw_pos_TEME, raw_vel_TEME = self.calculate_positions_all(jDay, jDayF)
        raw_pos_TEME = raw_pos_TEME[:, 0, :]
        raw_vel_TEME = raw_vel_TEME[:, 0, :]
        pos_ITRS, vel_ITRS = self.TEME_2_ITRS(jDay, jDayF, raw_pos_TEME, raw_vel_TEME)
        
        # go through all satellites in the TLE-file and find the visible ones (above the horizon)
        # https://math.stackexchange.com/questions/2998875/how-to-determine-if-a-point-is-above-or-below-a-plane-defined-by-a-triangle
        # normalize the rec_ITRS to use it as the normal-vector of the tangential-plane
        
        # type conversion (rec_TITRS desired type: location.itrs.x.value, location.itrs.y.value, location.itrs.z.value)
        rec_ITRS = rec_ITRS.x.value, rec_ITRS.y.value, rec_ITRS.z.value
        normal = rec_ITRS / np.linalg.norm(rec_ITRS)
        
        #distances satellites - receiver
        signed_distances = pos_ITRS - rec_ITRS  # shape(x,3)
        signed_distances = np.dot(signed_distances, normal)
        
        #find satellites with positive distance (negative distance = below plane = below horizon)
        index_positives = np.nonzero(signed_distances > 0)[0] #index of satellites with non-negative distance
        visible_satellites = []
        vis_sat_pos_ITRS = []
        for index in list(index_positives):
            #sat_pos_ITRS = pos_ITRS[index, :]
            sat_pos_ITRS = coord.ITRS(x=pos_ITRS[index, 0]*u.km,y=pos_ITRS[index, 1]*u.km,z=pos_ITRS[index, 2]*u.km,representation_type="cartesian")
            sat_name = self.sat_names[index]
            sat_distance = signed_distances[index]
            visible_satellites.append((sat_distance, sat_name, sat_pos_ITRS)) #sat_pos_ITRS.tolist()
            vis_sat_pos_ITRS.append(sat_pos_ITRS)

        visible_satellites = sorted(visible_satellites, reverse=True) #sorted descending i.e. 1st satellite: biggest distance i.e. best match as close to the plane = close to the horizon
        #print(f'{visible_satellites}\n')
        return visible_satellites #shape: [(distance, name, pos_ITRS)]



