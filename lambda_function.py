def lambda_handler(event, context):
    # this project checks permit datasets against percent for art layers and emails staff if any fall within 250 feet of an art site.
    import requests
    import pandas as pd
    import xlsxwriter
    import glob

    url = r'https://phl.carto.com/api/v2/sql?q=SELECT%20permit.address%20as%20permit_address,%20permit.permitissuedate,%20permit.permitdescription,%20permit.approvedscopeofwork,%20permit.permitnumber,%20art.title,%20art.artist,%20art.medium,%20art.image,%20art.google_streetview_link,%20art.p4a_id%20FROM%20phl.percent_for_art_public%20art%20inner%20join%20permits%20permit%20on%20ST_DWithin(permit.the_geom_webmercator,%20art.the_geom_webmercator,%2076.2)%20where%20permit.permitissuedate%20=%20(current_date%20-%20interval%20%271%20day%27)'
    r = requests.get(url)
    r_dict = r.json()
    r_dict_values = r_dict['rows']
    
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
    excelFileName = rootPath + "PulledPermits_" + yesterday + ".xlsx" if isAws else "PulledPermits_" + yesterday + ".xlsx"
    
    # send the email
    if len(r_dict_values) > 0:
        print(r_dict_values) 
        df = pd.DataFrame(data=r_dict_values,columns=['permit_address','permitissuedate','permitdescription','approvedscopeofwork','permitnumber','title','artist','medium','image','google_streetview_link','p4a_id'])
        writer = pd.ExcelWriter(excelFileName, engine='xlsxwriter', date_format='mm dd yyyy', datetime_format='mm/dd/yyy')
        df.to_excel(writer, header=['Permit Address','Permit Issue Date','Permit Description','Scope of Work','Permit Number','Art Title','Artist','Medium','Image','Streetview','Art P4A_ID'], sheet_name='Sheet1') 
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
    
        worksheet.set_column('B:F', 17)
        worksheet.set_column('G:L', 9.5)
    
        writer.save()
    
        # set up email variables 
        sender = os.environ.get('DPDAppsProd_Email')
        senderPassword = os.environ.get('DPDAppsProd_Password')
        receivers = [os.environ.get('Dan_Email'), os.environ.get('Kacie_Email'), os.environ.get('Sara_Email')]
        subject = 'Permit Pulled Near Art Location'
        message = 'A permit was pulled close to an art location. Explore art sites here: http://phl.maps.arcgis.com/apps/View/index.html?appid=096b3c2a955e49f9921d948f3403a1d0.'
    
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
        subject = 'No Permits Pulled Near Art Locations'
        message = 'No permits were pulled near art locations yesterday.'
    
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


