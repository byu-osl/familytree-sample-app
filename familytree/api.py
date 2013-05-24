from flask import session

# Python imports
from datetime import datetime, timedelta
import json
import threading
import time
import urllib
import urllib2

# local imports
from config import sandbox
import parser
from views.exceptions import NotLoggedInException, NotRespondingException

class Downloader:
    def __init__(self,access_token,urls):
        self.access_token = access_token
        self.urls = urls
        self.retries = 0
        self.delayed = False
        self.delay_time = 0.5

    def delay(self):
        if self.delayed:
            self.delay_time = self.delay_time * 2
            if self.delay_time >= 8:
                self.delay_time = 8
            time.sleep(self.delay_time)
            self.retries += 1
            if self.retries > 10:
                raise NotRespondingException

    def run_threads(self):
        threads = []
        for url in self.urls:
            thread = Getter(self.access_token,url)
            thread.start()
            threads.append(thread)
        # join threads
        for thread in threads:
            thread.join()
        return threads

    def get_results(self,threads):
        results = []
        for thread in threads:
            if thread.finished:
                results.append(thread.input)
                self.urls.remove(thread.url)
            elif thread.delayed:
                self.delayed = True
            elif thread.exception:
                raise thread.exception
        return results

    def run(self):
        results = []
        while len(self.urls) > 0:
            # delay if needed
            self.delay()
            # start threads
            threads = self.run_threads()
            # collect results
            results.extend(self.get_results(threads))

        return results
    

class Getter(threading.Thread):
    def __init__(self,access_token,url):
        threading.Thread.__init__(self)
        self.access_token = access_token
        self.url = url
        self.input = None
        self.finished = False
        self.delayed = False
        self.exception = None

    def run(self):
        try:
            request = urllib2.Request(self.url)
            request.add_header('Accept','application/x-gedcomx-v1+json,application/x-fs-v1+json')
            request.add_header('Authorization','Bearer ' + self.access_token)
            response = urllib2.urlopen(request)
            self.input = response.read()
            self.finished = True
            response.close()
        except urllib2.HTTPError as h:
            self.input = None
            if h.code == 503:
                self.delayed = True
            if h.code == 429:
                self.delayed = True
            elif h.code == 401:
                self.exception = NotLoggedInException()
            else:
                self.exception = h
        except urllib2.URLError as e:
            self.delayed = True
        except Exception as e:
            self.input = None
            self.exception = e

class API:
    def __init__(self,access_token):
        self.access_token = access_token
        self.agent = 'app/1.0'
        self.user = None

    def get_user(self):
        # get user
        uri = session['discovery']['links']['current-user']['href']
        d = Downloader(self.access_token,[uri])
        results = d.run()
        response = json.loads(results[0])
        user = response['users'][0]
        return user

    def get_permissions(self):
        uri = 'https://api.familysearch.org/identity/v2/permission?product=FamilyTree&sessionId=%s&dataFormat=application/json' % (self.access_token)
        d = Downloader(self.access_token,[uri])
        results = d.run()
        response = json.loads(results[0])
        return response

    def get_user_person(self):
        # get user person
        uri = session['discovery']['links']['current-user-person']['href']
        d = Downloader(self.access_token,[uri])
        results = d.run()
        response = json.loads(results[0])
        person = response['persons'][0]
        return person

    def get_individual(self, api_id):
        """Request a person read for an ID, then return the person."""
        if sandbox:
            uri = "https://sandbox.familysearch.org/platform/tree/persons-with-relationships?person=%s" % (api_id)
        else:
            uri = "https://familysearch.org/platform/tree/persons-with-relationships?person=%s" % (api_id)
        d = Downloader(self.access_token,[uri])
        results = d.run()
        response = json.loads(results[0])
        return response

    def get_individuals(self, api_ids):
        """Request a person read for a list of IDs, then return the
        responses."""
        uris = []
        for api_id in api_ids:
            if sandbox:
                uri = "https://sandbox.familysearch.org/platform/tree/persons-with-relationships?person=%s" % (api_id)
            else:
                uri = "https://familysearch.org/platform/tree/persons-with-relationships?person=%s" % (api_id)
            uris.append(uri)
        d = Downloader(self.access_token,uris)
        results = d.run()
        people = []
        for result in results:
            people.append(json.loads(result))
        return people

    def get_pedigree(self, api_id):
        """Request a pedigree read, then return a list of the person
        IDs associated with the pedigree."""

        if sandbox:
            uri = 'https://sandbox.familysearch.org/platform/tree/ancestry?person=%s' % (api_id)
        else:
            uri = 'https://familysearch.org/platform/tree/ancestry?person=%s' % (api_id)
        d = Downloader(self.access_token,[uri])
        results = d.run()
        response = json.loads(results[0])
        return response
