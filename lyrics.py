#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup

try:
    token = open("genius_api_key", "r").read()
except IOError:
    token = None
base_url = "https://api.genius.com"
headers = {'Authorization': 'Bearer %s' % token}

def _lyrics_from_song_api_path(song_api_path):
    song_url = base_url + song_api_path
    response = requests.get(song_url, headers=headers)
    json = response.json()
    path = json["response"]["song"]["path"]

    # Regular html scraping...
    page_url = "https://genius.com" + path
    page = requests.get(page_url)
    html = BeautifulSoup(page.text, "html.parser")

    # Remove script tags that they put in the middle of the lyrics
    [h.extract() for h in html('script')]

    return html.find("div", class_="lyrics").get_text()

def get_lyrics(song_title, artist_name):
    """ Return the lyrics for a given song and artist. """

    if not token:
        raise ValueError("Please put your Genius API token in the file 'genius_api_key' and restart in order to fetch lyrics.")

    search_url = base_url + "/search"
    data = {'q': song_title + " " + artist_name}
    response = requests.get(search_url, data=data, headers=headers)
    json = response.json()

    # The first hit is the best?
    if len(json["response"]["hits"]) > 0:
        song_info = json["response"]["hits"][0]
        song_api_path = song_info["result"]["api_path"]
        artist = song_info["result"]["primary_artist"]["name"]
        title = song_info["result"]["title"]
        return artist, title, _lyrics_from_song_api_path(song_api_path).strip()

    return None,None,None
