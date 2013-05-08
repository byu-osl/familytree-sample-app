from pymongo import MongoClient

# FamilyTree API keys
# Sandbox Key
# key = ''
# Production Key
key = ''

# database
connection = MongoClient()
db = connection.app

# logging
ADMINS = ['']
emailAddress = ''
emailPassword = ''
logFile = './app-log'
