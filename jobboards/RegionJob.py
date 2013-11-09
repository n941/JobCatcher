#!/usr/bin/env python
# -*- coding: utf-8 -*-

__authors__ = [
    'Yoann Sculo <yoann.sculo@gmail.com>',
    'Bruno Adelé <bruno@adele.im>',
]
__license__ = 'GPLv2'
__version__ = '0.1'

# System
import re
import time
import glob
from datetime import datetime

# Third party
import sqlite3 as lite
from html2text import html2text 
from BeautifulSoup import BeautifulSoup

# Jobcatcher
from jobcatcher import JobBoard
from jobcatcher import Offer


class JBRegionJob(JobBoard):

    def __init__(self, configs=[], interval=1200):
        self.name = "RegionJob"
        super(JBRegionJob, self).__init__(configs, interval)
        self.encoding = {'feed': 'utf-8', 'page': 'utf-8'}

    def getUrls(self):
        """Get Urls offers from feed"""

        urls = list()
        searchdir = "%s/feeds/*.feed" % self._processingDir

        for feed in glob.glob(searchdir):
            # Load the HTML feed
            fd = open(feed, 'rb')
            html = fd.read().decode(self.encoding['feed'])
            fd.close()

            # Search result
            res = re.finditer(
                r'<item>(.*?)</item>',
                html,
                flags=re.MULTILINE | re.DOTALL
            )
            for r in res:
                # Check if URL is valid
                m = re.search(r'<link>(.*?clients/offres_chartees/offre_chartee_modele\.aspx\?numoffre=.*?)</link>', r.group(1))
                if m:
                    urls.append(m.group(1))

        return urls

    def _regexExtract(self, regex, soup):
        """Extract a field in html page"""

        html = unicode.join(u'\n', map(unicode, soup))

        res = None
        m = re.search(regex, html, flags=re.MULTILINE | re.DOTALL)
        if m:
            res = html2text(m.group(1)).strip()

        return res

    def _extractRubrique(self, field, soup):
        """Extract rubrique"""

        html = unicode.join(u'\n', map(unicode, soup))

        res = None
        regex = ur'<p class="rubrique_annonce">%s</p>.*?<p>(.*?)</p>' % field
        m = re.search(regex, html, flags=re.MULTILINE | re.DOTALL)
        if m:
            res = html2text(m.group(1)).strip()

        return res

    def analyzePage(self, url, html):
        """Analyze page and extract datas"""

        soup = BeautifulSoup(html, fromEncoding=self.encoding['page'])
        item = soup.body.find('div', attrs={'id': 'annonce'})

        if (item is None):
            return 1

        # Title
        h1 = item.find('h1')
        if (h1 is None):
            return 1

        # Title & Url
        self.datas['title'] = html2text(h1.text).strip()
        self.datas['url'] = url

        # Date & Ref
        p = item.find('p', attrs={'class': 'date_ref'})
        self.datas['ref'] = self._regexExtract(ur'Réf :(.*)', p)
        self.datas['date_add'] = int(time.time())
        self.datas['date_pub'] = datetime.strptime(
            self._regexExtract(ur'publié le(.*?)<br />', p),
            "%d/%m/%Y").strftime('%s')

        # Job informations
        p = item.find('p', attrs={'class': 'contrat_loc'})
        self.datas['location'] = self._regexExtract(
            ur'Localisation :.*?<strong>(.*?)</strong>', p
        )
        self.datas['company'] = self._regexExtract(
            ur'Entreprise :.*?<strong>(.*?)</strong>', p
        )
        self.datas['contract'] = self._regexExtract(
            ur'Contrat :.*?<strong>(.*?)</strong>', p
        )

        # Salary
        self.datas['salary'] = self._extractRubrique("Salaire", item)

        # Insert to jobboard table
        self.insertToJBTable()

    def createTable(self,):
        if self.isTableCreated():
            return

        conn = None
        conn = lite.connect(self.configs['global']['database'])
        cursor = conn.cursor()

        # create a table
        cursor.execute("""CREATE TABLE jb_%s( \
                       ref TEXT, \
                       url TEXT, \
                       date_pub INTEGER, \
                       date_add INTEGER, \
                       title TEXT, \
                       company TEXT, \
                       contract TEXT, \
                       location TEXT, \
                       salary TEXT, \
                       PRIMARY KEY(ref))""" % self.name)

    def insertToJBTable(self):
        conn = lite.connect(self.configs['global']['database'])
        conn.text_factory = str
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO jb_%s VALUES(?,?,?,?,?,?,?,?,?)" %
                           self.name, (
                               self.datas['ref'],
                               self.datas['url'],
                               self.datas['date_pub'],
                               self.datas['date_add'],
                               self.datas['title'],
                               self.datas['company'],
                               self.datas['contract'],
                               self.datas['location'],
                               self.datas['salary'],
                           )
            )

            conn.commit()
        except lite.IntegrityError:
            pass
        finally:
            if conn:
                conn.close()

        return 0

    def createOffer(self, data):
        """Create a offer object with jobboard data"""
        data = dict(data)

        o = Offer()
        o.src = self.name
        o.url = data['url']
        o.ref = data['ref']
        o.title = data['title']
        o.company = data['company']
        o.contract = data['contract']
        o.location = data['location']
        o.salary = data['salary']
        o.date_pub = data['date_pub']
        o.date_add = data['date_add']

        if o.ref and o.company:
            return o

        return None
