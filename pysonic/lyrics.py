#!/usr/bin/env python3

import os
from typing import Optional

import requests
from bs4 import BeautifulSoup

base_url = "https://api.genius.com"


def get_token() -> Optional[str]:
    user_home_path = os.path.abspath(os.path.join(os.path.expanduser("~"), ".pysonic/"))

    try:
        with open(os.path.join(user_home_path, "genius_api_key"), "r") as token_file:
            token = token_file.read()
    except (IOError, FileNotFoundError):
        token = input("Please enter your Genius API token to use this feature (or press enter to cancel): ").strip()
        if not token:
            return None
        with open(os.path.join(user_home_path, "genius_api_key"), "w") as token_file:
            token_file.write(token)

    return token


def _lyrics_from_song_api_path(song_api_path):
    song_url = base_url + song_api_path
    response = requests.get(song_url, headers={'Authorization': f'Bearer {get_token()}'})
    json = response.json()
    path = json["response"]["song"]["path"]

    # Regular html scraping...
    page_url = "https://genius.com" + path
    page = requests.get(page_url)
    html = BeautifulSoup(page.text, "html.parser")

    # Remove script tags that they put in the middle of the lyrics
    [h.extract() for h in html('script')]

    divs = html.findAll("div")
    lyrics = ''
    for div in divs:
        classes = div.get('class')
        if classes:
            for one_class in classes:
                if one_class.startswith('Lyrics__Container'):
                    lyrics += div.get_text(separator="\n")
    if lyrics:
        return lyrics

    return 'Got a song response, but didn\'t find any lyircs.'


def get_lyrics(song_title, artist_name):
    """ Return the lyrics for a given song and artist. """

    search_url = base_url + "/search"
    data = {'q': song_title + " " + artist_name}
    token = get_token()
    if not token:
        return None, None, None
    response = requests.get(search_url, params=data, headers={'Authorization': f'Bearer {token}'})
    json = response.json()

    # The first hit is the best?
    if len(json["response"]["hits"]) > 0:
        song_info = json["response"]["hits"][0]
        song_api_path = song_info["result"]["api_path"]
        artist = song_info["result"]["primary_artist"]["name"]
        title = song_info["result"]["title"]
        return artist, title, _lyrics_from_song_api_path(song_api_path).strip()

    return None, None, None
