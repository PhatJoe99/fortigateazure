import json
import os
import wget
import settings
from bs4 import BeautifulSoup
from netmiko import Netmiko
import requests


Azure = ['AzureContainerRegistry.WestEurope', 'AzureCloud.westeurope', 'Sql.WestEurope', 'Storage.WestEurope']


def deleteOldJson():                        #usuwanie starego JSONa
    listDir = os.listdir('.')
    for item in listDir:
        if item.endswith(".json"):
            os.remove(item)
            print('File removed ' + item)


deleteOldJson()


def downloadJson():                                                         #skrypt do pobierania JSONa
    url = settings.MICROSOFT
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    url = soup.find('a', {'class': 'mscom-link failoverLink'})['href']
    filename = wget.download(url)
    print('JSON downloaded: ' + filename)
    return(filename)


downloadJson()


def checkMask(x):                                   #Przypisanie maski
    y = x[-2:]
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


def ipAddToSubnet(AzureContainer, ipAddress):
    return (' "' + AzureContainer + '.' + ipAddress + '"')


def ipPushToFortigate(AzurePart, ipAddress):                                    #Stworzenie nowego wpisu w firewallu i dopisanie go do listy komend
    command_list = []
    command_list.append('edit "' + AzurePart + '.' + str(ipAddress) + '"')
    ipAddressWithoutMask = ipAddress[:-3]
    command_list.append('set subnet ' + str(ipAddressWithoutMask) + ' ' + str(checkMask(ipAddress)))
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


def main():
    deleteOldJson()                                             #Usunięcie starego JSONa
    jsonFileName = downloadJson()                               #Pobranie nowego JSONa
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
            command_list.extend(ipPushToFortigate(item))
        command_list.append('end')
        send_config = net_connect.send_config_set(command_list) #Puszczenie listy komend na fortka
        command_list = []                                       #Wyczyszczenie listy komend
        command_list.append('config firewall addrgrp')
        command_list.append('edit "' + itemAzure + '"')
        members = ""
        for item in ipAddresses:
            members += ipAddToSubnet(itemAzure, item)
        command_list.append('set member' + members)
        command_list.append('next')
        command_list.append('end')
        send_config = net_connect.send_config_set(command_list)
        command_list = []