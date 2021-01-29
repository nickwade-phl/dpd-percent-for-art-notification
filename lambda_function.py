def lambda_handler(event, context):
    # this project checks permit datasets against percent for art layers and emails staff if any fall within 250 feet of an art site.
    import pandas as pd
    import requests
    import xlsxwriter
    import glob
    import json
    # import os for environmnent variables
    import os

    # import boto3 ses for simple email
    import boto3
    client = boto3.client('ses', region_name="us-east-1")
    # The character encoding for the email.
    CHARSET = "utf-8"

    # import mime stuff for better email layout
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.application import MIMEApplication

    # import things to handle email attachments
    from email import encoders
    import os.path

    from datetime import date, timedelta

    yesterday = (date.today() - timedelta(1)).strftime('%m-%d-%Y')

    isAws = os.environ.get('isAwsEnvironment', False)
    rootPath = "/tmp/"
    excelFileName = rootPath + "PermitApplications_" + yesterday + \
        ".xlsx" if isAws else "PermitApplications_" + yesterday + ".xlsx"

    token_url = "https://www.arcgis.com/sharing/rest/oauth2/token"

    P4A_ClientID = os.environ.get('PercentForArt_ClientID')
    P4A_ClientSecret = os.environ.get('PercentForArt_ClientSecret')

    payload = "client_id=" + P4A_ClientID + "&client_secret=" + \
        P4A_ClientSecret + "&grant_type=client_credentials"
    headers = {
        'content-type': "application/x-www-form-urlencoded",
        'accept': "application/json",
        'cache-control': "no-cache",
    }

    response = requests.request(
        "POST", token_url, data=payload, headers=headers)

    token = response.json()['access_token']

    # get permits as a geodataframe
    permits_url = (
        "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/PermitAppStatusEclipse/FeatureServer/0/query?"
        # UNCOMMENT FOR TESTING
        # "where=1=0&resultRecordCount=10"
        "where=APPLICATIONDATE > (CURRENT_TIMESTAMP - INTERVAL '2' DAY)"
            " AND geocode_x is not null"
            " AND APPLICATIONDESCRIPTION NOT IN ('ELECTRICAL PERMIT','FIRE SUPPRESSION PERMIT','MECHANICAL PERMIT','MECHANICAL / FUEL GAS PERMIT','PLUMBING PERMIT')"
        f"&token={token}"
        "&f=json"
        "&outSR=2272"
        "&outFields=ADDRESS,APPLICATIONNUMBER,APPLICATIONDATE,APPLICATIONDESCRIPTION,STATUS,COMMENTS,SYSTEM_OF_RECORD"
    )
    permit_response = requests.request("GET", permits_url)
    permit_result = permit_response.json()
    permit_geometries = [{"x": p["geometry"]["x"], "y": p["geometry"]["y"]}
                            for p in (x for x in permit_result["features"] if "geometry" in x)]
    permit_geometries_request_body = {
        "geometryType": "esriGeometryPoint",
        "geometries": permit_geometries
    }
    permit_buffer_request_payload = {
        'f': 'json',
        'geometries': json.dumps(permit_geometries_request_body),
        'distances': '250',
        'inSR': 2272,
        'outSR': 2272,
        'bufferSR': 2272,
        "unionResults": 'false',
        "geodesic": "false"

    }
    permit_buffer_url = "https://gis-utils.databridge.phila.gov/arcgis/rest/services/Utilities/Geometry/GeometryServer/buffer"

    permit_buffer_response = requests.request(
        "POST", permit_buffer_url, data=permit_buffer_request_payload)
    permit_buffer_result = permit_buffer_response.json()
    # get art as a geodataframe
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
    permit_buffer_rings = permit_buffer_result["geometries"] if  permit_buffer_result.get("geometries") else ""
    permit_buffer_geometry_request_body = {
        "geometryType": "esriGeometryPolygon",
        "geometries": permit_buffer_rings
    }
    art_geometry_json = json.dumps(art_geometries_request_body)
    permit_buffer_geometry_json = json.dumps(
        permit_buffer_geometry_request_body)

    relation_data = {
        'f': 'json',
        "sr": 2272,
        "geometries1": art_geometry_json,
        "geometries2": permit_buffer_geometry_json,
        "relation": "esriGeometryRelationIntersection"
    }

    relation_url = "https://gis-utils.databridge.phila.gov/arcgis/rest/services/Utilities/Geometry/GeometryServer/relation"
    relation_response = requests.request(
        "POST", relation_url, data=relation_data)
    relation_result = relation_response.json()

    art_features = art_result["features"]
    permit_features = permit_result["features"]

    joined_art = []
    relations = relation_result["relations"] if relation_result.get("relations") else ""
    if relations != "":
        for result in relations:
            art_feature = art_features[result["geometry1Index"]]["attributes"]
            permit_feature = permit_features[result["geometry2Index"]
                                                ]["attributes"]
            joined_feature = {**art_feature, **permit_feature}
            joined_art.append(joined_feature)

    # set up email variables
    sender =os.environ.get('DPDAppsProd_Email')
    receivers = [
        i for i in [
            os.environ.get('Dan_Email'),
            os.environ.get('Kacie_Email'),
            os.environ.get('Sara_Email')
        ] 
        if i
    ]
    destinations = ", ".join(receivers)

    # send the email
    if len(joined_art) > 0:
        print(joined_art)
        df = pd.DataFrame(data=joined_art, columns=['ADDRESS_left', 'APPLICATIONNUMBER', 'APPLICATIONDATE', 'APPLICATIONDESCRIPTION',
                                                    'STATUS_left', 'COMMENTS', 'SYSTEM_OF_RECORD', 'TITLE', 'ARTIST', 'MEDIUM', 'IMAGE', 'GOOGLE_STREETVIEW_LINK', 'P4A_ID'])
        pd.to_datetime(df['APPLICATIONDATE'], unit='ms')
        writer = pd.ExcelWriter(excelFileName, engine='xlsxwriter',
                                date_format='mm dd yyyy', datetime_format='mm/dd/yyyy')
        df.to_excel(writer, header=['Permit Address', 'Permit Number', 'Permit Application Date', 'Permit Description', 'Permit Status',
                                    'Permit Comments', 'Permit System of Record', 'Title', 'Artist', 'Medium', 'Image', 'Streetview', 'Art P4A_ID'], sheet_name='Sheet1')
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']

        worksheet.set_column('B:H', 22)
        worksheet.set_column('I:N', 15)

        writer.save()

        # set up email variables
        subject = 'Permit Activity Near an Art Site'
        message = 'Permit activity occurred near an art site yesterday. Explore art sites here: http://phl.maps.arcgis.com/apps/View/index.html?appid=096b3c2a955e49f9921d948f3403a1d0.'

        msg = MIMEMultipart('mixed')
        msg['From'] = sender
        msg['To'] = destinations
        msg['Subject'] = subject

        msg_body = MIMEMultipart('alternative')
        textpart = MIMEText(message.encode(CHARSET), 'plain', CHARSET)
        msg_body.attach(textpart)

        # attach the message to the MIMEMultipart object
        att = MIMEApplication(open(excelFileName, 'rb').read())

        att.add_header('Content-Disposition', 'attachment',
                        filename=os.path.basename(excelFileName))

        # attach the attachment & message body to the MIMEMultipart object
        msg.attach(att)
        msg.attach(msg_body)

        # send the email
        response = client.send_raw_email(
            Source=sender,
            Destinations=receivers,
            RawMessage={
                'Data': msg.as_string(),
            },
        )

    else:
        print("No matches")

        subject = 'No Permit Activity Near Art Locations'
        message = 'No permit applications were submitted near art locations yesterday.'

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = destinations
        msg['Subject'] = subject

        # attach the message to the MIMEMultipart object
        msg.attach(MIMEText(message, 'plain'))

        # send the email
        client.send_raw_email(
            RawMessage={
                'Data': msg.as_string(),
            },          
            Source=msg['From'],
            Destinations=receivers,
        )

    # remove excess files created
    files = glob.glob(f'{rootPath}/*')
    for f in files:
        os.remove(f)
