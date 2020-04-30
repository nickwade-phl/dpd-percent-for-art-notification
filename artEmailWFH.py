# create a parcels geojson-based geodataframe file with geometry to compare to AGO geojson-based geodataframe file with geometry
import geopandas as gpd
from geopandas import read_file

pwdParcels_gdf = read_file('https://phl.carto.com:443/api/v2/sql?q=select%20*%20from%20phl.pwd_parcels&format=GEOJSON&method=export')

# create an art sites geojson-based geodataframe file with geometry to compare to parcels geojson-based geodataframe file with geometry. define the crs as 4326 so it can be analyzed against the carto parcels and permits layers
artSites_gdf = read_file('https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Test_Art_Sites/FeatureServer/0/query?where=1%3D1&objectIds=&time=&geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&resultType=none&distance=0.0&units=esriSRUnit_Meter&returnGeodetic=false&outFields=*&returnHiddenFields=false&returnGeometry=true&returnCentroid=false&featureEncoding=esriDefault&multipatchOption=xyFootprint&maxAllowableOffset=&geometryPrecision=&outSR=&datumTransformation=&applyVCSProjection=false&returnIdsOnly=false&returnUniqueIdsOnly=false&returnCountOnly=false&returnExtentOnly=false&returnQueryGeometry=false&returnDistinctValues=false&cacheHint=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&having=&resultOffset=&resultRecordCount=&returnZ=false&returnM=false&returnExceededLimitFeatures=true&quantizationParameters=&sqlFormat=none&f=GEOJSON&token=Kd3CaU2QNHFkWVApSPuYu7TcgM5r-_0hObkgkmhlQ62is-fBfd7v8K0C20lmCY6B2rPp0buefxaJpas3ppsOIHkXLtPpCYia-FQlCI0KGtCEBdlet5zNCQqg6XB_OMEG7g8SjGcdQdwQv6coq91w-nZYSaJsRbqi-Zi4W6IK6Wf2zhSjYU11AopltMr61xwMsKI7V37Re2Onw3nJv_QDS8RNdkOwYcjui4MTvMHa8no.&format=GEOJSON&method=export', crs='EPSG:4326')

# join intersecting pwd parcels to test art sites (needs to be swapped out for real art sites later)
artSiteParcels = gpd.sjoin(pwdParcels_gdf, artSites_gdf, how='inner', op='intersects')
artSiteParcels

# rename the index columns of the artSiteParcels so that artSiteParcels can be joined again - this time, to the permits
artSiteParcels = artSiteParcels.rename(columns={'index_left': 'parcels_index','index_right': 'art_index'})

# read the l and i permits layer to see which permits were pulled and export to geojson. make sure to change the number of days to '1 day' when the script is ready 
liPermits_gdf = gpd.read_file("https://phl.carto.com:443/api/v2/sql?q=select%20*%20from%20phl.li_permits%20WHERE%20permitissuedate%20=%20(current_date%20-%20interval%20'82%20days')&format=GEOJSON&method=export")
liPermits_gdf

# find artSiteParcels that are intersected by liPermits_gdf
permits_at_artSiteParcels = gpd.sjoin(artSiteParcels, liPermits_gdf, how='inner', op='intersects')
permits_at_artSiteParcels

# import pandas to create dataframes
import pandas as pd

# import time to add the date of the export to the excel document
import time 

# import os for environmnent variables
import os

# openpyxl for writing to excel
import openpyxl
from openpyxl import Workbook

# import stmplib for simple email
import smtplib

# import mime stuff for better email layout
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase

# import things to handle email attachments
from email import encoders
import os.path

todaysDate = time.strftime('%d-%m-%Y')

excelFileName = "PulledPermits_" + todaysDate + ".xlsx"

# send the email
if len(permits_at_artSiteParcels) > 0:
    print(permits_at_artSiteParcels) 
    df = pd.DataFrame(data=permits_at_artSiteParcels,columns=['Address','Art_Name','address_right','permitdescription','permitnumber','address_left','owner1','owner2'])
    df.to_excel(excelFileName, header=['Art Site Address','Art Site Name','Permit Address','Permit Description','Permit Number','Triggering Parcel Address','Triggering Parcel Owner 1','Triggering Parcel Owner 2']) 
    
    # set up email variables 
    sender = os.environ.get('DanWork_Email')
    senderPassword = os.environ.get('DanWork_Password')
    receivers = os.environ.get('DanPersonal_Email')
    subject = 'Permit Pulled at Art Location'
    message = 'A permit was pulled at an art location. See the attached Excel file for details.'

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receivers
    msg['Subject'] = subject

    # attach the message to the MIMEMultipart object
    msg.attach(MIMEText(message, 'plain'))

    # set up the attachment
    filename = excelFileName
    attachment = open(filename, 'rb')
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename= %s' % filename)

    # attach the attachment to the MIMEMultipart object
    msg.attach(part)

    smtpObj = smtplib.SMTP('smtp.office365.com', 587)
    smtpObj.ehlo()
    smtpObj.starttls()
    smtpObj.ehlo()
    smtpObj.login(sender, senderPassword)
    text = msg.as_string()
    smtpObj.sendmail(sender, receivers, text)
    smtpObj.quit()

else:
    print("No matches")
    
    # set up email variables
    sender = os.environ.get('DanWork_Email')
    senderPassword = os.environ.get('DanWork_Password')
    receivers = os.environ.get('DanPersonal_Email')
    subject = 'No Permits Pulled at Art Locations'
    message = 'No permits were pulled at art locations yesterday.'

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receivers
    msg['Subject'] = subject

    # attach the message to the MIMEMultipart object
    msg.attach(MIMEText(message, 'plain'))

    smtpObj = smtplib.SMTP('smtp.office365.com', 587)
    smtpObj.ehlo()
    smtpObj.starttls()
    smtpObj.ehlo()
    smtpObj.login(sender, senderPassword)
    text = msg.as_string()
    smtpObj.sendmail(sender, receivers, text)
    smtpObj.quit()
