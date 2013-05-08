from flask import session

from views.exceptions import *
from config import db
from base import Base
from familytree.api import API

import datetime
import json
import threading
import time
import types


class PedigreeFetch(threading.Thread):
    def __init__(self,access_token='',user=None,api_id=''):
        threading.Thread.__init__(self)
        self.access_token = access_token
        self.user = user
        self.api_id = api_id
        self.personIDs = []

    def run(self):
        # get all the IDs of people in the pedigree
        api = API(self.access_token)
        data = api.get_pedigree(self.api_id)
        self.personIDs = []
        for person in data['persons']:
            self.personIDs.append(person['id'])

class Person(Base):
    def __init__(self,entries=None):
        if entries:
            Base.__init__(self, entries)
            return
        self.version = '1.0'
        self.user_id = ''
        self.api_id = ''
        self.api_data = {}
        self.name = {}
        self.gender = ''
        self.living = 'True'
        self.facts = {}
        self.parents = []
        self.families = []
        self.pedigree = []
        self.descendants = []
        self.missing_info = {}

    @staticmethod
    def new(user_id='',api_id=''):
        person = Person()
        person.user_id = user_id
        person.api_id = api_id
        return person

    @staticmethod
    def copy(person):
        pnew = Person()
        pnew._id = person._id
        pnew.user_id = person.user_id
        pnew.api_id = person.api_id
        try:
            pnew.api_data = person.api_data
        except:
            pass
        pnew.parse()
        return pnew

    @staticmethod
    def get(user=None,api_id='',sync=False,quick=False):
        if not user or not api_id:
            raise DBError

        # lookup person in deceased DB first then living
        data = db.deceased.find_one({'api_id':api_id})
        if not data:
            data = db.living.find_one({'user_id':user.api_id,'api_id':api_id})
        # wrap in person object
        if not data:
            person = Person.new(user_id=user.api_id,api_id=api_id)
        else:
            person = Person(data)

        # convert to new version
        if person.version != "1.0":
            person = person.copy(person)
            person.save()

        if not quick and (sync or person.stale()):
            api = API(session['access_token'])
            person.api_data = api.get_individual(api_id)
            person.parse()
            person.save()
        
        return person

    @staticmethod
    def get_people(user=None,personIDs=[],sync=False):
        if not personIDs:
            return []
        # select the persons that need to be fetched
        api = API(session['access_token'])
        pdict = {}
        ids = []
        for personID in personIDs:
            person = Person.get(user=user,api_id=personID,quick=True)
            pdict[personID] = person
            if sync or person.stale():
                ids.append(personID)

        # get person data
        pdata = api.get_individuals(ids)
        for data in pdata:
            personID = data['persons'][0]['id']
            pdict[personID].api_data = data
            pdict[personID].parse()

        # save any fetched persons
        for api_id in ids:
            pdict[api_id].save()

        # collect results
        people = []
        for personID in personIDs:
            person = pdict[personID]
            people.append(person)

        return people

    @staticmethod
    def pedigree(user=None,api_id='',generations=4,sync=False):
        if not sync:
            # check cached IDs and people
            people = Person.get_pedigree(user=user,api_id=api_id)
            if people != []:
                return people
 
        # get all the IDs of people in the pedigree
        api = API(session['access_token'])
        data = api.get_pedigree(api_id)
        personIDs = []
        for person in data['persons']:
            personIDs.append(person['id'])

        # get all the people in the pedigree
        people = Person.get_people(user=user,personIDs=personIDs,sync=sync)

        # find the leaves and get another four generations for each one
        pdict = {}
        for person in people:
            pdict[person.getID()] = person
        appIDs = Person.find_fourth(api_id=api_id,pdict=pdict)
        appPersonIDs = Person.get_pedigrees(user=user,appIDs=appIDs)
        # remove the people we already fetched
        for personID in personIDs:
            if personID in appPersonIDs:
                appPersonIDs.remove(personID)

        # get all those people
        app_people = Person.get_people(user=user,personIDs=appPersonIDs,sync=sync)

        # add them all up
        people.extend(app_people)

        # save people into person
        person = Person.get(user=user,api_id=api_id)
        person.pedigree = []
        for p in people:
            person.pedigree.append(p.api_id)
        person.save()
        return people

    @staticmethod
    def get_pedigree(user=None,api_id=''):
        if not user or not api_id:
            raise DBError

        person = Person.get(user=user,api_id=api_id)
        if not person or person.pedigree == []:
            return []

        people = []
        # check deceased for these people
        db_people = db.deceased.find({'api_id': {"$in": person.pedigree}})
        for db_person in db_people:
            people.append(Person(db_person))
        # check living for these people
        db_people = db.living.find({'api_id': {"$in": person.pedigree}})
        for db_person in db_people:
            people.append(Person(db_person))

        return people

    @staticmethod
    def get_pedigrees(user=None,appIDs=[]):
        threads = []
        for appID in appIDs:
            thread = PedigreeFetch(access_token=session['access_token'],user=user,api_id=appID)
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()

        personIDs = []
        for thread in threads:
            personIDs.extend(thread.personIDs)
        return personIDs

    @staticmethod
    def find_fourth(api_id='',pdict={},generation=1):
        if api_id == '':
            return []
        if generation == 4:
            return [api_id]
        if api_id not in pdict:
            return []
        fatherID = pdict[api_id].getFatherID()
        motherID = pdict[api_id].getMotherID()
        fleaves = Person.find_fourth(fatherID,pdict,generation+1)
        mleaves = Person.find_fourth(motherID,pdict,generation+1)
        return fleaves + mleaves

    def save(self):
        if self.living:
            db.living.save(self.serialize())
        else:
            db.deceased.save(self.serialize())

    def stale(self):
        if self.api_data == {}:
            return True
        return False

    """ Parsing """

    def parse(self):
        self.parse_name()
        self.parse_gender()
        self.parse_living()
        self.parse_facts()
        self.parse_parents()
        self.parse_couples()
        self.order_couples()

    def set_dict(self,obj,name):
        if name in obj and obj[name] == None:
            obj[name] = {}
        if not name in obj:
            obj[name] = {}

    def set_list(self,obj,name):
        if name in obj and obj[name] == None:
            obj[name] = []
        if not name in obj:
            obj[name] = []

    def set_str(self,obj,name):
        if name in obj and obj[name] == None:
            obj[name] = ""
        if not name in obj:
            obj[name] = ""

    def set_bool(self,obj,name):
        if name in obj and obj[name] == None:
            obj[name] = False
        if not name in obj:
            obj[name] = False

    def cleanup_name(self):
        pass

    def parse_name(self):
        self.cleanup_name()
        person = self.api_data['persons'][0]
        self.name = {'full':'','given':'','first':'','family':''}
        for name in person['names']:
            if not name['preferred']:
                continue
            for form in name['nameForms']:
                if form['lang'] != 'i-default':
                    continue
                self.name['full'] = form['fullText']
                for part in form['parts']:
                    if part['type'] == 'http://gedcomx.org/Given':
                        self.name['given'] = part['value']
                    if part['type'] == 'http://gedcomx.org/Surname':
                        self.name['family'] = part['value']

    def cleanup_gender(self):
        person = self.api_data['persons'][0]
        self.set_dict(person,'gender')
        self.set_dict(person['gender'],'type')

    def parse_gender(self):
        self.cleanup_gender()
        person = self.api_data['persons'][0]
        self.gender = ''
        if person['gender']['type'] == 'http://gedcomx.org/Male':
            self.gender = 'Male'
        if person['gender']['type'] == 'http://gedcomx.org/Female':
            self.gender = 'Female'

    def parse_living(self):
        person = self.api_data['persons'][0]
        self.living = person['living']

    def cleanup_facts(self):
        person = self.api_data['persons'][0]
        self.set_dict(person,'facts')
        for fact in person['facts']:
            self.set_str(fact,'type')
            self.set_dict(fact,'date')
            self.cleanup_date(fact['date'])
            self.set_dict(fact,'place')
            self.cleanup_place(fact['place'])

    def parse_facts(self):
        self.cleanup_facts()
        person = self.api_data['persons'][0]
        for fact in person['facts']:
            if fact['type'] == 'http://gedcomx.org/Birth':
                kind = 'birth'
            elif fact['type'] == 'http://gedcomx.org/Death':
                kind = 'death'
            else:
                continue
            blank = self.blank_date()
            blank['date'] = self.parse_date(fact['date'])
            blank['place'] = self.parse_place(fact['place'])
            blank['year'],blank['month'],blank['day'] = self.parse_date_parts(fact['date'])
            self.facts[kind] = blank

    def cleanup_parents(self):
        self.set_dict(self.api_data,'childAndParentsRelationships')
        for relationship in self.api_data['childAndParentsRelationships']:
            self.set_dict(relationship,'child')
            self.set_dict(relationship,'father')
            self.set_dict(relationship,'mother')
            self.set_str(relationship['child'],'resourceId')
            self.set_str(relationship['father'],'resourceId')
            self.set_str(relationship['mother'],'resourceId')

    def parse_parents(self):
        self.cleanup_parents()
        self.parents = []
        for relationship in self.api_data['childAndParentsRelationships']:
            # parse the child, father, and mother
            childID = relationship['child']['resourceId']
            fatherID = relationship['father']['resourceId']
            motherID = relationship['mother']['resourceId']
            if not childID:
                continue
            # is this a parent relationship?
            if childID == self.api_id:
                # add set of parents to this person
                parents = {'motherID':motherID,'fatherID':fatherID}
                self.parents.append(parents)
            else:
                # find out which person is the spouse
                if fatherID != self.api_id:
                    spouseID = fatherID
                elif motherID != self.api_id:
                    spouseID = motherID
                else:
                    continue
                # add child to the appropriate family
                added = False
                for family in self.families:
                    if family['spouseID'] == spouseID:
                        added = True
                        if childID not in family['children']:
                            family['children'].append(childID)
                        break
                if not added:
                    family = {'spouseID':spouseID,'marriage':self.blank_date(),'children':[childID]}
                    self.families.append(family)
            
    def cleanup_couples(self):
        self.set_dict(self.api_data,'relationships')
        for relationship in self.api_data['relationships']:
            self.set_dict(relationship,'person1')
            self.set_dict(relationship,'person2')
            self.set_str(relationship['person1'],'resouceId')
            self.set_str(relationship['person2'],'resouceId')
            self.set_dict(relationship,'facts')
            for fact in relationship['facts']:
                self.set_dict(fact,'date')
                self.cleanup_date(fact['date'])
                self.set_dict(fact,'place')
                self.cleanup_place(fact['place'])
                self.set_str(fact,'type')

    def parse_couples(self):
        self.cleanup_couples()
        for relationship in self.api_data['relationships']:
            # get the couple
            person1ID = relationship['person1']['resourceId']
            person2ID = relationship['person2']['resourceId']
            if person1ID != self.api_id:
                spouseID = person1ID
            elif person2ID != self.api_id:
                spouseID = person2ID
            else:
                continue
            # get the marriage date
            found = False
            for fact in relationship['facts']:
                if fact['type'] == 'http://gedcomx.org/Marriage':
                    found = True
                    date = self.parse_date(fact['date'])
                    year, month, day = self.parse_date_parts(fact['date'])
                    place = self.parse_place(fact['place'])
                    break
            if not found:
                continue
            # find the family record
            for family in self.families:
                if family['spouseID'] == spouseID:
                    family['marriage']['date'] = date
                    family['marriage']['year'] = year
                    family['marriage']['month'] = month
                    family['marriage']['day'] = day
                    family['marriage']['place'] = place
                    break

    def order_couples(self):
        s1 = sorted(self.families, key = lambda k: k['marriage']['day'])
        s2 = sorted(s1, key = lambda k: k['marriage']['month'])
        self.families =  sorted(s2, key = lambda k: k['marriage']['year'])

    def blank_date(self):
        return {'date':'','place':'','year':'','month':'','day':''}

    def cleanup_date(self,date):
        self.set_list(date,'normalized')
        for value in date['normalized']:
            self.set_str(value,'value')
        self.set_str(date,'original')
        self.set_str(date,'formal')

    def parse_date(self,date):
        normalized = ''
        if date['normalized']:
            normalized = date['normalized'][0]['value']
        original = date['original']
        if normalized:
            return normalized
        return original

    def parse_date_parts(self,date):
        year = ''
        month = ''
        day = ''
        try:
            parts = date['formal'].split('-')
            year = parts[0]
            try:
                year = year[year.index('+')+1:]
            except:
                pass
            month = parts[1]
            day = parts[2]
            a = int(year)
            a= int(month)
            a= int(day)
        except:
            year = ''
            month = ''
            day = ''
        return year,month,day

    def cleanup_place(self,place):
        self.set_str(place,'original')

    def parse_place(self,place):
        return place['original']

    """ Getting """

    def getID(self):
        return self.api_id

    def getFullName(self):
        return self.name['full']

    def getGivenName(self):
        return self.name['given']

    def getFirstName(self):
        return self.name['given']

    def getFamilyName(self):
        return self.name['family']

    def getGender(self):
        return self.gender

    def getBirth(self):
        if 'birth' in self.facts:
            return self.facts['birth']
        return self.blank_date()

    def getBirthDate(self):
        try:
            birth = self.getBirth()
            return birth['date']
        except:
            return ''

    def getBirthPlace(self):
        try:
            birth = self.getBirth()
            return birth['place']
        except:
            return ''

    def getBirthYear(self):
        try:
            birth = self.getBirth()
            return birth['year']
        except:
            return ''

    def getBirthMonth(self):
        try:
            birth = self.getBirth()
            return birth['month']
        except:
            return ''

    def getBirthDay(self):
        try:
            birth = self.getBirth()
            return birth['day']
        except:
            return ''

    def getDeath(self):
        if 'death' in self.facts:
            return self.facts['death']
        return self.blank_date()

    def getDeathDate(self):
        try:
            death = self.getDeath()
            return death['date']
        except:
            return ''

    def getDeathPlace(self):
        try:
            death = self.getDeath()
            return death['place']
        except:
            return ''

    def getDeathYear(self):
        try:
            death = self.getDeath()
            return death['year']
        except:
            return ''

    def getDeathMonth(self):
        try:
            death = self.getDeath()
            return death['month']
        except:
            return ''

    def getDeathDay(self):
        try:
            death = self.getDeath()
            return death['day']
        except:
            return ''

    def getParents(self):
        return self.parents
                
    def getMotherID(self):
        try:
            parents = self.getParents()
            return parents[0]['motherID']
        except:
            return ''

    def getFatherID(self):
        try:
            parents = self.getParents()
            return parents[0]['fatherID']
        except:
            return ''

    def getFamilies(self):
        return self.families

    def getSpouseIDs(self):
        spouses = []
        for family in self.getFamilies():
            if family['spouseID']:
                spouses.append(family['spouseID'])
        return spouses

    def getSpouseID(self):
        try:
            families = self.getFamilies()
            return families[0]['spouseID']
        except:
            return None
        
    def getChildrenIDs(self):
        childrenIDs = []
        for family in self.getFamilies():
            childrenIDs.extend(family['children'])
        return childrenIDs

    def sortChildren(self,children):
        for family in self.getFamilies():
            if self.childrenPresent(children,family['children']):
                family['children'] = sorted(family['children'],key = lambda childID: children[childID].getBirthYear())

    def childrenPresent(self,children,childrenIDs):
        for childID in childrenIDs:
            if childID not in children:
                return False
        return True

    def getMarriageDate(self):
        try:
            families = self.getFamilies()
            return families[0]['marriage']['date']
        except:
            return ''

    def getMarriageYear(self):
        try:
            families = self.getFamilies()
            return int(families[0]['marriage']['year'])
        except:
            return 0

    def getMarriagePlace(self):
        try:
            families = self.getFamilies()
            return families[0]['marriage']['place']
        except:
            return ''

    def within(self,diff,nowYear,year):
        if not year:
            return False
        years = int(nowYear) - int(year)
        if years <= diff:
            return True
        return False

    def diedAsChild(self):
        birthYear = self.getBirthYear()
        deathYear = self.getDeathYear()
        birthMonth = self.getBirthMonth()
        deathMonth = self.getDeathMonth()
        birthDay = self.getBirthDay()
        deathDay = self.getDeathDay()
        if not birthYear or not deathYear:
            return False
        if int(deathYear) - int(birthYear) < 8:
            return True
        if (int(deathYear) - int(birthYear) == 8):
            if not birthMonth or not deathMonth:
                return False
            if int(deathMonth) < int(birthMonth):
                return True
            if not birthDay or not deathDay:
                return False
            if int(deathMonth) == int(birthMonth):
                if int(deathDay) < int(birthDay):
                    return True
            
        return False
