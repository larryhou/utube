#!/usr/bin/env python3
import utube
import argparse, sys, os, json, re, shutil, io
import os.path as p

def run(command):
    print('+ {}'.format(command))
    return os.system(command)

def download(video_id):
    print('[+] {}'.format(video_id))
    youtube_url = 'https://www.youtube.com/watch?v={}'.format(video_id)
    filename = os.popen('youtube-dl -f 140 --get-filename "{}"'.format(youtube_url)).read() # type: str
    filename = re.sub(r'\.[^.]+$', '', filename)
    if p.exists('{}.mkv'.format(filename)):
        print('~ {}.mkv'.format(filename))
        return
    video_file = '{}.webm'.format(filename)
    if not p.exists(video_file):
        format_map = {}
        format_context = os.popen('youtube-dl -F "{}"'.format(youtube_url)).read() # type: str
        stream = io.StringIO(format_context)
        pattern = re.compile(r'^(\d{,3})\s')
        for line in stream.readlines():
            match = pattern.search(line)
            if not match: continue
            format_map[int(match.group(1))] = line[:-1]
        for code in (313, 271, 248, 247, -1):
            if code == -1: return
            if code not in format_map: continue
            print(format_map.get(code))
            if run('youtube-dl -f {} "{}"'.format(code, youtube_url)) != 0: return
    audio_file = '{}.m4a'.format(filename)
    if not p.exists(audio_file):
        if run('youtube-dl -f 140 "{}"'.format(youtube_url)) != 0:
            return
    run('ffmpeg -i "{}" -i "{}" -c copy -y "{}.mkv"'.format(audio_file, video_file, filename))
    os.remove(audio_file)
    os.remove(video_file)

def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--channel', '-c', nargs='+', required=True)
    arguments.add_argument('--order', '-o', default='rating', choices=('rating', 'date', 'relevance', 'viewCount', 'title'))
    options = arguments.parse_args(sys.argv[1:])
    WORKSPACE = p.abspath(os.getcwd())
    for channel in options.channel:
        channel_path = p.join(WORKSPACE, channel)
        if not p.exists(channel): os.makedirs(channel_path)
        os.chdir(channel_path)
        next_page_token = None
        while True:
            results = utube.query_api_channel_search(channel=channel, fields='nextPageToken,items(id(videoId),snippet(publishedAt, title))', max_result=50, order=options.order, next_page_token=next_page_token) # type: dict
            next_page_token = results.get('nextPageToken')
            items = results.get('items') # type: list
            for it in items:
                print('{}|{}|{}'.format(it['id']['videoId'], it['snippet']['publishedAt'], it['snippet']['title']))
                download(video_id=it['id']['videoId'])
            if not next_page_token: break

if __name__ == '__main__':
    main()
