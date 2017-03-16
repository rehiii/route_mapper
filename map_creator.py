"""
This script loads the aggregated route airline and Amtrak datasets,
performs a loose cut on infrequently flown routes to ensure consistency,
combines them, and finally creates an interactive map to visualize the routes and their metrics.
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

def midpoint(orig_lat, orig_lon, dest_lat, dest_lon):
    return (float(orig_lat)+float(dest_lat))*1.0 / 2, (float(orig_lon)+float(dest_lon))*1.0/2

def airport_data():
    """
    Read in airport data
    Source: http://openflights.org/data.html#airport
    Return pandas dataframe
    """
    airport_data_dir = 'data/airports'
    airports = pd.read_csv('{0}/airports.csv'.format(airport_data_dir), header=None, dtype=str)
    airports.columns = ['id', 'name', 'city', 'country', 'code', 'icao', 'lat', 'lon', 'altitude',
                        'utc_offset', 'dst', 'timezone', 'type', 'source']
    return airports


if __name__ == '__main__':
    import numpy as np
    import pandas as pd
    import folium
    import sys
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='This script loads the aggregated route airline and Amtrak datasets,\n'
                                        'performs a loose cut on infrequently flown routes to ensure consistency,\n'
                                        'combines them, and finally creates an interactive map to visualize the routes and their metrics.',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-q', '--quarter', dest='quarter',
                        default=None, metavar='QUARTER',
                        help='QUARTER over which to create the map, default None aggregates over all')
    parser.add_argument('--monthly-flights', dest='monthly_flights',
                        default=50,
                        help='Minimum monthly flights over a route to ensure consistent pool of travelers')
    parser.add_argument('--monthly-passengers', dest='monthly_passengers',
                        default=1000,
                        help='Minimum monthly passengers over a route to ensure consistent pool of travelers')
    args = parser.parse_args()

    # Input directory
    if args.quarter:
        input_dir = 'data/aggregated/q{0}'.format(args.quarter)
        months = 3
        mapname_suffix = '_Q{0}'.format(args.quarter)
    else:
        input_dir = 'data/aggregated'
        months = 12
        mapname_suffix = '_Full_Year'

    # use entire year dataset for amtrak inputs (retrieved less programmatically - see documentation)
    amtrak_input_dir = 'data/amtrak'

    # output directory
    map_dir = 'maps'

    print('creating {0}/Route_Mapper{1}.html...'.format(map_dir, mapname_suffix))
    sys.stdout.flush()

    # load data
    aircraft_delay_routes = pd.read_csv('{0}/aircraft_delay_routes.csv'.format(input_dir))
    aircraft_occupancy_routes = pd.read_csv('{0}/aircraft_occupancy_routes.csv'.format(input_dir))
    amtrak = pd.read_csv('{0}/ca_amtrak_airports_ridership_delays.csv'.format(amtrak_input_dir))
    flyer_class_routes = pd.read_csv('{0}/flyer_class_routes.csv'.format(input_dir))
    flyer_stopover_routes = pd.read_csv('{0}/flyer_stopover_routes.csv'.format(input_dir))

    # Airport Data (need for amtrak station - airport mapping)
    airports = airport_data()
    airports_usa = airports.loc[airports['country'] == 'United States']

    # light cut to ensure consistently traveled routes
    flight_cut = args.monthly_flights * months
    pass_cut = args.monthly_passengers * months
    ## delay (ot = on time)
    ot_routes0 = aircraft_delay_routes.loc[aircraft_delay_routes['Flight_Count'] > flight_cut]
    ## occupancy (occ)
    occ_routes0 = aircraft_occupancy_routes.loc[aircraft_occupancy_routes['DEPARTURES_PERFORMED_sum'] > flight_cut]
    ## class (cl); 0.1 factor because data is 10% sample of all tickets
    cl_routes = flyer_class_routes.loc[flyer_class_routes['PASSENGERS_sum'] > pass_cut * 0.1]
    ## stopover (so); 0.1 factor because data is 10% sample of all tickets
    so_routes = flyer_stopover_routes.loc[flyer_stopover_routes['PASSENGERS_sum'] > pass_cut * 0.1]

    # add in fare class data to delay and occupancy data to show where available
    cl_routes_cols = ['class_bf_frac',
                      'orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon',
                      'dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']
    ot_routes_cl = pd.merge(ot_routes0, cl_routes[cl_routes_cols],
                            on=['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon',
                                'dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon'],
                            how='left')
    ot_routes_cols = list(ot_routes0.columns) + ['class_bf_frac']
    ot_routes = ot_routes_cl[ot_routes_cols]
    ot_routes['class_bf_frac'].fillna('no data', inplace=True)

    occ_routes_cl = pd.merge(occ_routes0, cl_routes[cl_routes_cols],
                             on=['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon',
                                 'dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon'],
                             how='left')
    occ_routes_cols = list(occ_routes0.columns) + ['class_bf_frac']
    occ_routes = occ_routes_cl[occ_routes_cols]
    occ_routes['class_bf_frac'].fillna('no data', inplace=True)

    # top route cuts per metric
    ot_routes_20 = ot_routes.sort_values(['AirlineDelay_20frac'], ascending=False).iloc[:20]
    ot_routes_40 = ot_routes.sort_values(['AirlineDelay_20frac'], ascending=False).iloc[:40]
    occ_routes_20 = occ_routes.sort_values(['occupancy_mean'], ascending=False).iloc[:20]
    occ_routes_40 = occ_routes.sort_values(['occupancy_mean'], ascending=False).iloc[:40]
    ot_amtrak_20 = amtrak.sort_values(['delay_avg'], ascending=False).iloc[:20]
    cl_routes_20 = cl_routes.sort_values(['class_bf_frac'], ascending=False).iloc[:20]
    cl_routes_40 = cl_routes.sort_values(['class_bf_frac'], ascending=False).iloc[:40]
    so_routes_20 = so_routes.sort_values(['stopover_frac'], ascending=False).iloc[:20]
    so_routes_40 = so_routes.sort_values(['stopover_frac'], ascending=False).iloc[:40]

    # find overlapping routes in above datasets
    ## ot + occ
    ot_occ_routes = pd.merge(ot_routes_40, occ_routes_40,
                             on=['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon',
                                 'dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon'],
                             how='inner')
    ot_occ_routes.rename(columns={'class_bf_frac_x': 'class_bf_frac'}, inplace=True)
    ## ot + cl
    ot_cl_routes = pd.merge(ot_routes_40, cl_routes_40,
                            on=['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon',
                                'dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon'],
                            how='inner')
    ot_cl_routes.rename(columns={'class_bf_frac_x': 'class_bf_frac'}, inplace=True)
    ## occ + cl
    occ_cl_routes = pd.merge(occ_routes_40, cl_routes_40,
                             on=['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon',
                                 'dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon'],
                             how='inner')
    occ_cl_routes.rename(columns={'class_bf_frac_x': 'class_bf_frac',
                                  'PASSENGERS_sum_x': 'PASSENGERS_sum',
                                  'DISTANCE_mean_x': 'DISTANCE_mean'}, inplace=True)
    ## ot + occ + cl
    ot_occ_cl_routes = pd.merge(ot_occ_routes, cl_routes_40,
                                on=['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon',
                                    'dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon'],
                                how='inner')
    ot_occ_cl_routes.rename(columns={'class_bf_frac_x': 'class_bf_frac',
                                     'PASSENGERS_sum_x': 'PASSENGERS_sum',
                                     'DISTANCE_mean_x': 'DISTANCE_mean'}, inplace=True)

    # create map -- A lot of code! but just iterating on the same block for the 10 groups below
    la_coords = [43, -118] # center map on LA
    m = folium.Map(location=la_coords, zoom_start=5, tiles='stamentoner')
    # groups for layers
    g1 = folium.FeatureGroup(name='Airline Delays (top 20 routes)')
    g2 = folium.FeatureGroup(name='Aircraft Occupancy (top 20 routes)')
    g3 = folium.FeatureGroup(name='First/Business Class (top 20 routes)')
    g4 = folium.FeatureGroup(name='Stopovers (top 20 routes)')
    g5 = folium.FeatureGroup(name='Amtrak Stations and Nearest Airports')
    g6 = folium.FeatureGroup(name='Amtrak Delays (top 20 stations)')
    g7 = folium.FeatureGroup(name='Airline Delays & Occupancy (in top 40 of each)')
    g8 = folium.FeatureGroup(name='Airline Delays & First/Business (in top 40 of each)')
    g9 = folium.FeatureGroup(name='Occupancy & First/Business (in top 40 of each)')
    g10 = folium.FeatureGroup(name='Airline Delays & Occupancy & First/Business (in top 40 of each)')

    ############# Airline Delays (top 20 routes) #############
    orig_list = []
    dest_no_orig_list = []
    orig_dest_list = []
    # get origin airport data to plot
    for row in ot_routes_20.iterrows():
        origin, orig_name, orig_city, orig_lat, orig_lon = row[1][
            ['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon']]
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        delay_mean_route, delay_20pct_route, flight_count_route = row[1][['AirlineDelay_mean',
                                                                          'AirlineDelay_20frac', 'Flight_Count']]
        dist_mean_route, airtime_mean_route, elapsed_mean_route = row[1][['Distance_mean', 'AirTime_mean',
                                                                          'ActualElapsedTime_mean']]
        bf_frac = row[1][['class_bf_frac']]
        try:
            bf_pct = '{0:.1f}%'.format(float(bf_frac) * 100)
        except:
            bf_pct = 'no data for'

        # only 1 marker per airport
        if origin not in orig_list:
            html = """{0} {1}<BR>{2}""".format(origin, orig_name, orig_city)
            iframe = folium.element.IFrame(html=html, width=300, height=150)
            popup = folium.Popup(iframe, max_width=1000)
            g2.add_child(folium.Marker([orig_lat, orig_lon], popup=popup))
            orig_list.append(origin)

        # plot straight line for route from orig to dest
        g1.add_child(
            folium.PolyLine([[float(orig_lat), float(orig_lon)], [float(dest_lat), float(dest_lon)]], color='green',
                            weight=3))

        # plot marker in center of route with route stats(perturb lon coord if out and back routes both included)
        if set([orig_name, dest_name]) not in orig_dest_list:
            p = 0
        else:
            p = .2
        route_lat, route_lon = midpoint(orig_lat, orig_lon, dest_lat, dest_lon)
        html = """{0} {1}<BR>to<BR>{2} {3}<BR><BR><font color="green">{4}</font> Total Flights<BR><BR>""" \
               """{5} mi<BR>{6:.1f} min. avg. Air Time<BR>{7:.1f} min. avg. Elapsed Gate to Gate<BR><BR>""" \
               """<font color="green">{8}</font> First/Business Flyers (from 10% sample of domestic tickets)<BR><BR>""" \
               """<font color="red">{9:.1f}%</font> Aircraft Delay > 20 min<BR>""" \
               """<font color="red">{10} min.</font> avg. Aircraft Delay time for non-weather and non-airport ops delays""".format(
            origin,
            orig_city, dest, dest_city, flight_count_route, int(dist_mean_route), airtime_mean_route,
            elapsed_mean_route,
            bf_pct, delay_20pct_route * 100, int(delay_mean_route))
        iframe = folium.element.IFrame(html=html, width=300, height=400)
        popup = folium.Popup(iframe, max_width=1000)
        g1.add_child(folium.Marker([route_lat, route_lon + p], popup=popup,
                                   icon=folium.Icon(color='green')))
        orig_dest_list.append(set([orig_name, dest_name]))

    # get dest airports with no returns in data (not an origin)
    for row in ot_routes_20.iterrows():
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        if dest not in orig_list:
            html = """{0} {1}<BR>{2}""".format(dest, dest_name, dest_city)
            iframe = folium.element.IFrame(html=html, width=300, height=100)
            popup = folium.Popup(iframe, max_width=1000)
            g1.add_child(folium.Marker([dest_lat, dest_lon], popup=popup))
            dest_no_orig_list.append([dest, dest_name, dest_city])

    ############# Aircraft Occupancy (top 20 routes) #############
    orig_list = []
    dest_no_orig_list = []
    orig_dest_list = []
    # get origin airport data to plot
    for row in occ_routes_20.iterrows():
        origin, orig_name, orig_city, orig_lat, orig_lon = row[1][
            ['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon']]
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        passenger_sum, occupancy_mean, departures_sum = row[1][
            ['PASSENGERS_sum', 'occupancy_mean', 'DEPARTURES_PERFORMED_sum']]
        dist_mean_route = row[1]['DISTANCE_mean']
        bf_frac = row[1][['class_bf_frac']]
        try:
            bf_pct = '{0:.1f}%'.format(float(bf_frac) * 100)
        except:
            bf_pct = 'no data for'

        # only 1 marker per airport
        if origin not in orig_list:
            html = """{0} {1}<BR>{2}""".format(origin, orig_name, orig_city)
            iframe = folium.element.IFrame(html=html, width=300, height=150)
            popup = folium.Popup(iframe, max_width=1000)
            g2.add_child(folium.Marker([orig_lat, orig_lon], popup=popup))
            orig_list.append(origin)

        # plot straight line for route from orig to dest
        g2.add_child(
            folium.PolyLine([[float(orig_lat), float(orig_lon)], [float(dest_lat), float(dest_lon)]], color='green',
                            weight=3))

        # plot marker in center of route with route stats (perturb lon coord if out and back routes both included)
        if set([orig_name, dest_name]) not in orig_dest_list:
            p = 0
        else:
            p = .3
        route_lat, route_lon = midpoint(orig_lat, orig_lon, dest_lat, dest_lon)
        html = """{0} {1}<BR>to<BR>{2} {3}<BR><BR>""" \
               """<font color="green">{4}</font> Total Passengers<BR>""" \
               """<font color="green">{5}</font> Total Departures<BR>{6} mi<BR><Br>""" \
               """<font color="green">{7}</font> First/Business Flyers (from 10% sample of domestic tickets)<BR><BR>""" \
               """<font color="red">{8:.1f}%</font> avg. Occupancy<BR><BR>""".format(origin,
                                                                                     orig_city, dest, dest_city,
                                                                                     int(passenger_sum),
                                                                                     int(departures_sum),
                                                                                     int(dist_mean_route), bf_pct,
                                                                                     occupancy_mean * 100)
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        g2.add_child(folium.Marker([route_lat, route_lon + p], popup=popup,
                                   icon=folium.Icon(color='green')))
        orig_dest_list.append(set([orig_name, dest_name]))

    # get dest airports with no returns in data (not an origin)
    for row in occ_routes_20.iterrows():
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        if dest not in orig_list:
            html = """{0} {1}<BR>{2}""".format(dest, dest_name, dest_city)
            iframe = folium.element.IFrame(html=html, width=300, height=100)
            popup = folium.Popup(iframe, max_width=1000)
            g2.add_child(folium.Marker([dest_lat, dest_lon], popup=popup))
            dest_no_orig_list.append([dest, dest_name, dest_city])

    ############# First/Business Class (top 20 routes) #############
    orig_list = []
    dest_no_orig_list = []
    orig_dest_list = []
    # get origin airport data to plot
    for row in cl_routes_20.iterrows():
        origin, orig_name, orig_city, orig_lat, orig_lon = row[1][
            ['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon']]
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        passenger_sum, dist_mean_route = row[1][['PASSENGERS_sum', 'DISTANCE_mean']]
        class_bf, class_c = row[1][['class_bf_frac', 'class_c_frac']]

        # only 1 marker per airport
        if origin not in orig_list:
            html = """{0} {1}<BR>{2}""".format(origin, orig_name, orig_city)
            iframe = folium.element.IFrame(html=html, width=300, height=150)
            popup = folium.Popup(iframe, max_width=1000)
            g3.add_child(folium.Marker([orig_lat, orig_lon], popup=popup))
            orig_list.append(origin)

        # plot straight line for route from orig to dest
        g3.add_child(
            folium.PolyLine([[float(orig_lat), float(orig_lon)], [float(dest_lat), float(dest_lon)]], color='green',
                            weight=3))

        # plot marker in center of route with route stats(perturb lon coord if out and back routes both included)
        if set([orig_name, dest_name]) not in orig_dest_list:
            p = 0
        else:
            p = .2
        route_lat, route_lon = midpoint(orig_lat, orig_lon, dest_lat, dest_lon)
        html = """{0} {1}<BR>to<BR>{2} {3}<BR><BR>""" \
               """ (10% sample of domestic tickets)<Br><font color="green">{4}</font> Total Passengers<BR>""" \
               """{5} mi<BR><Br>""" \
               """<font color="green">{6}%</font> First/Business Flyers<BR>{7}% Coach Flyers""".format(origin,
                                                                                                               orig_city,
                                                                                                               dest,
                                                                                                               dest_city,
                                                                                                               int(
                                                                                                                   passenger_sum),
                                                                                                               int(
                                                                                                                   dist_mean_route),
                                                                                                               class_bf * 100,
                                                                                                               class_c * 100)
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        g3.add_child(folium.Marker([route_lat, route_lon + p], popup=popup,
                                   icon=folium.Icon(color='green')))
        orig_dest_list.append(set([orig_name, dest_name]))

        # get dest airports with no returns in data (not an origin)
    for row in cl_routes_20.iterrows():
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        if dest not in orig_list:
            html = """{0} {1}<BR>{2}""".format(dest, dest_name, dest_city)
            iframe = folium.element.IFrame(html=html, width=300, height=100)
            popup = folium.Popup(iframe, max_width=1000)
            g3.add_child(folium.Marker([dest_lat, dest_lon], popup=popup))
            dest_no_orig_list.append([dest, dest_name, dest_city])

    ############# Stopovers (top 20 routes) #############
    orig_list = []
    dest_no_orig_list = []
    orig_dest_list = []
    # get origin airport data to plot
    for row in so_routes_20.iterrows():
        origin, orig_name, orig_city, orig_lat, orig_lon = row[1][
            ['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon']]
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        passenger_sum, approx_dist = row[1][['PASSENGERS_sum', 'dist_calc']]
        so_frac, no_so_frac, so_airports = row[1][['stopover_frac', 'no_stopover_frac', 'stopover_airports_clean']]

        # only 1 marker per airport
        if origin not in orig_list:
            html = """{0} {1}<BR>{2}""".format(origin, orig_name, orig_city)
            iframe = folium.element.IFrame(html=html, width=300, height=150)
            popup = folium.Popup(iframe, max_width=1000)
            g4.add_child(folium.Marker([orig_lat, orig_lon], popup=popup))
            orig_list.append(origin)

        # plot straight line for route from orig to dest
        g4.add_child(
            folium.PolyLine([[float(orig_lat), float(orig_lon)], [float(dest_lat), float(dest_lon)]], color='green',
                            weight=3))

        # plot marker in center of route with route stats(perturb lon coord if out and back routes both included)
        if set([orig_name, dest_name]) not in orig_dest_list:
            p = 0
        else:
            p = .2
        route_lat, route_lon = midpoint(orig_lat, orig_lon, dest_lat, dest_lon)
        html = """{0} {1}<BR>to<BR>{2} {3}<BR>""" \
               """~{4} mi<BR><BR>""" \
               """(10% sample of domestic tickets)<Br><font color="green">{5}</font> Total Passengers<BR><BR>""" \
               """<font color="red">{6:.1f}%</font> stopovers<BR>(through {7})""".format(origin,
                                                                                         orig_city, dest, dest_city,
                                                                                         int(approx_dist),
                                                                                         int(passenger_sum),
                                                                                         so_frac * 100, so_airports)
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        g4.add_child(folium.Marker([route_lat, route_lon + p], popup=popup,
                                   icon=folium.Icon(color='green')))
        orig_dest_list.append(set([orig_name, dest_name]))

        # get dest airports with no returns in data (not an origin)
    for row in so_routes_20.iterrows():
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        if dest not in orig_list:
            html = """{0} {1}<BR>{2}""".format(dest, dest_name, dest_city)
            iframe = folium.element.IFrame(html=html, width=300, height=100)
            popup = folium.Popup(iframe, max_width=1000)
            g4.add_child(folium.Marker([dest_lat, dest_lon], popup=popup))
            dest_no_orig_list.append([dest, dest_name, dest_city])

    ############# Amtrak Stations and Nearest Airports #############
    a_list = []
    # get origin airport data to plot
    for row in amtrak.iterrows():
        t_code, t_city, users, t_delay_avg, t_lat, t_lon = row[1][['City', 'code', 'Users', 'delay_avg', 'lat', 'lon']]
        a1_code, a1_name, a1_city, a1_dist = row[1][
            ['closest_a1_code', 'closest_a1_name', 'closest_a1_city', 'closest_a1_dist']]
        a1_lat, a1_lon = airports_usa.loc[airports_usa['name'] == a1_name, ['lat', 'lon']].values[0]
        a2_code, a2_name, a2_city, a2_dist = row[1][
            ['closest_a2_code', 'closest_a2_name', 'closest_a2_city', 'closest_a2_dist']]
        a2_lat, a2_lon = airports_usa.loc[airports_usa['name'] == a2_name, ['lat', 'lon']].values[0]

        # plot Amtrak station, users, delay, and nearest airport info
        html = """{0} {1} Amtrak Station<BR>""" \
               """<font color="green">{2}</font> 2016 users<BR>""" \
               """<font color="red">{3} min.</font> avg. delay in 2016<BR><BR>""" \
               """Nearest airport is {4}, {5}<BR>{6} mi away<BR><BR>""" \
               """Next nearest airport is {7}, {8}<BR>{9} mi away""".format(t_city, t_code, users, t_delay_avg,
                                                                            a1_name, a1_city, int(a1_dist),
                                                                            a2_name, a2_city, int(a2_dist))
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        g5.add_child(folium.Marker([t_lat, t_lon], popup=popup,
                                   icon=folium.Icon(color='red')))

        # plot thin line from Amtrak station to 2 closest airports
        g5.add_child(
            folium.PolyLine([[float(t_lat), float(t_lon)], [float(a1_lat), float(a1_lon)]], color='red', weight=2))
        g5.add_child(
            folium.PolyLine([[float(t_lat), float(t_lon)], [float(a2_lat), float(a2_lon)]], color='red', weight=2))

        html = """{0} {1}<BR>{2}""".format(a1_code, a1_name, a1_city)
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        if a1_name not in a_list:
            g5.add_child(folium.Marker([a1_lat, a1_lon], popup=popup,
                                       icon=folium.Icon()))

        html = """{0} {1}<BR>{2}""".format(a2_code, a2_name, a2_city)
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        if a2_name not in a_list:
            g5.add_child(folium.Marker([a2_lat, a2_lon], popup=popup,
                                       icon=folium.Icon()))
        a_list.append(a1_name)
        a_list.append(a2_name)

    ############# Amtrak Delays (top 20 stations) #############
    a_list = []
    # get origin airport data to plot
    for row in ot_amtrak_20.iterrows():
        t_code, t_city, users, t_delay_avg, t_lat, t_lon = row[1][['City', 'code', 'Users', 'delay_avg', 'lat', 'lon']]
        a1_code, a1_name, a1_city, a1_dist = row[1][
            ['closest_a1_code', 'closest_a1_name', 'closest_a1_city', 'closest_a1_dist']]
        a1_lat, a1_lon = airports_usa.loc[airports_usa['name'] == a1_name, ['lat', 'lon']].values[0]
        a2_code, a2_name, a2_city, a2_dist = row[1][
            ['closest_a2_code', 'closest_a2_name', 'closest_a2_city', 'closest_a2_dist']]
        a2_lat, a2_lon = airports_usa.loc[airports_usa['name'] == a2_name, ['lat', 'lon']].values[0]

        # plot Amtrak station, users, delay, and nearest airport info
        html = """{0} {1} Amtrak Station<BR>""" \
               """<font color="green">{2}</font> 2016 users<BR>""" \
               """<font color="red">{3} min.</font> avg. delay in 2016<BR><BR>""" \
               """Nearest airport is {4}, {5}<BR>{6} mi away<BR><BR>""" \
               """Next nearest airport is {7}, {8}<BR>{9} mi away""".format(t_city, t_code, users, t_delay_avg,
                                                                            a1_name, a1_city, int(a1_dist),
                                                                            a2_name, a2_city, int(a2_dist))
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        g6.add_child(folium.Marker([t_lat, t_lon], popup=popup,
                                   icon=folium.Icon(color='red')))

        # plot thin line from Amtrak station to 2 closest airports
        g6.add_child(
            folium.PolyLine([[float(t_lat), float(t_lon)], [float(a1_lat), float(a1_lon)]], color='red', weight=2))
        g6.add_child(
            folium.PolyLine([[float(t_lat), float(t_lon)], [float(a2_lat), float(a2_lon)]], color='red', weight=2))

        html = """{0} {1}<BR>{2}""".format(a1_code, a1_name, a1_city)
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        if a1_name not in a_list:
            g6.add_child(folium.Marker([a1_lat, a1_lon], popup=popup,
                                       icon=folium.Icon()))

        html = """{0} {1}<BR>{2}""".format(a2_code, a2_name, a2_city)
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        if a2_name not in a_list:
            g6.add_child(folium.Marker([a2_lat, a2_lon], popup=popup,
                                       icon=folium.Icon()))
        a_list.append(a1_name)
        a_list.append(a2_name)

    ############# Airline Delays & Occupancy (in top 40 of each) #############
    orig_list = []
    dest_no_orig_list = []
    orig_dest_list = []
    # get origin airport data to plot
    for row in ot_occ_routes.iterrows():
        origin, orig_name, orig_city, orig_lat, orig_lon = row[1][
            ['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon']]
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        delay_mean_route, delay_20pct_route, flight_count_route = row[1][['AirlineDelay_mean',
                                                                          'AirlineDelay_20frac', 'Flight_Count']]
        airtime_mean_route, elapsed_mean_route = row[1][['AirTime_mean', 'ActualElapsedTime_mean']]
        passenger_sum, occupancy_mean, departures_sum = row[1][
            ['PASSENGERS_sum', 'occupancy_mean', 'DEPARTURES_PERFORMED_sum']]
        dist_mean_route = row[1][['DISTANCE_mean']]

        bf_frac = row[1][['class_bf_frac']]
        try:
            bf_pct = '{0:.1f}%'.format(float(bf_frac) * 100)
        except:
            bf_pct = 'no data for'

        # only 1 marker per airport
        if origin not in orig_list:
            html = """{0} {1}<BR>{2}""".format(origin, orig_name, orig_city)
            iframe = folium.element.IFrame(html=html, width=300, height=150)
            popup = folium.Popup(iframe, max_width=1000)
            g7.add_child(folium.Marker([orig_lat, orig_lon], popup=popup))
            orig_list.append(origin)

        # plot straight line for route from orig to dest
        g7.add_child(
            folium.PolyLine([[float(orig_lat), float(orig_lon)], [float(dest_lat), float(dest_lon)]], color='green',
                            weight=3))

        # plot marker in center of route with route stats(perturb lon coord if out and back routes both included)
        if set([orig_name, dest_name]) not in orig_dest_list:
            p = 0
        else:
            p = .2
        route_lat, route_lon = midpoint(orig_lat, orig_lon, dest_lat, dest_lon)
        html = """{0} {1}<BR>to<BR>{2} {3}<BR><BR><font color="green">{4}</font> Total Flights (delay data)<BR>""" \
               """<font color="green">{5}</font> Total Flights (occupancy data)<BR>""" \
               """<font color="green">{6}</font> Total Passengers (occupancy data)<BR>""" \
               """{7} mi<BR>{8:.1f} min. avg. Air Time<BR>{9:.1f} min. avg. Elapsed Gate to Gate<BR><BR>""" \
               """<font color="green">{10}</font> First/Business Flyers (from 10% sample of domestic tickets)<BR><BR>""" \
               """<font color="red">{11:.1f}%</font> Aircraft Delay > 20 min<BR>""" \
               """<font color="red">{12} min.</font> avg. Aircraft Delay time for non-weather and non-airport ops delays<BR><BR>""" \
               """<font color="red">{13:.1f}%</font> avg. Occupancy""".format(origin,
                                                                              orig_city, dest, dest_city,
                                                                              flight_count_route, departures_sum,
                                                                              passenger_sum,
                                                                              int(dist_mean_route), airtime_mean_route,
                                                                              elapsed_mean_route, bf_pct,
                                                                              delay_20pct_route * 100,
                                                                              int(delay_mean_route),
                                                                              occupancy_mean * 100)
        iframe = folium.element.IFrame(html=html, width=300, height=400)
        popup = folium.Popup(iframe, max_width=1000)
        g7.add_child(folium.Marker([route_lat, route_lon + p], popup=popup,
                                   icon=folium.Icon(color='green')))
        orig_dest_list.append(set([orig_name, dest_name]))

    # get dest airports with no returns in data (not an origin)
    for row in ot_occ_routes.iterrows():
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        if dest not in orig_list:
            html = """{0} {1}<BR>{2}""".format(dest, dest_name, dest_city)
            iframe = folium.element.IFrame(html=html, width=300, height=100)
            popup = folium.Popup(iframe, max_width=1000)
            g7.add_child(folium.Marker([dest_lat, dest_lon], popup=popup))
            dest_no_orig_list.append([dest, dest_name, dest_city])

    ############# Airline Delays & First/Business (in top 40 of each) #############
    orig_list = []
    dest_no_orig_list = []
    orig_dest_list = []
    # get origin airport data to plot
    for row in ot_cl_routes.iterrows():
        origin, orig_name, orig_city, orig_lat, orig_lon = row[1][
            ['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon']]
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        delay_mean_route, delay_20pct_route, flight_count_route = row[1][['AirlineDelay_mean',
                                                                          'AirlineDelay_20frac', 'Flight_Count']]
        dist_mean_route, airtime_mean_route, elapsed_mean_route = row[1][
            ['Distance_mean', 'AirTime_mean', 'ActualElapsedTime_mean']]
        bf_frac = row[1][['class_bf_frac']]
        try:
            bf_pct = '{0:.1f}%'.format(float(bf_frac) * 100)
        except:
            bf_pct = 'no data for'

        # only 1 marker per airport
        if origin not in orig_list:
            html = """{0} {1}<BR>{2}""".format(origin, orig_name, orig_city)
            iframe = folium.element.IFrame(html=html, width=300, height=150)
            popup = folium.Popup(iframe, max_width=1000)
            g8.add_child(folium.Marker([orig_lat, orig_lon], popup=popup))
            orig_list.append(origin)

        # plot straight line for route from orig to dest
        g8.add_child(
            folium.PolyLine([[float(orig_lat), float(orig_lon)], [float(dest_lat), float(dest_lon)]], color='green',
                            weight=3))

        # plot marker in center of route with route stats(perturb lon coord if out and back routes both included)
        if set([orig_name, dest_name]) not in orig_dest_list:
            p = 0
        else:
            p = .2
        route_lat, route_lon = midpoint(orig_lat, orig_lon, dest_lat, dest_lon)
        html = """{0} {1}<BR>to<BR>{2} {3}<BR><BR><font color="green">{4}</font> Total Flights<BR><BR>""" \
               """{5} mi<BR>{6:.1f} min. avg. Air Time<BR>{7:.1f} min. avg. Elapsed Gate to Gate<BR><BR>""" \
               """<font color="green">{8}</font> First/Business Flyers (from 10% sample of domestic tickets)<BR><BR>""" \
               """<font color="red">{9:.1f}%</font> Aircraft Delay > 20 min<BR>""" \
               """<font color="red">{10} min.</font> avg. Aircraft Delay time for non-weather and non-airport ops delays""".format(
            origin,
            orig_city, dest, dest_city, flight_count_route,
            int(dist_mean_route), airtime_mean_route, elapsed_mean_route, bf_pct,
            delay_20pct_route * 100, int(delay_mean_route))
        iframe = folium.element.IFrame(html=html, width=300, height=400)
        popup = folium.Popup(iframe, max_width=1000)
        g8.add_child(folium.Marker([route_lat, route_lon + p], popup=popup,
                                   icon=folium.Icon(color='green')))
        orig_dest_list.append(set([orig_name, dest_name]))

    # get dest airports with no returns in data (not an origin)
    for row in ot_cl_routes.iterrows():
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        if dest not in orig_list:
            html = """{0} {1}<BR>{2}""".format(dest, dest_name, dest_city)
            iframe = folium.element.IFrame(html=html, width=300, height=100)
            popup = folium.Popup(iframe, max_width=1000)
            g8.add_child(folium.Marker([dest_lat, dest_lon], popup=popup))
            dest_no_orig_list.append([dest, dest_name, dest_city])

    ############# Occupancy & First/Business (in top 40 of each) #############
    orig_list = []
    dest_no_orig_list = []
    orig_dest_list = []
    # get origin airport data to plot
    for row in occ_cl_routes.iterrows():
        origin, orig_name, orig_city, orig_lat, orig_lon = row[1][
            ['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon']]
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        passenger_sum, occupancy_mean, departures_sum = row[1][
            ['PASSENGERS_sum', 'occupancy_mean', 'DEPARTURES_PERFORMED_sum']]
        dist_mean_route = row[1]['DISTANCE_mean']
        bf_frac = row[1][['class_bf_frac']]
        try:
            bf_pct = '{0:.1f}%'.format(float(bf_frac) * 100)
        except:
            bf_pct = 'no data for'

        # only 1 marker per airport
        if origin not in orig_list:
            html = """{0} {1}<BR>{2}""".format(origin, orig_name, orig_city)
            iframe = folium.element.IFrame(html=html, width=300, height=150)
            popup = folium.Popup(iframe, max_width=1000)
            g9.add_child(folium.Marker([orig_lat, orig_lon], popup=popup))
            orig_list.append(origin)

        # plot straight line for route from orig to dest
        g9.add_child(
            folium.PolyLine([[float(orig_lat), float(orig_lon)], [float(dest_lat), float(dest_lon)]], color='green',
                            weight=3))

        # plot marker in center of route with route stats(perturb lon coord if out and back routes both included)
        if set([orig_name, dest_name]) not in orig_dest_list:
            p = 0
        else:
            p = .2
        route_lat, route_lon = midpoint(orig_lat, orig_lon, dest_lat, dest_lon)
        html = """{0} {1}<BR>to<BR>{2} {3}<BR><BR>""" \
               """<font color="green">{4}</font> Total Passengers<BR>""" \
               """<font color="green">{5}</font> Total Departures<BR>{6} mi<BR><Br>""" \
               """<font color="green">{7}</font> First/Business Flyers (from 10% sample of domestic tickets)<BR><BR>""" \
               """<font color="red">{8:.1f}%</font> avg. Occupancy<BR><BR>""".format(origin,
                                                                                     orig_city, dest, dest_city,
                                                                                     int(passenger_sum),
                                                                                     int(departures_sum),
                                                                                     int(dist_mean_route), bf_pct,
                                                                                     occupancy_mean * 100)
        iframe = folium.element.IFrame(html=html, width=300, height=250)
        popup = folium.Popup(iframe, max_width=1000)
        g9.add_child(folium.Marker([route_lat, route_lon + p], popup=popup,
                                   icon=folium.Icon(color='green')))
        orig_dest_list.append(set([orig_name, dest_name]))

    # get dest airports with no returns in data (not an origin)
    for row in occ_cl_routes.iterrows():
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        if dest not in orig_list:
            html = """{0} {1}<BR>{2}""".format(dest, dest_name, dest_city)
            iframe = folium.element.IFrame(html=html, width=300, height=100)
            popup = folium.Popup(iframe, max_width=1000)
            g9.add_child(folium.Marker([dest_lat, dest_lon], popup=popup))
            dest_no_orig_list.append([dest, dest_name, dest_city])

    ############# Airline Delays & Occupancy & First/Business (in top 40 of each) #############
    orig_list = []
    dest_no_orig_list = []
    orig_dest_list = []
    # get origin airport data to plot
    for row in ot_occ_cl_routes.iterrows():
        origin, orig_name, orig_city, orig_lat, orig_lon = row[1][
            ['orig_code', 'orig_name', 'orig_city', 'orig_lat', 'orig_lon']]
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        delay_mean_route, delay_20pct_route, flight_count_route = row[1][['AirlineDelay_mean',
                                                                          'AirlineDelay_20frac', 'Flight_Count']]
        airtime_mean_route, elapsed_mean_route = row[1][['AirTime_mean', 'ActualElapsedTime_mean']]
        passenger_sum, occupancy_mean, departures_sum = row[1][
            ['PASSENGERS_sum', 'occupancy_mean', 'DEPARTURES_PERFORMED_sum']]
        dist_mean_route = row[1][['DISTANCE_mean']]

        bf_frac = row[1][['class_bf_frac']]
        try:
            bf_pct = '{0:.1f}%'.format(float(bf_frac) * 100)
        except:
            bf_pct = 'no data for'

        # only 1 marker per airport
        if origin not in orig_list:
            html = """{0} {1}<BR>{2}""".format(origin, orig_name, orig_city)
            iframe = folium.element.IFrame(html=html, width=300, height=150)
            popup = folium.Popup(iframe, max_width=1000)
            g10.add_child(folium.Marker([orig_lat, orig_lon], popup=popup))
            orig_list.append(origin)

        # plot straight line for route from orig to dest
        g10.add_child(
            folium.PolyLine([[float(orig_lat), float(orig_lon)], [float(dest_lat), float(dest_lon)]], color='green',
                            weight=3))

        # plot marker in center of route with route stats(perturb lon coord if out and back routes both included)
        if set([orig_name, dest_name]) not in orig_dest_list:
            p = 0
        else:
            p = .2
        route_lat, route_lon = midpoint(orig_lat, orig_lon, dest_lat, dest_lon)
        html = """{0} {1}<BR>to<BR>{2} {3}<BR><BR><font color="green">{4}</font> Total Flights (delay data)<BR>""" \
               """<font color="green">{5}</font> Total Flights (occupancy data)<BR>""" \
               """<font color="green">{6}</font> Total Passengers (occupancy data)<BR>""" \
               """{7} mi<BR>{8:.1f} min. avg. Air Time<BR>{9:.1f} min. avg. Elapsed Gate to Gate<BR><BR>""" \
               """<font color="green">{10}</font> First/Business Flyers (from 10% sample of domestic tickets)<BR><BR>""" \
               """<font color="red">{11:.1f}%</font> Aircraft Delay > 20 min<BR>""" \
               """<font color="red">{12} min.</font> avg. Aircraft Delay time for non-weather and non-airport ops delays<BR><BR>""" \
               """<font color="red">{13:.1f}%</font> avg. Occupancy""".format(origin,
                                                                              orig_city, dest, dest_city,
                                                                              flight_count_route, departures_sum,
                                                                              passenger_sum,
                                                                              int(dist_mean_route), airtime_mean_route,
                                                                              elapsed_mean_route, bf_pct,
                                                                              delay_20pct_route * 100,
                                                                              int(delay_mean_route),
                                                                              occupancy_mean * 100)
        iframe = folium.element.IFrame(html=html, width=300, height=400)
        popup = folium.Popup(iframe, max_width=1000)
        g10.add_child(folium.Marker([route_lat, route_lon + p], popup=popup,
                                    icon=folium.Icon(color='green')))
        orig_dest_list.append(set([orig_name, dest_name]))

    # get dest airports with no returns in data (not an origin)
    for row in ot_occ_cl_routes.iterrows():
        dest, dest_name, dest_city, dest_lat, dest_lon = row[1][
            ['dest_code', 'dest_name', 'dest_city', 'dest_lat', 'dest_lon']]
        if dest not in orig_list:
            html = """{0} {1}<BR>{2}""".format(dest, dest_name, dest_city)
            iframe = folium.element.IFrame(html=html, width=300, height=100)
            popup = folium.Popup(iframe, max_width=1000)
            g10.add_child(folium.Marker([dest_lat, dest_lon], popup=popup))
            dest_no_orig_list.append([dest, dest_name, dest_city])

    m.add_child(g1)
    m.add_child(g2)
    m.add_child(g3)
    m.add_child(g4)
    m.add_child(g5)
    m.add_child(g6)
    m.add_child(g7)
    m.add_child(g8)
    m.add_child(g9)
    m.add_child(g10)
    m.add_child(folium.LayerControl())
    m.save('{0}/Route_Mapper{1}.html'.format(map_dir, mapname_suffix))