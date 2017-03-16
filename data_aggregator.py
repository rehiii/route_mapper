"""
This script loads the airline datasets,
cuts them down to be anchored in a specified state and short-haul in nature,
and finally aggregates them on a route (origin-destination) level.
"""
from __future__ import print_function

def geocalc(lat0, lon0, lat1, lon1):
    """
    Return the distance (in mi) between two points in geographical coordinates
    """
    EARTH_R = 6372.8 / 1.609 #km to mi
    lat0 = np.radians(lat0)
    lon0 = np.radians(lon0)
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    dlon = lon0 - lon1
    y = np.sqrt(
        (np.cos(lat1) * np.sin(dlon)) ** 2
         + (np.cos(lat0) * np.sin(lat1)
         - np.sin(lat0) * np.cos(lat1) * np.cos(dlon)) ** 2)
    x = np.sin(lat0) * np.sin(lat1) + \
        np.cos(lat0) * np.cos(lat1) * np.cos(dlon)
    c = np.arctan2(y, x)
    return EARTH_R * c

def remove_return_list(l, el):
    """Used for cleaning up the stopover airports list"""
    l.remove(el)
    return l

def airport_data():
    """
    Read in airport data
    Source: http://openflights.org/data.html#airport
    Return pandas dataframe
    """
    airport_data_dir = '{0}/airports'.format(data_dir)
    airports = pd.read_csv('{0}/airports.csv'.format(airport_data_dir), header=None, dtype=str)
    airports.columns = ['id', 'name', 'city', 'country', 'code', 'icao', 'lat', 'lon', 'altitude',
                        'utc_offset', 'dst', 'timezone', 'type', 'source']
    return airports

def aircraft_delay_data(quarter, anchor_state='CA', max_dist=800):
    """
    Read in aircraft delay (a.k.a. on time performance) data
    Note: "ot" stands for "on time"
    Source: On-Time Performance Database in https://www.transtats.bts.gov/Tables.asp?DB_ID=120&DB_Name=Airline%20On-Time%20Performance%20Data&DB_Short_Name=On-Time
    Return pandas dataframe aggregated to a collection of routes
    """
    ot_data_dir = '{0}/aircraft_delays'.format(data_dir)
    ot_files = sorted(glob('{0}/*.csv'.format(ot_data_dir)))
    print('using files {0}'.format(ot_files))
    sys.stdout.flush()
    ot_df_list = []
    for fname in ot_files:
        ot_df_i = pd.read_csv(fname)
        ot_df_list.append(ot_df_i)
    ot_df = pd.concat(ot_df_list)

    # columns to keep
    ot_cols = ['Year', 'Quarter', 'Month', 'DayOfWeek', 'FlightDate',
               'UniqueCarrier', 'AirlineID', 'FlightNum',
               'OriginAirportID', 'Origin', 'OriginState', 'OriginStateName',
               'DestAirportID', 'Dest', 'DestState', 'DestStateName',
               'DepDelay', 'TaxiOut', 'ArrDelay', 'Cancelled', 'CancellationCode',
               'CarrierDelay', 'SecurityDelay', 'WeatherDelay', 'NASDelay', 'LateAircraftDelay',
               'AirTime', 'ActualElapsedTime', 'Flights', 'Distance']

    # cut down to anchor state and max distance
    if quarter:
        ot_ca = ot_df.loc[((ot_df['OriginState'] == anchor_state) | (ot_df['DestState'] == anchor_state)) & \
                          (ot_df['Distance'] < max_dist) & (ot_df['Distance'] > 0) & \
                          (ot_df['Flights'] == 1.0) & (ot_df['Quarter'] == quarter)][ot_cols]
    else:
        ot_ca = ot_df.loc[((ot_df['OriginState'] == anchor_state) | (ot_df['DestState'] == anchor_state)) & \
                          (ot_df['Distance'] < max_dist) & (ot_df['Distance'] > 0) & \
                          (ot_df['Flights'] == 1.0)][ot_cols]

    # merge in airport orig/dest data
    ot_ca_airports_orig = pd.merge(ot_ca, airports,
                                   left_on=['Origin'],
                                   right_on=['code'],
                                   how='inner')
    ot_ca_airports_orig.rename(
        columns={'id': 'orig_id', 'name': 'orig_name', 'city': 'orig_city', 'country': 'orig_country',
                 'code': 'orig_code', 'icao': 'orig_icao', 'lat': 'orig_lat', 'lon': 'orig_lon',
                 'altitude': 'orig_altitude', 'utc_offset': 'orig_utc_offest', 'dst': 'orig_dst',
                 'type': 'orig_type', 'source': 'orig_source'}, inplace=True)
    ot_ca_airports = pd.merge(ot_ca_airports_orig, airports,
                              left_on=['Dest'],
                              right_on=['code'],
                              how='inner')
    ot_ca_airports.rename(columns={'id': 'dest_id', 'name': 'dest_name', 'city': 'dest_city', 'country': 'dest_country',
                                   'code': 'dest_code', 'icao': 'dest_icao', 'lat': 'dest_lat', 'lon': 'dest_lon',
                                   'altitude': 'dest_altitude', 'utc_offset': 'dest_utc_offest', 'dst': 'dest_dst',
                                   'type': 'dest_type', 'source': 'dest_source'}, inplace=True)

    # boolean for airline-caused delays longer than x minutes
    ot_ca_airports['AirlineDelay'] = ot_ca_airports['LateAircraftDelay'] + ot_ca_airports['CarrierDelay']
    ot_ca_airports['AirlineDelay_5'] = ot_ca_airports['AirlineDelay'] > 5.0
    ot_ca_airports['AirlineDelay_10'] = ot_ca_airports['AirlineDelay'] > 10.0
    ot_ca_airports['AirlineDelay_20'] = ot_ca_airports['AirlineDelay'] > 20.0
    ot_ca_airports['AirlineDelay_30'] = ot_ca_airports['AirlineDelay'] > 30.0

    # aggregate stats for each route
    ## median delay time, fraction of delays > x minutes, total flights taken
    orig_stats_cols = ['orig_code', 'orig_name', 'orig_city', 'OriginState', 'orig_lat', 'orig_lon',
                       'DepDelay', 'TaxiOut', 'ArrDelay', 'SecurityDelay', 'WeatherDelay', 'NASDelay',
                       'LateAircraftDelay', 'CarrierDelay', 'AirlineDelay', 'Distance', 'AirTime', 'ActualElapsedTime',
                       'AirlineDelay_5', 'AirlineDelay_10', 'AirlineDelay_20', 'AirlineDelay_30']
    dest_stats_cols = ['dest_code', 'dest_name', 'dest_city', 'DestState', 'dest_lat', 'dest_lon',
                       'DepDelay', 'TaxiOut', 'ArrDelay', 'SecurityDelay', 'WeatherDelay', 'NASDelay',
                       'LateAircraftDelay', 'CarrierDelay', 'AirlineDelay', 'Distance', 'AirTime', 'ActualElapsedTime',
                       'AirlineDelay_5', 'AirlineDelay_10', 'AirlineDelay_20', 'AirlineDelay_30']
    ot_stats_cols = sorted(list(set(orig_stats_cols + dest_stats_cols)))

    ## group and calculate
    med_delay = ot_ca_airports[ot_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'OriginState', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DestState', 'dest_lat', 'dest_lon'],
        as_index=False).median().reset_index()
    med_delay['AirlineDelay_med'] = med_delay['AirlineDelay']

    mean_delay = ot_ca_airports[ot_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'OriginState', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DestState', 'dest_lat', 'dest_lon'],
        as_index=False).mean().reset_index()
    mean_delay['AirlineDelay_10frac'] = mean_delay['AirlineDelay_10']
    mean_delay['AirlineDelay_20frac'] = mean_delay['AirlineDelay_20']
    mean_delay['AirlineDelay_30frac'] = mean_delay['AirlineDelay_30']
    mean_delay['AirlineDelay_mean'] = mean_delay['AirlineDelay']
    mean_delay['Distance_mean'] = mean_delay['Distance']
    mean_delay['AirTime_mean'] = mean_delay['AirTime']
    mean_delay['ActualElapsedTime_mean'] = mean_delay['ActualElapsedTime']

    count_delay = ot_ca_airports.groupby(
        ['orig_code', 'orig_name', 'orig_city', 'OriginState', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DestState', 'dest_lat', 'dest_lon'],
        as_index=False).count().reset_index()
    count_delay['Flight_Count'] = count_delay['Flights']

    med_delay_cols = ['orig_code', 'orig_name', 'orig_city', 'OriginState', 'orig_lat', 'orig_lon',
                               'dest_code', 'dest_name', 'dest_city', 'DestState', 'dest_lat', 'dest_lon',
                               'AirlineDelay_med']
    mean_delay_cols = ['orig_code', 'orig_name', 'orig_city', 'OriginState', 'orig_lat', 'orig_lon',
                             'dest_code', 'dest_name', 'dest_city', 'DestState', 'dest_lat', 'dest_lon',
                             'AirlineDelay_10frac', 'AirlineDelay_20frac', 'AirlineDelay_30frac',
                             'AirlineDelay_mean',
                             'Distance_mean', 'AirTime_mean', 'ActualElapsedTime_mean']
    count_delay_cols = ['orig_code', 'orig_name', 'orig_city', 'OriginState', 'orig_lat', 'orig_lon',
                              'dest_code', 'dest_name', 'dest_city', 'DestState', 'dest_lat', 'dest_lon',
                              'Flight_Count']

    ## merge
    route_med_mean_merge = pd.merge(med_delay[med_delay_cols],
                                       mean_delay[mean_delay_cols],
                                       on=['orig_code', 'orig_name', 'orig_city', 'OriginState', 'orig_lat', 'orig_lon',
                                           'dest_code', 'dest_name', 'dest_city', 'DestState', 'dest_lat', 'dest_lon'],
                                       how='inner')

    route_med_mean_count_merge = pd.merge(route_med_mean_merge, count_delay[count_delay_cols],
                                             on=['orig_code', 'orig_name', 'orig_city', 'OriginState', 'orig_lat',
                                                 'orig_lon',
                                                 'dest_code', 'dest_name', 'dest_city', 'DestState', 'dest_lat', 'dest_lon'],
                                             how='inner')

    route_merge = route_med_mean_count_merge
    print('{0} routes'.format(len(route_merge)))

    return route_merge

def aircraft_occupancy_data(quarter, anchor_state='CA', max_dist=800):
    """
    Read in aircraft occupancy data
    Note: "pas" stands for "passenger"
    Source: T-100 Domestic Segment Database in https://www.transtats.bts.gov/Tables.asp?DB_ID=110&DB_Name=Air%20Carrier%20Statistics%20%28Form%2041%20Traffic%29-%20%20U.S.%20Carriers&DB_Short_Name=Air%20Carriers
    Return pandas dataframe aggregated to a collection of routes
    """
    pas_dir = '{0}/aircraft_occupancy'.format(data_dir)
    pas_files = sorted(glob('{0}/*.csv'.format(pas_dir)))
    print('using files {0}'.format(pas_files))
    sys.stdout.flush()
    pas_df_list = []
    for fname in pas_files:
        pas_df_i = pd.read_csv(fname)
        pas_df_list.append(pas_df_i)
    pas_df = pd.concat(pas_df_list)

    # cut down to anchor state and max distance
    if quarter:
        pas_ca = pas_df.loc[((pas_df['ORIGIN_STATE_ABR'] == anchor_state) | (pas_df['DEST_STATE_ABR'] == anchor_state)) & \
                            (pas_df['DISTANCE'] < max_dist) & (pas_df['DISTANCE'] > 0) & \
                            (pas_df['PASSENGERS'] > 0) & (pas_df['QUARTER'] == quarter)]
    else:
        pas_ca = pas_df.loc[
            ((pas_df['ORIGIN_STATE_ABR'] == anchor_state) | (pas_df['DEST_STATE_ABR'] == anchor_state)) & \
            (pas_df['DISTANCE'] < max_dist) & (pas_df['DISTANCE'] > 0) & \
            (pas_df['PASSENGERS'] > 0)]

    # merge in airport orig/dest data
    pas_ca_airports_orig = pd.merge(pas_ca, airports,
                                    left_on=['ORIGIN'],
                                    right_on=['code'],
                                    how='inner')
    pas_ca_airports_orig.rename(
        columns={'id': 'orig_id', 'name': 'orig_name', 'city': 'orig_city', 'country': 'orig_country',
                 'code': 'orig_code', 'icao': 'orig_icao', 'lat': 'orig_lat', 'lon': 'orig_lon',
                 'altitude': 'orig_altitude', 'utc_offset': 'orig_utc_offest', 'dst': 'orig_dst',
                 'type': 'orig_type', 'source': 'orig_source'}, inplace=True)
    pas_ca_airports = pd.merge(pas_ca_airports_orig, airports,
                               left_on=['DEST'],
                               right_on=['code'],
                               how='inner')
    pas_ca_airports.rename(
        columns={'id': 'dest_id', 'name': 'dest_name', 'city': 'dest_city', 'country': 'dest_country',
                 'code': 'dest_code', 'icao': 'dest_icao', 'lat': 'dest_lat', 'lon': 'dest_lon',
                 'altitude': 'dest_altitude', 'utc_offset': 'dest_utc_offest', 'dst': 'dest_dst',
                 'type': 'dest_type', 'source': 'dest_source'}, inplace=True)

    # aggregate occupancy per route, carrier, aircraft type, month (as close granular as this dataset allows)
    pas_ca_airports['occupancy'] = pas_ca_airports['PASSENGERS'] * 1.0 / pas_ca_airports['SEATS']

    # aggregate stats for each route
    ## total departures, total seats, total passengers,
    pas_stats_cols = ['DEPARTURES_SCHEDULED', 'DEPARTURES_PERFORMED', 'SEATS', 'PASSENGERS', 'occupancy',
                      'DISTANCE', 'RAMP_TO_RAMP', 'AIR_TIME',
                      'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                      'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon',
                      'YEAR', 'MONTH']

    ## group and calculate
    sum_pas = pas_ca_airports[pas_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
        as_index=True).sum().reset_index()
    sum_pas['DEPARTURES_PERFORMED_sum'] = sum_pas['DEPARTURES_PERFORMED']
    sum_pas['SEATS_sum'] = sum_pas['SEATS']
    sum_pas['PASSENGERS_sum'] = sum_pas['PASSENGERS']
    ## this occupancy is an overall measure of seat availability across airlines and aircraft
    ## with a high occupancy_total value, however, smaller aircraft could still offer lower occupancy rates on a given route
    sum_pas['occupancy_total'] = sum_pas['PASSENGERS'] * 1.0 / sum_pas['SEATS']

    med_pas = pas_ca_airports[pas_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
        as_index=True).median().reset_index()
    med_pas['occupancy_med'] = med_pas['occupancy']

    mean_pas = pas_ca_airports[pas_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
        as_index=True).mean().reset_index()
    mean_pas['occupancy_mean'] = mean_pas['occupancy']
    mean_pas['DISTANCE_mean'] = mean_pas['DISTANCE']
    mean_pas['RAMP_TO_RAMP_mean'] = mean_pas['RAMP_TO_RAMP']
    mean_pas['AIR_TIME_mean'] = mean_pas['AIR_TIME']

    sum_pas_cols = ['DEPARTURES_PERFORMED_sum', 'SEATS_sum', 'PASSENGERS_sum', 'occupancy_total',
                    'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                    'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon']
    med_pas_cols = ['occupancy_med',
                    'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                    'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon']
    mean_pas_cols = ['occupancy_mean', 'DISTANCE_mean', 'RAMP_TO_RAMP_mean', 'AIR_TIME_mean',
                     'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                     'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon']
    ## merge
    route_sum_med_merge = pd.merge(sum_pas[sum_pas_cols], med_pas[med_pas_cols],
                             on=['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                                 'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
                             how='inner')

    route_sum_med_mean_merge = pd.merge(route_sum_med_merge, mean_pas[mean_pas_cols],
                                  on=['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                                      'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
                                  how='inner')

    route_merge = route_sum_med_mean_merge
    print('{0} routes'.format(len(route_merge)))

    return route_merge

def flyer_class_data(quarter, anchor_state='CA', max_dist=800):
    """
    Read in flyer class data
    Note: this is the same dataset used for the stopover statistics
        "so" stands for "stopover"
        "cl" stands for "class"
    Source: DB1BCoupon database in https://www.transtats.bts.gov/Tables.asp?DB_ID=125&DB_Name=Airline%20Origin%20and%20Destination%20Survey%20%28DB1B%29&DB_Short_Name=Origin%20and%20Destination%20Survey
    Return pandas dataframe aggregated to a collection of routes
    """
    so_dir = '{0}/air_coupons'.format(data_dir)
    so_files = sorted(glob('{0}/*.csv'.format(so_dir)))
    print('using files {0}'.format(so_files))
    sys.stdout.flush()
    so_df_list = []
    for fname in so_files:
        so_df_i = pd.read_csv(fname)
        so_df_list.append(so_df_i)
    so_df = pd.concat(so_df_list)

    # cut down to anchor state and max distance
    if quarter:
        so_ca = so_df.loc[((so_df['ORIGIN_STATE_ABR'] == anchor_state) | (so_df['DEST_STATE_ABR'] == anchor_state)) & \
                          (so_df['DISTANCE'] < max_dist) & (so_df['DISTANCE'] > 0) & \
                          (so_df['PASSENGERS'] > 0) & (so_df['QUARTER'] == quarter)]
    else:
        so_ca = so_df.loc[((so_df['ORIGIN_STATE_ABR'] == anchor_state) | (so_df['DEST_STATE_ABR'] == anchor_state)) & \
                          (so_df['DISTANCE'] < max_dist) & (so_df['DISTANCE'] > 0) & \
                          (so_df['PASSENGERS'] > 0)]

    # merge in airport orig/dest data
    so_ca_airports_orig = pd.merge(so_ca, airports,
                                   left_on=['ORIGIN'],
                                   right_on=['code'],
                                   how='inner')
    so_ca_airports_orig.rename(
        columns={'id': 'orig_id', 'name': 'orig_name', 'city': 'orig_city', 'country': 'orig_country',
                 'code': 'orig_code', 'icao': 'orig_icao', 'lat': 'orig_lat', 'lon': 'orig_lon',
                 'altitude': 'orig_altitude', 'utc_offset': 'orig_utc_offest', 'dst': 'orig_dst',
                 'type': 'orig_type', 'source': 'orig_source'}, inplace=True)
    so_ca_airports = pd.merge(so_ca_airports_orig, airports,
                              left_on=['DEST'],
                              right_on=['code'],
                              how='inner')
    so_ca_airports.rename(columns={'id': 'dest_id', 'name': 'dest_name', 'city': 'dest_city', 'country': 'dest_country',
                                   'code': 'dest_code', 'icao': 'dest_icao', 'lat': 'dest_lat', 'lon': 'dest_lon',
                                   'altitude': 'dest_altitude', 'utc_offset': 'dest_utc_offest', 'dst': 'dest_dst',
                                   'type': 'dest_type', 'source': 'dest_source'}, inplace=True)

    # boolean for fare class (C,D = business; F,G = first; X,Y = coach)
    ## also treat 3% of nans as coach
    so_ca_airports['class_b'] = (so_ca_airports['FARE_CLASS'] == 'C') | (so_ca_airports['FARE_CLASS'] == 'D')
    so_ca_airports['class_f'] = (so_ca_airports['FARE_CLASS'] == 'F') | (so_ca_airports['FARE_CLASS'] == 'G')
    so_ca_airports['class_bf'] = (so_ca_airports['class_b'] == True) | (so_ca_airports['class_f'] == True)
    so_ca_airports['class_c'] = (so_ca_airports['FARE_CLASS'] == 'X') | (so_ca_airports['FARE_CLASS'] == 'Y') | \
                                pd.isnull(so_ca_airports['FARE_CLASS'])
    ## for passenger-weighted class % because each row is an aggregate of passengers per class
    so_ca_airports['class_bf_w'] = so_ca_airports['class_bf'] * so_ca_airports['PASSENGERS']
    so_ca_airports['class_c_w'] = so_ca_airports['class_c'] * so_ca_airports['PASSENGERS']

    # aggregate stats for each route
    ## total passengers, fraction of tickets of a particular class set
    cl_stats_cols = ['PASSENGERS', 'DISTANCE', 'class_b', 'class_f', 'class_bf', 'class_c', 'class_bf_w', 'class_c_w',
                     'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                     'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon',
                     'YEAR', 'QUARTER']

    ## group and calculate
    sum_cl = so_ca_airports[cl_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
        as_index=True).sum().reset_index()
    sum_cl['PASSENGERS_sum'] = sum_cl['PASSENGERS']
    sum_cl['class_bf_frac'] = sum_cl['class_bf_w'] * 1.0 / sum_cl['PASSENGERS']
    sum_cl['class_c_frac'] = sum_cl['class_c_w'] * 1.0 / sum_cl['PASSENGERS']

    mean_cl = so_ca_airports[cl_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
        as_index=True).mean().reset_index()
    mean_cl['DISTANCE_mean'] = mean_cl['DISTANCE']

    sum_cl_cols = ['PASSENGERS_sum', 'class_bf_frac', 'class_c_frac',
                   'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                   'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon']
    mean_cl_cols = ['DISTANCE_mean',
                    'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                    'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon']

    ## merge
    route_sum_mean_merge = pd.merge(sum_cl[sum_cl_cols], mean_cl[mean_cl_cols],
                                 on=['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                                     'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
                                 how='inner')

    route_merge = route_sum_mean_merge
    print('{0} routes'.format(len(route_merge)))

    return route_merge

def flyer_stopover_data(quarter, anchor_state='CA', max_dist=800):
    """
    Read in flyer stopover data
    Note: this is the same dataset used for the fare class statistics
        "so" stands for "stopover"
    Source: DB1BCoupon database in https://www.transtats.bts.gov/Tables.asp?DB_ID=125&DB_Name=Airline%20Origin%20and%20Destination%20Survey%20%28DB1B%29&DB_Short_Name=Origin%20and%20Destination%20Survey
    Return pandas dataframe aggregated to a collection of routes
    """
    so_dir = '{0}/air_coupons'.format(data_dir)
    so_files = sorted(glob('{0}/*.csv'.format(so_dir)))
    print('using files {0}'.format(so_files))
    sys.stdout.flush()
    so_df_list = []
    for fname in so_files:
        so_df_i = pd.read_csv(fname)
        so_df_list.append(so_df_i)
    so_df = pd.concat(so_df_list)

    # cut down to anchor state and max distance
    if quarter:
        so_ca = so_df.loc[((so_df['ORIGIN_STATE_ABR'] == anchor_state) | (so_df['DEST_STATE_ABR'] == anchor_state)) & \
                          (so_df['DISTANCE'] < max_dist) & (so_df['DISTANCE'] > 0) & \
                          (so_df['PASSENGERS'] > 0) & (so_df['QUARTER'] == quarter)]
    else:
        so_ca = so_df.loc[((so_df['ORIGIN_STATE_ABR'] == anchor_state) | (so_df['DEST_STATE_ABR'] == anchor_state)) & \
                          (so_df['DISTANCE'] < max_dist) & (so_df['DISTANCE'] > 0) & \
                          (so_df['PASSENGERS'] > 0)]

    # merge in airport orig/dest data
    so_ca_airports_orig = pd.merge(so_ca, airports,
                                   left_on=['ORIGIN'],
                                   right_on=['code'],
                                   how='inner')
    so_ca_airports_orig.rename(
        columns={'id': 'orig_id', 'name': 'orig_name', 'city': 'orig_city', 'country': 'orig_country',
                 'code': 'orig_code', 'icao': 'orig_icao', 'lat': 'orig_lat', 'lon': 'orig_lon',
                 'altitude': 'orig_altitude', 'utc_offset': 'orig_utc_offest', 'dst': 'orig_dst',
                 'type': 'orig_type', 'source': 'orig_source'}, inplace=True)
    so_ca_airports = pd.merge(so_ca_airports_orig, airports,
                              left_on=['DEST'],
                              right_on=['code'],
                              how='inner')
    so_ca_airports.rename(columns={'id': 'dest_id', 'name': 'dest_name', 'city': 'dest_city', 'country': 'dest_country',
                                   'code': 'dest_code', 'icao': 'dest_icao', 'lat': 'dest_lat', 'lon': 'dest_lon',
                                   'altitude': 'dest_altitude', 'utc_offset': 'dest_utc_offest', 'dst': 'dest_dst',
                                   'type': 'dest_type', 'source': 'dest_source'}, inplace=True)

    # group by market id (itinerary before prolonged stop) to count stopovers
    count_so_cols = ['MKT_ID', 'SEQ_NUM']
    min_so_cols = ['MKT_ID', 'SEQ_NUM', 'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat',
                   'orig_lon']
    max_so_cols = ['MKT_ID', 'SEQ_NUM', 'PASSENGERS', 'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR',
                   'dest_lat', 'dest_lon',
                   'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon']

    ## row count per market id
    count_so_ca_mkts = so_ca_airports[count_so_cols].groupby(['MKT_ID']).count().reset_index()
    count_so_ca_mkts['mkt_row_count'] = count_so_ca_mkts['SEQ_NUM']
    count_so_ca_mkts['stopovers'] = count_so_ca_mkts['mkt_row_count'] - 1

    ## first and last seq_num and orig and dest per market id
    min_so_ca_mkts = so_ca_airports.sort_values('SEQ_NUM')[min_so_cols].groupby(['MKT_ID'], as_index=False).first()
    min_so_ca_mkts.rename(columns={'SEQ_NUM': 'SEQ_NUM_min'}, inplace=True)
    max_so_ca_mkts = so_ca_airports.sort_values('SEQ_NUM')[max_so_cols].groupby(['MKT_ID'], as_index=False).last()
    max_so_ca_mkts.rename(columns={'SEQ_NUM': 'SEQ_NUM_max'}, inplace=True)
    ## rename stopover location to --_so
    for key in ['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon']:
        max_so_ca_mkts.rename(columns={'{0}'.format(key): '{0}_so'.format(key)}, inplace=True)

    # merge
    so_count_min_merge = pd.merge(count_so_ca_mkts, min_so_ca_mkts,
                                  on=['MKT_ID'],
                                  how='inner')

    so_count_min_max_merge = pd.merge(so_count_min_merge, max_so_ca_mkts,
                                      on=['MKT_ID'],
                                      how='inner')

    so_ca_merge = so_count_min_max_merge

    so_ca_merge['stopover_false'] = so_ca_merge['stopovers'] == 0
    so_ca_merge['stopover_true'] = so_ca_merge['stopovers'] > 0

    # aggregate stats for each route
    ## total passengers, fraction of itineraries with stopovers
    so_stats_cols = ['stopover_false', 'stopover_true', 'PASSENGERS', 'stopovers',
                     'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                     'orig_code_so', 'orig_name_so', 'orig_city_so', 'ORIGIN_STATE_ABR_so', 'orig_lat_so',
                     'orig_lon_so',
                     'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon']

    ## group and calculate
    mean_so = so_ca_merge[so_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
        as_index=True).mean().reset_index()
    mean_so['stopover_frac'] = mean_so['stopover_true']
    mean_so['no_stopover_frac'] = mean_so['stopover_false']
    mean_so['stopovers_mean'] = mean_so['stopovers']

    sum_so = so_ca_merge[so_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
        as_index=True).sum().reset_index()
    sum_so['PASSENGERS_sum'] = sum_so['PASSENGERS']

    set_so = so_ca_merge[so_stats_cols].groupby(
        ['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
         'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
        as_index=True)['orig_code_so'].apply(set).reset_index() # use set to get unique values
    set_so['stopover_airports'] = set_so['orig_code_so']

    mean_so_cols = ['stopover_frac', 'no_stopover_frac', 'stopovers_mean',
                    'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                    'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon']
    sum_so_cols = ['PASSENGERS_sum',
                   'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                   'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon']
    set_so_cols = ['stopover_airports',
                   'orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                   'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon']

    ## merge
    route_sum_mean_merge = pd.merge(sum_so[sum_so_cols], mean_so[mean_so_cols],
                                 on=['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat', 'orig_lon',
                                     'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat', 'dest_lon'],
                                 how='inner')

    route_sum_mean_set_merge = pd.merge(route_sum_mean_merge, set_so[set_so_cols],
                                     on=['orig_code', 'orig_name', 'orig_city', 'ORIGIN_STATE_ABR', 'orig_lat',
                                         'orig_lon',
                                         'dest_code', 'dest_name', 'dest_city', 'DEST_STATE_ABR', 'dest_lat',
                                         'dest_lon'],
                                     how='inner')

    ## merge
    route_merge = route_sum_mean_set_merge

    ## remove orig from stopover_airports
    route_merge['stopover_airports_clean'] = route_merge.apply(lambda f: remove_return_list(list(f['stopover_airports']),f['orig_code']) if f['orig_code'] in list(f['stopover_airports']) \
                                                           else list(f['stopover_airports']), axis=1)
    ## ensure short-haul routes from orig to dest, still anchored in anchor state
    route_merge['dist_calc'] = route_merge.apply(lambda f: geocalc(float(f['orig_lat']), float(f['orig_lon']),
                                                             float(f['dest_lat']), float(f['dest_lon'])), axis=1)
    route_merge_short = route_merge.loc[((route_merge['ORIGIN_STATE_ABR'] == anchor_state) | (route_merge['DEST_STATE_ABR'] == anchor_state)) & \
                                         (route_merge['dist_calc'] < max_dist)]

    print('{0} routes'.format(len(route_merge_short)))

    return route_merge_short


if __name__ == '__main__':
    import numpy as np
    import pandas as pd
    from glob import glob
    import sys
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='This script loads the airline datasets,\n'
                                        'cuts them down to be anchored in CA and short-haul flights,\n'
                                        'and finally aggregates them on a route (origin-destination) level.',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-q', '--quarter', dest='quarter',
                        default=None, metavar='QUARTER', type=int,
                        help='QUARTER over which to aggregate data, default None aggregates over all quarters')
    parser.add_argument('--air-delay', dest='air_delay',
                        default=False, action='store_true',
                        help='Create route aircraft delay dataset')
    parser.add_argument('--air-occ', dest='air_occ',
                        default=False, action='store_true',
                        help='Create route aircraft occupancy dataset')
    parser.add_argument('--air-class', dest='air_class',
                        default=False, action='store_true',
                        help='Create flyer fare class dataset')
    parser.add_argument('--air-stopover', dest='air_stopover',
                        default=False, action='store_true',
                        help='Create flyer stopover dataset')
    parser.add_argument('--anchor-state', dest='anchor_state',
                        default='CA',
                        help='Orig or Dest for each route must be in this anchor state')
    parser.add_argument('--max-dist', dest='max_dist',
                        default=800,
                        help='Maximum distance in miles of routes')
    args = parser.parse_args()

    # input directory
    # data_dir = 'data'
    data_dir = 'E://blackbird_data/script_data'

    # output directory
    if args.quarter:
        output_dir = 'data/aggregated/q{0}'.format(args.quarter)
        print('for quarter {0}...'.format(args.quarter))
        sys.stdout.flush()
    else:
        output_dir = 'data/aggregated'
        print('for all quarters...')
        sys.stdout.flush()

    # Airport Data (need for all)
    airports = airport_data()

    # Aircraft Delay Data
    if args.air_delay:
        print('creating {0}/aircraft_delay_routes.csv...'.format(output_dir))
        sys.stdout.flush()
        aircraft_delay_routes = aircraft_delay_data(quarter=args.quarter, anchor_state=args.anchor_state, max_dist=args.max_dist)
        aircraft_delay_routes.to_csv('{0}/aircraft_delay_routes.csv'.format(output_dir), index=False)

    # Aircraft Occupancy Data
    if args.air_occ:
        print('creating {0}/aircraft_occupancy_routes.csv...'.format(output_dir))
        sys.stdout.flush()
        aircraft_occupancy_routes = aircraft_occupancy_data(quarter=args.quarter, anchor_state=args.anchor_state, max_dist=args.max_dist)
        aircraft_occupancy_routes.to_csv('{0}/aircraft_occupancy_routes.csv'.format(output_dir), index=False)

    # Amtrak Locations, Delays + Nearest Airport Data
    ## amtrak_stations.csv copied from
    ## ca_amtrak_station_ridership_2016.csv copied from
    ## delay data from https://juckins.net/amtrak_status/archive/html/resources.php (scraper of amtrak site) to query 2016 delay data for each of the above station codes
    ## combined all with airports data, using geocalc function to find nearest airports
    ## saved to ca_amtrak_airports_ridership_delays.csv
    ## manually removed non-CA stations (e.g. Richmond, Colfax) from ca_amtrak_airports_ridership_delays.csv

    # Flyer Fare Class Data
    if args.air_class:
        print('creating {0}/flyer_class_routes.csv...'.format(output_dir))
        sys.stdout.flush()
        flyer_class_routes = flyer_class_data(quarter=args.quarter, anchor_state=args.anchor_state, max_dist=args.max_dist)
        flyer_class_routes.to_csv('{0}/flyer_class_routes.csv'.format(output_dir), index=False)

    # Flyer Stopover Data
    if args.air_stopover:
        print('creating {0}/flyer_stopover_routes.csv...'.format(output_dir))
        sys.stdout.flush()
        flyer_stopover_routes = flyer_stopover_data(quarter=args.quarter, anchor_state=args.anchor_state, max_dist=args.max_dist)
        flyer_stopover_routes.to_csv('{0}/flyer_stopover_routes.csv'.format(output_dir), index=False)