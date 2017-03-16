####################
Route Mapper Project
####################


#######
Purpose
#######
These scripts combine several commercial air and Amtrak datasets to map flight routes that are grouped by various pain point metrics, such as delays, occupancy, stopovers, and coverage.

The two scripts used to aggregate the data and map the routes are listed below along with the data sources.


##################
Script:
data_aggregator.py
##################

Description:
This script loads the airline datasets, cuts them down to be anchored in a specified state and short-haul in nature, and finally aggregates them on a route (origin-destination) level.

Arguments:
-q, --quarter  Quarter over which to aggregate data, default None aggregates over all quarters
--air-delay  Create route aircraft delay dataset (aircraft_delay_routes.csv)
--air-occ  Create route aircraft occupancy dataset (aircraft_occupancy_routes.csv)
--air-class  Create flyer fare class dataset (flyer_class_routes.csv)
--air-stopover  Create flyer stopover dataset
--anchor-state  Orig or Dest for each route must be in this anchor state (default: CA)
--max-dist  Maximum distance in miles of routes (default: 800mi for short haul flights)

Input directories:
data/airports (data included)
data/aircraft_delays
data/aircraft_occupancy
data/air_coupons (stopover + class data)
data/amtrak (California data included)

Output directory:
data/aggregated


##############
Script:
map_creator.py
##############

Description:
This script loads the aggregated route airline and Amtrak datasets, performs a loose cut on infrequently flown routes to ensure consistency, combines them, and finally creates an interactive map to visualize the routes and their metrics.

Each route dataset is initially trimmed by a soft cut in minimum monthly flights or passengers in order to ensure a consistent pool of travelers.

Arguments:
-q --quarter  Quarter over which to create the map, default None aggregates over all quarters
--monthly-flights  Minimum monthly flights over a route to ensure consistent pool of travelers (default: 50)
--monthly-passengers  Minimum monthly passengers over a route to ensure consistent pool of travelers (default:1000)

Input directory:
data/aggregated (default output data from data_aggregator.py included)

Output directory:
maps (default data maps included)


########################
Required python packages
########################
numpy
pandas
argparse
folium


############
Data sources
############
* Aircraft Delays
https://www.transtats.bts.gov/DL_SelectFields.asp?Table_ID=236&DB_Short_Name=On-Time
- Airline On-Time Performance database from the Bureau of Transportation Statistics
"Monthly data reported by US certified air carriers that account for at least one percent of domestic scheduled passenger revenues--includes scheduled and actual arrival and departure times for flights."
-- On-Time Performance table
"This table contains on-time arrival data for non-stop domestic flights by major air carriers, and provides such additional items as departure and arrival delays, origin and destination airports, flight numbers, scheduled and actual departure and arrival times, cancelled or diverted flights, taxi-out and taxi-in times, air time, and non-stop distance."
-- Rows are per flight (take off datetime, origin, destination)
-- Delays are calculated using only delays cause by an airline-related reason (maintenance crew problems, baggage loading, fueling, previous flight with same aircraft arrived late) .

* Aircraft Occupancy
https://www.transtats.bts.gov/DL_SelectFields.asp?Table_ID=259&DB_Short_Name=Air%20Carriers
- Air Carrier Statistics (Form 41 Traffic)- U.S. Carriers database from the Bureau of Transportation Statistics
"Monthly data reported by certificated U.S. air carriers on passengers, freight and mail transported. Also includes aircraft type, service class, available capacity and seats, and aircraft hours ramp-to-ramp and airborne."
-- T-100 Domestic Segment (U.S.) Carriers table
"This table contains domestic non-stop segment data reported by U.S. air carriers, including carrier, origin, destination, aircraft type and service class for transported passengers, freight and mail, available capacity, scheduled departures, departures performed, aircraft hours, and load factor when both origin and destination airports are located within the boundaries of the United States and its territories."
-- Rows are per month, origin-destination pair, carrier, aircraft type
-- Occupancy is calculated by (Total Passengers)/(Total Seats) for each row and then the average is take for each origin-destination route pair.
-- Note: Occupancy could also be calculated by (Total Passengers)/(Total Seats) over each origin-destination route pair (not taking the average over all rows).  This yields a similar result to the above, but this method tends to wash out smaller aircraft that still offer lower occupancy rates on a given route.

* Air Fare Class and Stopovers
https://www.transtats.bts.gov/DL_SelectFields.asp?Table_ID=289&DB_Short_Name=Origin%20and%20Destination%20Survey
- Airline Origin and Destination Survey (DB1B) database from the Bureau of Transportation Statistics
"Origin and Destination Survey (DB1B) is a 10% sample of airline tickets from reporting carriers. Data includes origin, destination and other itinerary details of passengers transported."
-- DB1BCoupon table
"This table provides coupon-specific information for each domestic itinerary of the Origin and Destination Survey, such as the operating carrier, origin and destination airports, number of passengers, fare class, coupon type, trip break indicator, and distance."
-- Rows are per month, itinerary id (includes extended stopovers), market id (includes only short aircraft changes), sequence number in itinerary, origin, destination, passengers, fare class
-- Fraction of fare class travelers is weighted by the total passengers on that route.
-- Stopovers are calculated by counting the number of sequence numbers within a market id for a given route.

* Airport Locations
http://openflights.org/data.html#airport
- airports.dat

* Amtrak Station Locations
http://www.ensingers.com/Bill222E/gpsamtrak.html

* Amtrak Station Ridership Statistics
https://www.narprail.org/our-issues/reports-and-white-papers/ridership-statistics/
- Copied from California PDF

* Amtrak Station Delays
https://juckins.net/amtrak_status/archive/html/resources.php
- Publicly-available twice-daily scraper from Amtrak.com
- Data taken from "Amtrak Status Maps Archive Database"

* Combined California-based Amtrak+Airport data already created and used by these scripts at:
data/amtrak/ca_amtrak_airport_ridership_delays.csv