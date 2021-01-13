def lambda_handler(event, context):
    # this project checks permit datasets against percent for art layers and emails staff if any fall within 250 feet of an art site.
    import pandas as pd
    import requests
    import geopandas as gpd
    import json
    import matplotlib.pyplot as plt
    from shapely.geometry import shape
    from shapely.geometry.collection import GeometryCollection
    import xlsxwriter
    import glob

    # import os for environmnent variables
    import os

    # import stmplib for simple email
    import smtplib

    # import mime stuff for better email layout
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase

    # import things to handle email attachments
    from email import encoders
    import os.path

    from datetime import date, timedelta
    
    yesterday = (date.today() - timedelta(1)).strftime('%m-%d-%Y')
    
    isAws = os.environ.get('isAwsEnvironment', False)
    rootPath = "/tmp/"
    excelFileName = rootPath + "PermitApplications_" + yesterday + ".xlsx" if isAws else "PermitApplications_" + yesterday + ".xlsx"
    
    token_url = "https://www.arcgis.com/sharing/rest/oauth2/token"

    P4A_ClientID = os.environ.get('PercentForArt_ClientID')
    P4A_ClientSecret = os.environ.get('PercentForArt_ClientSecret')

    payload = "client_id="+ P4A_ClientID + "&client_secret=" + P4A_ClientSecret + "&grant_type=client_credentials"
    headers = {
        'content-type': "application/x-www-form-urlencoded",
        'accept': "application/json",
        'cache-control': "no-cache",
        }

    response = requests.request("POST", token_url, data=payload, headers=headers)

    token = response.json()['access_token']
    
    # get permits as a geodataframe
    permits_url = 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/PermitAppStatusEclipse/FeatureServer/0/query?where=APPLICATIONDATE+%3E+%28CURRENT_TIMESTAMP+-+INTERVAL+%272%27+DAY%29+AND%20geocode_x%20is%20not%20null%20AND+APPLICATIONDESCRIPTION+NOT+IN+%28%27ELECTRICAL+PERMIT%27%2C%27FIRE+SUPPRESSION+PERMIT%27%2C%27MECHANICAL+PERMIT%27%2C%27MECHANICAL+%2F+FUEL+GAS+PERMIT%27%2C%27PLUMBING+PERMIT%27%29&objectIds=&time=&geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&resultType=none&distance=0.0&units=esriSRUnit_Meter&returnGeodetic=false&outFields=*&returnGeometry=true&featureEncoding=esriDefault&multipatchOption=xyFootprint&maxAllowableOffset=&geometryPrecision=&outSR=&datumTransformation=&applyVCSProjection=false&returnIdsOnly=false&returnUniqueIdsOnly=false&returnCountOnly=false&returnExtentOnly=false&returnQueryGeometry=false&returnDistinctValues=false&cacheHint=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&having=&resultOffset=&resultRecordCount=&returnZ=false&returnM=false&returnExceededLimitFeatures=true&quantizationParameters=&sqlFormat=standard&f=pgeojson&token=' + token
    permits_geodf = gpd.read_file(permits_url)
    
    # get art as a geodataframe
    art_url = 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Percent_for_Art_Public/FeatureServer/0/query?where=1%3D1&objectIds=&time=&geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&resultType=none&distance=0.0&units=esriSRUnit_Meter&returnGeodetic=false&outFields=*&returnGeometry=true&returnCentroid=false&featureEncoding=esriDefault&multipatchOption=xyFootprint&maxAllowableOffset=&geometryPrecision=&outSR=&datumTransformation=&applyVCSProjection=false&returnIdsOnly=false&returnUniqueIdsOnly=false&returnCountOnly=false&returnExtentOnly=false&returnQueryGeometry=false&returnDistinctValues=false&cacheHint=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&having=&resultOffset=&resultRecordCount=&returnZ=false&returnM=false&returnExceededLimitFeatures=true&quantizationParameters=&sqlFormat=standard&f=pgeojson&token=' + token
    art_geodf = gpd.read_file(art_url)
    
    # update the crs to ensure a match
    permits_pa = permits_geodf.to_crs(epsg=2272) 
    art_pa = art_geodf.to_crs(epsg=2272)
    
    # change permit geometry to a 250' buffer of the license point feature
    permits_pa['geometry'] = permits_pa.geometry.buffer(250)
    
    # make a spatial join
    joined_art = gpd.sjoin(permits_pa, art_pa, how="inner", op="intersects")
    
    # correct the date format
    joined_art['APPLICATIONDATE']=(pd.to_datetime(joined_art['APPLICATIONDATE'],unit='ms'))
    
    # send the email
    if len(joined_art) > 0:
        print(joined_art) 
        df = pd.DataFrame(data=joined_art,columns=['ADDRESS_left','APPLICATIONNUMBER','APPLICATIONDATE','APPLICATIONDESCRIPTION','STATUS_left','COMMENTS','SYSTEM_OF_RECORD','TITLE', 'ARTIST','MEDIUM','IMAGE','GOOGLE_STREETVIEW_LINK','P4A_ID'])
        pd.to_datetime(df['APPLICATIONDATE'], unit='ms')        
        writer = pd.ExcelWriter(excelFileName, engine='xlsxwriter', date_format='mm dd yyyy', datetime_format='mm/dd/yyyy')
        df.to_excel(writer, header=['Permit Address','Permit Number','Permit Application Date','Permit Description','Permit Status','Permit Comments','Permit System of Record','Title', 'Artist','Medium','Image','Streetview','Art P4A_ID'], sheet_name='Sheet1') 
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']

        worksheet.set_column('B:H', 22)
        worksheet.set_column('I:N', 15)

        writer.save()
    
        # set up email variables 
        sender = os.environ.get('DPDAppsProd_Email')
        senderPassword = os.environ.get('DPDAppsProd_Password')
        receivers = [os.environ.get('Dan_Email'), os.environ.get('Kacie_Email'), os.environ.get('Sara_Email')]
        subject = 'Permit Activity Near an Art Site'
        message = 'Permit activity occurred near an art site yesterday. Explore art sites here: http://phl.maps.arcgis.com/apps/View/index.html?appid=096b3c2a955e49f9921d948f3403a1d0.'
    
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = ", ".join(receivers)
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
        sender = os.environ.get('DPDAppsProd_Email')
        senderPassword = os.environ.get('DPDAppsProd_Password')
        receivers = [os.environ.get('Dan_Email'), os.environ.get('Kacie_Email'), os.environ.get('Sara_Email')]
        subject = 'No Permit Activity Near Art Locations'
        message = 'No permit applications were submitted near art locations yesterday.'
    
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = ",".join(receivers)
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

    files = glob.glob(f'{rootPath}/*')
    for f in files:
        os.remove(f)


