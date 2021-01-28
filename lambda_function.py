def lambda_handler(event, context):
    # this project checks permit datasets against percent for art layers and emails staff if any fall within 250 feet of an art site.
    import pandas as pd
    import requests
    import xlsxwriter
    import glob
    import json
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
    #permits_url = 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/PermitAppStatusEclipse/FeatureServer/0/query?where=APPLICATIONDATE+%3E+%28CURRENT_TIMESTAMP+-+INTERVAL+%272%27+DAY%29+AND%20geocode_x%20is%20not%20null%20AND+APPLICATIONDESCRIPTION+NOT+IN+%28%27ELECTRICAL+PERMIT%27%2C%27FIRE+SUPPRESSION+PERMIT%27%2C%27MECHANICAL+PERMIT%27%2C%27MECHANICAL+%2F+FUEL+GAS+PERMIT%27%2C%27PLUMBING+PERMIT%27%29&objectIds=&time=&geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&resultType=none&distance=0.0&units=esriSRUnit_Meter&returnGeodetic=false&outFields=*&returnGeometry=true&featureEncoding=esriDefault&multipatchOption=xyFootprint&maxAllowableOffset=&geometryPrecision=&outSR=&datumTransformation=&applyVCSProjection=false&returnIdsOnly=false&returnUniqueIdsOnly=false&returnCountOnly=false&returnExtentOnly=false&returnQueryGeometry=false&returnDistinctValues=false&cacheHint=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&having=&resultOffset=&resultRecordCount=&returnZ=false&returnM=false&returnExceededLimitFeatures=true&quantizationParameters=&sqlFormat=standard&f=pgeojson&token=' + token
    permits_url = (
                "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/PermitAppStatusEclipse/FeatureServer/0/query?"
                    "where=1=1&resultRecordCount=10"
                    #"where=APPLICATIONDATE > (CURRENT_TIMESTAMP - INTERVAL '2' DAY)"
                #    " AND geocode_x is not null"
                #    " AND APPLICATIONDESCRIPTION NOT IN ('ELECTRICAL PERMIT','FIRE SUPPRESSION PERMIT','MECHANICAL PERMIT','MECHANICAL / FUEL GAS PERMIT','PLUMBING PERMIT')"
                    f"&token={token}"
                    "&f=json"
                    "&outSR=2272"
                    "&outFields=ADDRESS,APPLICATIONNUMBER,APPLICATIONDATE,APPLICATIONDESCRIPTION,STATUS,COMMENTS,SYSTEM_OF_RECORD"
                )
    permit_response = requests.request("GET", permits_url)
    permit_result = permit_response.json()
    permit_geometries = [{"x": p["geometry"]["x"], "y": p["geometry"]["y"]} for p in (x for x in permit_result["features"] if "geometry" in x)]
    permit_geometries_request_body = {
        "geometryType": "esriGeometryPoint",
        "geometries": permit_geometries
    }
    permit_buffer_request_payload = {
        'f': 'json',
        'geometries': json.dumps(permit_geometries_request_body),
        'distances': '250',
        'inSR' : 2272,
        'outSR' : 2272,
        'bufferSR': 2272,
        "unionResults": 'false',
        "geodesic": "false"

    }
    permit_buffer_url = "https://gis-utils.databridge.phila.gov/arcgis/rest/services/Utilities/Geometry/GeometryServer/buffer"

    permit_buffer_response = requests.request("POST", permit_buffer_url, data=permit_buffer_request_payload)
    permit_buffer_result = permit_buffer_response.json()
    # get art as a geodataframe
    #art_url = 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Percent_for_Art_Public/FeatureServer/0/query?where=1%3D1&objectIds=&time=&geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&resultType=none&distance=0.0&units=esriSRUnit_Meter&returnGeodetic=false&outFields=*&returnGeometry=true&returnCentroid=false&featureEncoding=esriDefault&multipatchOption=xyFootprint&maxAllowableOffset=&geometryPrecision=&outSR=&datumTransformation=&applyVCSProjection=false&returnIdsOnly=false&returnUniqueIdsOnly=false&returnCountOnly=false&returnExtentOnly=false&returnQueryGeometry=false&returnDistinctValues=false&cacheHint=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&having=&resultOffset=&resultRecordCount=&returnZ=false&returnM=false&returnExceededLimitFeatures=true&quantizationParameters=&sqlFormat=standard&f=pgeojson&token=' + token
    art_url = (
                "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Percent_for_Art_Public/FeatureServer/0/query?"
                "&where=1=1"
                f"&token={token}"
                "&f=json"
                "&outSR=2272"
                "&outFields=TITLE,ARTIST,MEDIUM,IMAGE,GOOGLE_STREETVIEW_LINK,P4A_ID"
            )
    art_response = requests.request("GET", art_url)
    art_result = art_response.json()
    art_geometries = [a["geometry"]for a in art_result["features"]]
    art_geometries_request_body = {
        "geometryType": "esriGeometryPolygon",
        "geometries": art_geometries
    }
    permit_buffer_rings = permit_buffer_result["geometries"]
    permit_buffer_geometry_request_body = {
        "geometryType": "esriGeometryPolygon",
        "geometries": permit_buffer_rings
    }
    art_geometry_json = json.dumps(art_geometries_request_body)
    permit_buffer_geometry_json = json.dumps(permit_buffer_geometry_request_body)

    relation_data = {
        'f': 'json',
        "sr": 2272,
        "geometries1": art_geometry_json,
        "geometries2": permit_buffer_geometry_json,
        "relation": "esriGeometryRelationIntersection"
    }

    relation_url = "https://gis-utils.databridge.phila.gov/arcgis/rest/services/Utilities/Geometry/GeometryServer/relation"
    relation_response = requests.request("POST", relation_url, data=relation_data)
    relation_result = relation_response.json()

    art_features = art_result["features"]
    permit_features = permit_result["features"]

    joined_art = []

    for result in relation_result["relations"]:
        art_feature = art_features[result["geometry1Index"]]["attributes"]
        permit_feature = permit_features[result["geometry2Index"]]["attributes"]
        joined_feature = {**art_feature, **permit_feature}
        joined_art.append(joined_feature)

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
        receivers = [r for r in [os.environ.get('Dan_Email'), os.environ.get('Kacie_Email'), os.environ.get('Sara_Email')] if not r is None]
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

        smtpObj = smtplib.SMTP('smtp.office365.com', 587) if isAws else smtplib.SMTP('relay.city.phila.local', 25) 
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

        smtpObj = smtplib.SMTP('smtp.office365.com', 587) if isAws else smtplib.SMTP('relay.city.phila.local', 25) 
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


