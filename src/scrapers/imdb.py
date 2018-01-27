#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import unicode_literals
from ..helpers import get_config_file, HEADERS
from .base_scraper import BaseScraper
import lxml.html
import requests
import time
from   unicodedata import normalize


class IMDB(BaseScraper):

  def __init__(self):
    pass

  def construct_search_url(self, title):
    # Construct search results url for specified title

    safe_title = normalize("NFC", title).replace(" ", "+").replace("&", "%26").replace("?", "%3F").lower()
    return get_config_file()["base_url"] + get_config_file()["search_path"] + safe_title + get_config_file()["url_end"]

  def get_title(self, xml_doc):
    try:
      return xml_doc.xpath('//div[@class="title_block"]//h1/text()')[0].strip()
    except IndexError:
      return ''

  def get_alternative_title(self, xml_doc):
    try:
      return xml_doc.xpath('//div[@class="title_wrapper"]//div[@class="originalTitle"]/text()')
    except IndexError:
      return ''

  def get_description(self, xml_doc):
    try:
      return xml_doc.xpath('//div[@class="summary_text"]')[0].text_content().strip().replace('See full summary', '').replace('»', '').strip()
    except IndexError:
      return ''

  def get_director(self, xml_doc):
    try:
      return xml_doc.xpath('//div[@class="plot_summary_wrapper"]/div[1]/div[2]/span/a/span/text()')
    except IndexError:
      return ''

  def get_rating(self, xml_doc):
    try:
      return xml_doc.xpath('//span[@itemprop="ratingValue"]/text()')[0].strip()
    except IndexError:
      return ''

  def get_genres(self, xml_doc):
    try:
      return xml_doc.xpath('//div[@class="title_wrapper"]//div[@class="subtext"]//span[@itemprop="genre"]/text()')
    except IndexError:
      return ''

  def get_votes(self, xml_doc):
    try:
      return xml_doc.xpath('//span[@itemprop="ratingCount"]/text()')[0].strip()
    except IndexError:
      return ''

  def get_running_time(self, xml_doc):
    try:
      return xml_doc.xpath('//time[@itemprop="duration"]/text()')[0].strip()
    except IndexError:
      return ''

  def get_content_rating(self, xml_doc):
    try:
      return xml_doc.xpath('//div[@class="title_wrapper"]/div[@class="subtext"]//*[@itemprop="contentRating"]/@content')
    except IndexError:
      return ''

  def get_stars(self, xml_doc):
    try:
      return xml_doc.xpath('//div[@class="title-overview"]//*[@itemprop="actors"]/a/span/text()')
    except IndexError:
      try:
        return xml_doc.xpath('//div[@class="plot_summary_wrapper"]/div[1]/div[3]/span/a/span/text()')
      except IndexError:
        return ''

  def get_languages(self, xml_doc):
    try:
      if xml_doc.xpath('//*[@id="titleDetails"]/div[3]/h4/text()') == ['Language:']:
        return xml_doc.xpath('//*[@id="titleDetails"]/div[3]/a/text()')
      else:
        return xml_doc.xpath('//*[@id="titleDetails"]/div[2]/a/text()')
    except IndexError:
      return ''

  def get_image_url(self, xml_doc):
    try:
      return xml_doc.xpath('//*[@class="poster"]/a/img/@src')[0]
    except IndexError:
      return ''

  # Movie specific functions
  def get_movie_year(self, xml_doc):
    try:
      return xml_doc.xpath('//*[@class="title_wrapper"]//span[@id="titleYear"]/a/text()')[0]
    except IndexError:
      return ''

  def get_awards(self, xml_doc):
    try:
      awards = xml_doc.xpath('//*[@id="titleAwardsRanks"]/span[@itemprop="awards"]/b/text()')[0].strip()
      if not "oscar" in awards.lower():
        return ''
      else:
        if awards[-1:] == ".":
          return ' '.join(xml_doc.xpath('//*[@id="titleAwardsRanks"]/span[@itemprop="awards"]/b/text()')[0].strip().split())
        try:
          return get_config_file()['base_url'] + movie_page.xpath('//*[@id="titleAwardsRanks"]/span[@class="see-more inline"]/a/@href')[0]
        except IndexError:
          return ''
    except IndexError:
      return ''

  # Series Specific Functions
  def get_series_year(self, xml_doc):
    try:
      return xml_doc.xpath('//div[@class="title_wrapper"]//div[@class="subtext"]/a/text()')[0].strip().split('(')[-1].split(')')[0].strip()
    except IndexError:
      return ''

  def get_creator(self, xml_doc):
    try:
      return xml_doc.xpath('//div[@class="title-overview"]//*[@itemprop="creator"]/a/span/text()')
    except IndexError:
      return ''


  # Full Response Payloads

  def get_movie_details(self, movie, movie_url):
    # Scrape movie page for attributes specified below

    if movie_url != None:
      movie_page = lxml.html.document_fromstring(requests.get(movie_url, headers=HEADERS).content)

      return {
        'url':                movie_url,
        'filename':           movie['name'],
        'extension':          movie['extension'],
        'info_retrieved':     time.strftime("%Y-%m-%d"),
        'title':              self.get_title(movie_page),
        'alternative_title':  self.get_alternative_title(movie_page),
        'year':               self.get_movie_year(movie_page),
        'description':        self.get_description(movie_page),
        'director':           self.get_director(movie_page),
        'stars':              self.get_stars(movie_page),
        'genre':              self.get_genres(movie_page),
        'rating':             self.get_rating(movie_page),
        'votes':              self.get_votes(movie_page),
        'running_time':       self.get_running_time(movie_page),
        'languages':          self.get_languages(movie_page),
        'content_rating':     self.get_content_rating(movie_page),
        'awards':             self.get_awards(movie_page),
        'image_url':          self.get_image_url(movie_page),
      }


  def get_series_details(self, series, series_url):
    # Scrape series page for attributes specified below

    if series_url != None:
      series_page = lxml.html.document_fromstring(requests.get(series_url, headers=HEADERS).content)

      return {
        'url':            series_url,
        'filename':       series['name'],
        'extension':      series['extension'],
        'info_retrieved': time.strftime("%Y-%m-%d"),
        'title':          self.get_title(series_page),
        'year':           self.get_series_year(series_page),
        'description':    self.get_description(series_page),
        'creator':        self.get_creator(series_page),
        'stars':          self.get_stars(series_page),
        'genre':          self.get_genres(series_page),
        'rating':         self.get_rating(series_page),
        'votes':          self.get_votes(series_page),
        'running_time':   self.get_running_time(series_page),
        'languages':      self.get_languages(series_page),
        'content_rating': self.get_content_rating(series_page),
        'image_url':      self.get_image_url(series_page),
      }

