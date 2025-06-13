import src.constellation_generation.by_TLE.download_TLE_data as DOWNLOAD_TLE_DATA
import h5py
from datetime import datetime
import numpy as np
import json

def view_constellation_TLE_data(constellation_name):
    file_path = '/Users/bytedance/Desktop/StarPerf_Simulator/StarPerf_Simulator/config/TLE_constellation/' + constellation_name + '/tle.h5'
    with h5py.File(file_path, 'a') as file:
        current_date = datetime.now()
        formatted_date = current_date.strftime('%Y%m%d')
        TLE_group = file[formatted_date]
        TLE_2LE = np.array(TLE_group[formatted_date + '-2LE']).tolist()
        TLE_2LE = [item.decode('utf-8') for item in TLE_2LE]
        TLE_JSON = np.array(TLE_group[formatted_date + '-json']).tolist()
        TLE_JSON = [item.decode('utf-8') for item in TLE_JSON]
        # convert string to JSON object
        TLE_JSON = [json.loads(item) for item in TLE_JSON]

    print('\t\t\t2LE format TLE data : ')
    for tle in TLE_2LE:
        print("\t\t\t" , tle)
    # print('\t\t\tJSON format TLE data : ')
    # for tle in TLE_JSON:
    #     print("\t\t\t", tle)

if __name__ == '__main__':
    view_constellation_TLE_data("Starlink")