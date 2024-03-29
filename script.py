import json
import os
import wget
import settings
from bs4 import BeautifulSoup
from netmiko import Netmiko
import requests
from datetime import date
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


Azure = ['AzureContainerRegistry.WestEurope', 'AzureCloud.westeurope', 'Sql.WestEurope', 'Storage.WestEurope']


maskDict = {
    "15": "255.254.0.0",
    "16": "255.255.0.0",
    "17": "255.255.128.0",
    "18": "255.255.192.0",
    "19": "255.255.224.0",
    "20": "255.255.240.0",
    "21": "255.255.248.0",
    "22": "255.255.252.0",
    "23": "255.255.254.0",
    "24": "255.255.255.0",
    "25": "255.255.255.128",
    "26": "255.255.255.192",
    "27": "255.255.255.224",
    "28": "255.255.255.240",
    "29": "255.255.255.248",
    "30": "255.255.255.252",
    "31": "255.255.255.254",
    "32": "255.255.255.255"
}


def deleteOldJson():                        #usuwanie starego JSONa
    listDir = os.listdir('.')
    for item in listDir:
        if item.endswith(".json"):
            oldJson = item
            os.remove(item)
            print('File removed ' + item)
            return(item)


def downloadJson():                                                         #skrypt do pobierania JSONa
    url = settings.MICROSOFT
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    url = soup.find('a', {'class': 'mscom-link failoverLink'})['href']
    filename = wget.download(url)
    print('JSON downloaded: ' + filename)
    return(filename)


def checkMask(x):                                   #Przypisanie maski
    y = x[-2:]
    return maskDict[y]
    """
    match y:
        case '15':
            return '255.254.0.0'
        case '16':
            return '255.255.0.0'
        case '17':
            return '255.255.128.0'
        case '18':
            return '255.255.192.0'
        case '19':
            return '255.255.224.0'
        case '20':
            return '255.255.240.0'
        case '21':
            return '255.255.248.0'
        case '22':
            return '255.255.252.0'
        case '23':
            return '255.255.254.0'
        case '24':
            return '255.255.255.0'
        case '25':
            return '255.255.255.128'
        case '26':
            return '255.255.255.192'
        case '27':
            return '255.255.255.224'
        case '28':
            return '255.255.255.240'
        case '29':
            return '255.255.255.248'
        case '30':
            return '255.255.255.252'
        case '31':
            return '255.255.255.254'
        case '32':
            return '255.255.255.255'
        case _:
            return 0
"""


def ipAddToSubnet(AzureContainer, ipAddress):
    return (' "' + AzureContainer + '.' + ipAddress + '"')


def ipPushToFortigate(AzurePart, ipAddress):                                    #Stworzenie nowego wpisu w firewallu i dopisanie go do listy komend
    command_list = []
    command_list.append('edit "' + AzurePart + '.' + str(ipAddress) + '"')
    mask = str(checkMask(ipAddress))
    ipAddressWithoutMask = ipAddress[:-3]
    command_list.append('set subnet ' + str(ipAddressWithoutMask) + ' ' + mask)
    command_list.append('set allow-routing enable')
    command_list.append('next')
    return command_list


def jsonImport(AzurePart, jsonFileName):
    ipTable = []        #Pusta tablica do przechowania adresów IP
    f = open(jsonFileName,)   #Otwarcie jsona
    data = json.loads(f.read())                     #Odczytanie jsona
    for i in data['values']:                        #Pętla odczytywania wartości
        if i['name'] == AzurePart:                      #Sprawdzenie czy warości odpowiadają wymaganiom
            ipTable += i['properties'].get('addressPrefixes')   #Pobranie adresów IP i przypisanie ich do tablicy
    f.close()           #Zamknięcie jsona
    return ipTable


def sendEmail(receiver, msg):
    receiver_email = receiver
    message = MIMEMultipart("alternative")
    message["Subject"] = "IP Addresses from Azure have been updated"
    message["From"] = settings.SENDER_EMAIL
    message["To"] = receiver_email
    text = msg
    PlainTextBecauseItsEasier = MIMEText(text, "plain")
    message.attach(PlainTextBecauseItsEasier)
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(settings.SENDER_EMAIL, settings.EMAIL_PASS)
        server.sendmail(settings.SENDER_EMAIL, receiver_email, message.as_string())


def logToFile(logText):
    today = date.today()
    filename = today + '.txt'
    if os.path.exists(filename):
        append_or_write = 'a'
    else:
        append_or_write = 'w'
    logFile = open(filename, append_or_write)
    logFile.write(logText + '\n')
    logFile.close()


def main():
    ipAddressesToString = ""
    oldJson = deleteOldJson()                                   #Usunięcie starego JSONa
    print(oldJson)
    jsonFileName = downloadJson()                               #Pobranie nowego JSONa
    print(jsonFileName)
    if oldJson != jsonFileName:
        print("Przystępuję od aktualizacji konfiguracji na fortigate")
        logToFile("-"*20 + "BEGIN" + "-"*20)
        fortek = {                                                  #Dane logowania do fortka
        'host':settings.IP,
        'username':settings.LOGIN,
        'password':settings.PASS,
        'device_type':'fortinet'
        }
        net_connect = Netmiko(**fortek)                             #Nawiązanie połączenia z fortkiem
        for itemAzure in Azure:                                     #Wylistowanie wszystkich adresów z danego regionu Azure
            ipAddresses = jsonImport(itemAzure, jsonFileName)
            command_list = []                                       #Pusta lista komend do puszczenia na fortka
            command_list.append('config firewall address')
            for item in ipAddresses:
                if item[:4] != '2603' and item[:4] != '2a01':
                    command_list.extend(ipPushToFortigate(itemAzure, item))
                    ipAddressesToString += "\n" + item
            command_list.append('end')
            print(command_list)
            send_config = net_connect.send_config_set(command_list) #Puszczenie listy komend na fortka
            print(send_config)
            logToFile(send_config)
            command_list = []                                       #Wyczyszczenie listy komend
            for item in ipAddresses:
                if item[:4] != '2603' and item[:4] != '2a01':
                    members = ""
                    command_list.append('config firewall addrgrp')
                    command_list.append('edit "' + itemAzure + '"')
                    members += ipAddToSubnet(itemAzure, item)
                    command_list.append('append member' + members)
                    command_list.append('next')
                    command_list.append('end')
                    print(command_list)
                    send_config = net_connect.send_config_set(command_list)
                    print(send_config)
                    logToFile(send_config)
                    command_list = []
        sendEmail("august.wardencki@lifeflow.eu", ipAddressesToString)
        sendEmail("piotr.bienias@lifeflow.eu", ipAddressesToString)
        sendEmail("mti@mtisystems.pl", ipAddressesToString)
        logToFile("-"*21 + "END" + "-"*21)
    else:
        print("JSON nie uległ zmianie, konfiguracja fortigate nadal aktualna")

if __name__ == "__main__":                                      #Wykonanie skryptu
    main()
