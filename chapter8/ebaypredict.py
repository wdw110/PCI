#encoding=utf-8

import httplib
from xml.dom.minidom import parse, parseString, Node

devKey = 'developerkey'
appKey = 'applicationkey'
certKey = 'certificatekey'
userToken = 'token'

def getHeaders(apicall,siteID='0',compatabilityLevel='433'):
	headers = {"X-EBAY-API-COMPATIBILITY-LEVEL": compatabilityLevel,
			   "X-EBAY-API-DEV-NAME": devKey,
			   "X-EBAY-API-APP-NAME": appKey,
			   "X-EBAY-API-CERT-NAME": appKey,
			   "X-EBAY-API-CALL-NAME": apicall,
			   "X-EBAY-API-SITEID": siteID,
			   "Content-Type": 'text/xml'}
	return headers