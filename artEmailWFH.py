# create a parcels geojson-based geodataframe file with geometry to compare to AGO geojson-based geodataframe file with geometry
import geopandas as gpd
from geopandas import read_file

pwdParcels_gdf = read_file('https://phl.carto.com:443/api/v2/sql?q=select%20*%20from%20phl.pwd_parcels&format=GEOJSON&method=export')

# see the new pwdParcels geodataframe column names. this shows that there is now a 'geometry'
pwdParcels_gdf.head()

# get the fake prop zoning layer (which will have to be swapped out for the art site layer) and its geometries
import requests

url = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/ProposedZoning_AlteredSouth01/FeatureServer/0/query?where=1%3D1&objectIds=&time=&geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&resultType=none&distance=0.0&units=esriSRUnit_Meter&returnGeodetic=false&outFields=*&returnHiddenFields=false&returnGeometry=true&returnCentroid=false&featureEncoding=esriDefault&multipatchOption=xyFootprint&maxAllowableOffset=&geometryPrecision=&outSR=&datumTransformation=&applyVCSProjection=false&returnIdsOnly=false&returnUniqueIdsOnly=false&returnCountOnly=false&returnExtentOnly=false&returnQueryGeometry=false&returnDistinctValues=false&cacheHint=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&having=&resultOffset=&resultRecordCount=&returnZ=false&returnM=false&returnExceededLimitFeatures=true&quantizationParameters=&sqlFormat=none&f=GEOJSON&token=3br531jBTSe-yIKL229VF0L39ei4MNm4lHibsJc5UGpR2MsVAw_NbbP0it7DX46pTAIJO00Caemf8zuobrOHHAqjxZCjrecg4bok8_sO6Qx5ZtXnfuAX4zZ7nCfGDrWLe_rjRlQE1YeyBL3yw7FUKQFGQ3Rhb6xIalEhSEddsfvZ7_6fv7VZKyGKbUi6d6CcMwLSUL36Jw9LHZh-pK88EC-2m-pt6gRIHVDXN1R45EbMxo1qSvnsfWbikuhcHgmx"

payload = {}
headers= {}

artSites = requests.request("GET", url, headers=headers, data = payload)

# turn artSites to json. i think this is a necessary intermediate step, but i could be wrong. 
artSites_json = artSites.json()
artSites_json

# this is a great step. now we actually have polygons with a recognized geometry
artSites_gdf = gpd.GeoDataFrame.from_features(artSites_json["features"])
print(artSites_gdf.head())
gdf.geometry
