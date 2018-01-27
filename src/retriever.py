#!/usr/bin/env python
# -*- coding: utf8 -*-

from   __future__ import unicode_literals
from   datetime import datetime
from   .helpers import HEADERS, verify_config_file, video_media_details, get_filepath_from_dir, path_of_depth, get_nested_directory_contents
import jinja2
import json
import lxml.html
from   .message import Message
import os
import requests
import pdb
from . import scraper
import pymediainfo
import shutil
import sys
import time
from   unicodedata import normalize
import urllib


class Retriever():

  def __init__(self):
    self.config = verify_config_file()
    self.movie_scraper  = scraper.Scraper("IMDB")
    self.series_scraper = scraper.Scraper("IMDB")
 

  def start(self, dry_run=False):
    script_started = datetime.now()

    if dry_run:
      self.generate_site([], [])
    else:
      movie_list  = self.initialize_asset_repo("movies", "movie")
      series_list = self.initialize_asset_repo("series", "series")
      self.generate_site(movie_list, series_list)

    Message.success("Script completed after {} seconds\n".format((datetime.now() - script_started).seconds))


  def initialize_asset_repo(self, base_path, mediatype):
    # Create empty datafiles if not present

    if not os.path.isfile(self.config['assets'][base_path]['saved_data']):
      with open(self.config['assets'][base_path]['saved_data'], 'w+') as item_feed:
        json.dump({}, item_feed)

    if self.config['assets'][base_path]['index_asset']:

      return self.compile_file_list(
        self.config['assets'][base_path]['location'],
        self.config['assets'][base_path]['saved_data'],
        mediatype
      )

    return []


  def get_file_list(self, path, repo, mediatype):
    asset_type = "movies" if mediatype == "movie" else mediatype

    try:
      # Enforce per asset type limit
      if not self.config["assets"][asset_type]["max_assets"] == 0:
        file_list = os.listdir(path)[0:self.config["assets"][asset_type]["max_assets"]]
      else:
        file_list = os.listdir(path)
    
    except OSError:
      Message.error(
        "Path \"{}\" not found. Specify a valid path in conf.json and ensure all directories on this path exist.\n".format(path)
      )
      raise SystemExit

    filtered_file_list = []

    for file in file_list:

      # If the extension is in include_extension, or file is a folder not preceded by '_'
      if (((os.path.isfile(path + file) and file.split(".")[-1:][0].lower() in self.config["include_extensions"]) or
           (os.path.isdir(path + file) and file[0] != "_")) and
           file not in self.config["exclude_files"]):

        # Strip extension from file
        if os.path.isfile(path + file):
          file_details = {
            'name':           file.rsplit(".", 1)[0],
            'extension':      file.rsplit('.', 1)[1],
            'full_path':      path + file,
            'relative_path':  file
          }

        else:
          nested_filepath = get_filepath_from_dir(path + file)
          extension = nested_filepath.split('.')[-1] if nested_filepath else None
          file_details = {
            'name':           file,
            'extension':      extension,
            'full_path':      nested_filepath,
            'relative_path':  path_of_depth(nested_filepath, 2)
          }

        # Drop prepending "._" from files on external drives
        if file_details['name'][0:2] == "._":
          file_details['name'] = file_details['name'][2:]

        # Add the file if it is not already in
        with open(repo, 'r') as saved_file_list:
          saved_files = json.load(saved_file_list)

          # Do not repeat scrape for already acquired title
          if not file_details['name'] in saved_files:
            print("Now adding: %s : %s" %(path, file_details['name']))
            filtered_file_list.append(file_details)

    return filtered_file_list


  def get_title_url(self, asset, mediatype):
    # Return the URL corresponding to particular title

    if mediatype == "movie":
      invalid_results = ["(TV Episode)", "(TV Series)", "(TV Mini-Series)", "(Short)", "(Video)"]
      search_url = self.movie_scraper.construct_search_url(asset)
    
    elif mediatype =="series":
      valid_results = ["(TV Series)", "(TV Mini-Series)"]
      search_url = self.series_scraper.construct_search_url(asset)

    page = lxml.html.document_fromstring(requests.get(search_url, headers=HEADERS).content)

    try:
      for index, section in enumerate(page.xpath('//*[@id="main"]/div[1]/div')):
        if len(section.xpath('h3/text()')) > 0:

          # Find the Div associated with Titles (rather than Characters, etc)
          if section.xpath('h3/text()')[0] == "Titles":

            # Select first in list which doesn't contain invalid_results
            for index, list_title in enumerate(page.xpath('//*[@id="main"]/div[1]/div[2]/table[1]/tr')):

              # Movies in list have no tag
              if mediatype == "movie":
                if not any(x in list_title.text_content() for x in invalid_results):
                  endpoint = page.xpath('//*[@id="main"]/div[1]/div[2]/table[1]/tr[%i]/td/a' %(index+1))[0].attrib['href']
                  return self.config["base_url"] + endpoint

              # Series in list are tagged
              elif mediatype == "series":
                if any(x in list_title.text_content() for x in valid_results):

                  # Some items listed as "TV Episode" also contain a link with the term "TV Series" below
                  if "(TV Episode)" not in list_title.text_content():
                    endpoint = page.xpath('//*[@id="main"]/div[1]/div[2]/table[1]/tr[%i]/td/a' %(index+1))[0].attrib['href']
                    return self.config["base_url"] + endpoint

      print(Message.warn("\"{}\" not found. Skipping.".format(asset)))

    except IndexError:
      print(Message.warn("\"{}\" not found. Skipping.".format(asset)))


  def save_image(self, url, name, mediatype):
    # If image_url was found, write image to directory
    try:
      img = requests.get(url, headers=HEADERS, stream=True)
    except:
      return None

    if img.status_code == 200:

      if mediatype == "movie":
        media_dir = "movies"
      
      elif mediatype == "series":
        media_dir = "series"

      try:
      # TODO use relative_path helper function
        with open('_output/images/' + media_dir + '/' + name + '.png', 'wb') as f:
          img.raw.decode_content = True
          shutil.copyfileobj(img.raw, f)
      except:
        pass


  def compile_file_list(self, path, repo, mediatype):
    # path          -> top level directory starting from asset directory in conf file
    #     ex. DoctorWho/
    #
    # relative_path -> complete file path starting at "/"
    #     ex. /Volumes/Media/Series/DoctorWho/
    
    file_attributes_list = []

    for file_details in self.get_file_list(path, repo, mediatype):
      
      media_url = self.get_title_url(file_details['name'], mediatype)

      if mediatype == "movie":
        file_attributes = self.movie_scraper.get_movie_details(file_details, media_url)

      elif mediatype == "series":
        file_attributes = self.series_scraper.get_series_details(file_details, media_url)
        
      if file_attributes != None:
        if mediatype == "movie":
          media_details = video_media_details(file_details['full_path'])
          file_attributes.update(media_details)

        elif mediatype == "series":
          file_attributes['episodes'] = get_nested_directory_contents(
            "{}/{}".format(path, file_details['name']).replace('//', '/')
          )

        self.save_image(file_attributes['image_url'], file_attributes['filename'], mediatype)
        file_attributes['relative_path'] = file_details['relative_path']
        file_attributes_list.append(file_attributes)

    return file_attributes_list


  def write_scraped_data(self, base_path, additional_assets):

    # Import Data from JSON file
    # TODO use relative path helper
    with open(self.config['assets'][base_path]['saved_data'], 'r') as asset_feed:
      saved_assets = json.load(asset_feed)

    if additional_assets != []:

      # Add new saved assets to JSON file
      for asset in additional_assets:
        saved_assets[asset['filename']] = asset

      # Write combined asset contents to JSON file
      # TODO: use relative path helper
      with open(self.config['assets'][base_path]['saved_data'], 'w+') as asset_feed:
        json.dump(saved_assets, asset_feed, encoding="utf-8", indent=4)

    return saved_assets


  def generate_site(self, additional_movies, additional_series):

    try:
      # TODO: use relative path helper
      with open('conf.json') as config_json:
        movie_location = json.load(config_json)['assets']['movies']['location']
    except:
      movie_location = None

    saved_movies  = self.write_scraped_data("movies", additional_movies)
    saved_series  = self.write_scraped_data("series", additional_series)
    num_movies    = len(saved_movies)
    num_series    = len(saved_series)

    # Output Environment for static html generation
    env             = jinja2.Environment(loader=jinja2.FileSystemLoader(["./_templates"]))
    index           = env.get_template("index.html")
    series          = env.get_template("series.html")
    about           = env.get_template("about.html")
    movie_details   = env.get_template("movie_details.html")
    series_details  = env.get_template("series_details.html")


    # Movie Index Page
    movies_page = index.render(movie_list = saved_movies,
                               number_of_series = num_series)
    f = open("_output/index.html", "wb")
    f.write(movies_page.encode('utf-8'))
    f.close

    # TV Series Page
    series_page = series.render(series_list = saved_series,
                                number_of_movies = num_movies)
    j = open("_output/series.html", "wb")
    j.write(series_page.encode('utf-8'))
    j.close

    # About Page
    about_page = about.render(number_of_movies = num_movies,
                              number_of_series = num_series,
                              time = str(datetime.now()))
    g = open("_output/about.html", "wb")
    g.write(about_page.encode('utf-8'))
    g.close

    # Individual Movie Pages
    for item in saved_movies:
      output_dir = "_output/movies/%s(%s).html" %(saved_movies[item]['title'].replace('/', ''), saved_movies[item]['year'])
      movie_page = movie_details.render(number_of_movies = num_movies,
                                        movie = saved_movies[item],
                                        number_of_series = num_series,
                                        location = movie_location)
      h = open(output_dir, "wb")
      h.write(movie_page.encode('utf-8'))
      h.close

    # Individual Series Page
    for item in saved_series:
      output_dir = "_output/series/%s(%s).html" %(saved_series[item]['title'].replace('/', ''), saved_series[item]['year'][0:4])
      series_page = series_details.render(number_of_series = num_series,
                                          series = saved_series[item],
                                          number_of_movies = num_movies)
      k = open(output_dir, "wb")
      k.write(series_page.encode('utf-8'))
      k.close

