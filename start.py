"""
Arguments should be (in order): gamedate (YYYYMMDD) away team abbreviation (e.g. BOS) home team abbreviation (e.g. CLE).

The file team_metadata.csv has two required columns: ABBR and PRIMARY_COLOR (as HTML color code)

The schedule.csv needs to contain the GAMECODE (YYYYMMDD/AWYHOM), first year of the SEASON (2017 for 2017-18) and NBA.com GAME_ID (8 digits or 10 with zero padding)
for each game.

Add the IPs of your Yeelights bulbs in config.py as part of the BULB_IPS list. Make sure that developer mode is activated on the Yeelights.

Brooklyn Nets have a color scheme (black & white) that doesn't work well for this purpose, feel free to tweak the PRIMARY_COLOR. 
Purple is used as the primary color for the San Antonio Spurs.

A future version needs to be able to detect if two team colors are similar to another and switch one of the teams to their SECONDARY_COLOR.

Currently the PBP file is ead fully and once each time the script is started. To support "ambilights" during live games it would be good to have a loop that checks
if new PBP events have been added and react to these instead of parsing the whole file.
"""

import os
import sys
import time
import datetime
import pandas as pd
import requests
import json
import colorsys
import yeelight

from config import PBP_URL, BULB_IPS

def download(url):
    headers = {'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) '
               'AppleWebKit/537.36 (KHTML, like Gecko) '
               'Chrome/50.0.2661.94 Safari/537.36',
               'referer': 'http://stats.nba.com/scores/'}
    try:
        response = requests.get(url, headers=headers)
    except requests.exceptions.ConnectionError:
            return None
    else:
        return response.content.decode("utf-8")


def margin_to_brightness(margin, max_lead=30, pct_pts_base=0):
    """"Tweak max_lead and pct_pts_base to get the desired brightness range"""
    return int((abs(margin) / max_lead) * 100) + pct_pts_base


def control_yeelight(bulbs, color, margin, last_margin):
    if color is None:
        for bulb in bulbs:
            bulb.turn_off()
    else:
        if last_margin == 0:
            for bulb in bulbs:
                bulb.turn_on()
        brightness = margin_to_brightness(margin)
        r, g, b = color_code_to_int(color)
        for bulb in bulbs:
            bulb.set_rgb(r, g, b)
            bulb.set_brightness(brightness)


def color_code_to_int(color):
    color = color.strip("#")
    r = color[:2]
    g = color[2:4]
    b = color[4:6]
    r = int(r, 16)
    g = int(g, 16)
    b = int(b, 16)
    return r, g, b


def get_bulbs():
    return [yeelight.Bulb(ip) for ip in BULB_IPS]


def process_game(g, away, home, delay=1, redownload=False):
    """
    Note: There is currently no explicit API quota handling, but delay can be tweaked to
    mitigate some of the issues. 
    """
    bulbs = get_bulbs()
    for bulb in bulbs:
        bulb.turn_off()
    jpath = "{}.json".format(g["GAME_ID"])
    if redownload is True or not os.path.exists(jpath):
        url = PBP_URL.format(year=g["SEASON"], game_id=str(g["GAME_ID"]).zfill(10))
        data = download(url)
        if data is not None:
            try:
                data = json.loads(data)
            except ValueError:
                print("Error reading play-by-play data")
                exit()
            else:
                with open(jpath, "w") as h:
                    h.write(json.dumps(data))
    with open(jpath, "r") as h:
        data = json.loads(h.read())
    last_margin = 0
    for p, period in enumerate(data["g"]["pd"]):
        pstr = p+1
        for play in period["pla"]:
            s = pd.Series(play)
            s["cl"] = "{}.0".format(s["cl"]) if "." not in s["cl"] else s["cl"]
            clstr = s["cl"][:5]
            margin = s["vs"] - s["hs"]
            s["cl"] = pd.to_datetime(s["cl"], format='%M:%S.%f').time()
            print(pstr, clstr, s["de"], margin, sep="\t")
            if margin > 0:
                color = away["PRIMARY_COLOR"]
            elif margin < 0:
                color = home["PRIMARY_COLOR"]
            else:
                color = None
            if margin != last_margin:
                control_yeelight(bulbs, color, margin, last_margin)
                last_margin = margin
            time.sleep(delay)
        time.sleep(10)
    time.sleep(60)
    for bulb in bulbs:
        bulb.turn_off()


def play(date, away, home):
    schedule = pd.read_csv("schedule.csv", index_col=0)
    team_data = pd.read_csv("team_metadata.csv", index_col=0)
    dstr = str(date).replace("-", "")
    try:
        g = schedule.loc["{}/{}{}".format(dstr, away, home)]
    except KeyError:
        print("Game not found")
    else:
        a = team_data.loc[away]
        h = team_data.loc[home]
        process_game(g, a, h)

def main(args):
    if args:
        play(args[0], args[1], args[2])
    else:
        print("Required arguments: date away home")

if __name__ == '__main__':
    args = sys.argv[1:]
    main(args)
