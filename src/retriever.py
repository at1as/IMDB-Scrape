#!/usr/bin/env python
# -*- coding: utf8 -*-

from   __future__ import unicode_literals
from   datetime import datetime
from   helpers import HEADERS, verify_config_file
import jinja2
import json
import lxml.html
from   message import Message
import os
import requests
import pdb
import scraper
import pymediainfo
import shutil
import sys
import time
from   unicodedata import normalize
import urllib

config = None


class Retriever():

  @staticmethod
  def start():
    main()


def initialize_asset_repo(base_path, mediatype):
  # Create empty datafiles if not present

  if not os.path.isfile(config['assets'][base_path]['saved_data']):
    with open(config['assets'][base_path]['saved_data'], 'w+') as item_feed:
      json.dump({}, item_feed)

  if config['assets'][base_path]['index_asset']:
    item_list = compile_file_list(
      config['assets'][base_path]['location'],
      config['assets'][base_path]['saved_data'],
      mediatype
    )
  else:
    item_list = []

  return item_list


def get_file_list(path, repo, mediatype):
  asset_type = "movies" if mediatype == "movie" else mediatype

  try:
    # Enforce per asset type limit
    if not config["assets"][asset_type]["max_assets"] == 0:
      file_list = os.listdir(path)[0:config["assets"][asset_type]["max_assets"]]
    else:
      file_list = os.listdir(path)
  except OSError:
    print "\nError: Path \"%s\" not found. Specify a valid path in conf.json and ensure all directories on this path exist.\n" % path
    raise SystemExit

  filtered_file_list = []

  for file in file_list:

    # If the extension is in include_extension, or file is a folder not preceded by '_'
    if ((os.path.isfile(path + file) and file.split(".")[-1:][0].lower() in config["include_extensions"]) or (os.path.isdir(path + file) and file[0] != "_")) and file not in config["exclude_files"]:

      # Strip extension from file
      if os.path.isfile(path + file):
        file_details = {'name': file.rsplit(".", 1)[0], 'extension': file.rsplit('.', 1)[1]}
      else:
        file_details = {'name': file, 'extension': None}

      # Drop prepending "._" from files on external drives
      if file_details['name'][0:2] == "._":
        file_details['name'] = file_details['name'][2:]

      # Add the file if it is not already in
      with open(repo, 'r') as saved_file_list:
        saved_files = json.load(saved_file_list)

        # Do not repeat scrape for already acquired title
        if not saved_files.has_key(file_details['name']):
          print "Now adding: %s : %s" %(path, file_details['name'])
          filtered_file_list.append(file_details)

  return filtered_file_list


def construct_search_url(title):
  # Construct search results url for specified title

  safe_title = normalize("NFC", title).replace(" ", "+").replace("&", "%26").replace("?", "%3F").lower()
  return config["base_url"] + config["search_path"] + safe_title + config["url_end"]


def get_title_url(asset, mediatype):
  # Return the URL corresponding to particular title

  if mediatype == "movie":
    invalid_results = ["(TV Episode)", "(TV Series)", "(TV Mini-Series)", "(Short)", "(Video)"]
  
  elif mediatype =="series":
    valid_results = ["(TV Series)", "(TV Mini-Series)"]

  search_url = construct_search_url(asset)
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
                return config["base_url"] + endpoint

            # Series in list are tagged
            elif mediatype == "series":
              if any(x in list_title.text_content() for x in valid_results):

                # Some items listed as "TV Episode" also contain a link with the term "TV Series" below
                if "(TV Episode)" not in list_title.text_content():
                  endpoint = page.xpath('//*[@id="main"]/div[1]/div[2]/table[1]/tr[%i]/td/a' %(index+1))[0].attrib['href']
                  return config["base_url"] + endpoint

    print Message.warn("\"{}\" not found. Skipping.".format(asset))
  except IndexError:
    print Message.warn("\"{}\" not found. Skipping.".format(asset))


def save_image(url, name, mediatype):
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

    with open('_output/images/' + media_dir + '/' + name + '.png', 'wb') as f:
      img.raw.decode_content = True
      shutil.copyfileobj(img.raw, f)


def compile_file_list(path, repo, mediatype):
  file_attributes_list = []

  for file_details in get_file_list(path, repo, mediatype):

    if mediatype == "movie":
      movie_url = get_title_url(file_details['name'], "movie")
      file_attributes = scraper.get_movie_details(file_details, "movie", movie_url)

    elif mediatype == "series":
      series_url = get_title_url(file_details['name'], "series")
      file_attributes = scraper.get_series_details(file_details, "series", series_url)

    if file_attributes != None:
      file_attributes_list.append(file_attributes)

  return file_attributes_list


def write_scraped_data(base_path, additional_assets):

  # Import Data from JSON file
  with open(config['assets'][base_path]['saved_data'], 'r') as asset_feed:
    saved_assets = json.load(asset_feed)

  if additional_assets != []:

    # Add new saved assets to JSON file
    for asset in additional_assets:
      saved_assets[asset['filename']] = asset

    # Write combined asset contents to JSON file
    with open(config['assets'][base_path]['saved_data'], 'w+') as asset_feed:
      json.dump(saved_assets, asset_feed, encoding="utf-8", indent=4)

  return saved_assets


def generate_site(additional_movies, additional_series):

  try:
    with open('conf.json') as config_json:
      movie_location = json.load(config_json)['assets']['movies']['location']
  except:
    movie_location = None

  saved_movies  = write_scraped_data("movies", additional_movies)
  saved_series  = write_scraped_data("series", additional_series)
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
  f = open("_output/index.html", "w")
  f.write(movies_page.encode('utf-8'))
  f.close

  # TV Series Page
  series_page = series.render(series_list = saved_series,
                              number_of_movies = num_movies)
  j = open("_output/series.html", "w")
  j.write(series_page.encode('utf-8'))
  j.close

  # About Page
  about_page = about.render(number_of_movies = num_movies,
                            number_of_series = num_series,
                            time = str(datetime.now()))
  g = open("_output/about.html", "w")
  g.write(about_page.encode('utf-8'))
  g.close

  # Individual Movie Pages
  for item in saved_movies:
    output_dir = "_output/movies/%s(%s).html" %(saved_movies[item]['title'].replace('/', ''), saved_movies[item]['year'])
    movie_page = movie_details.render(number_of_movies = num_movies,
                                      movie = saved_movies[item],
                                      number_of_series = num_series,
                                      location = movie_location)
    h = open(output_dir, "w")
    h.write(movie_page.encode('utf-8'))
    h.close

  # Individual Series Page
  for item in saved_series:
    output_dir = "_output/series/%s(%s).html" %(saved_series[item]['title'].replace('/', ''), saved_series[item]['year'][0:4])
    series_page = series_details.render(number_of_series = num_series,
                                        series = saved_series[item],
                                        number_of_movies = num_movies)
    k = open(output_dir, "w")
    k.write(series_page.encode('utf-8'))
    k.close


def main():
  script_started = datetime.now()

  # TODO: refactor above methods into class and purge this global
  global config
  config = verify_config_file()
  
  movie_list  = initialize_asset_repo("movies", "movie")
  series_list = initialize_asset_repo("series", "series")
  generate_site(movie_list, series_list)

  Message.success("Script completed after {} seconds\n".format((datetime.now() - script_started).seconds))