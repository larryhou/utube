#!/usr/bin/env python3
import utube
import argparse, sys, os, json, re, shutil
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
    audio_file = '{}.m4a'.format(filename)
    if not p.exists(audio_file):
        if run('youtube-dl -f 140 "{}"'.format(youtube_url)) != 0:
            return
    video_file = '{}.webm'.format(filename)
    if not p.exists(video_file):
        if run('youtube-dl -f 313 "{}"'.format(youtube_url)) != 0:
            if run('youtube-dl -f 248 "{}"'.format(youtube_url)) != 0:
                if run('youtube-dl -f 247 "{}"'.format(youtube_url)) != 0:
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
            results = utube.query_api_channel_search(channel=channel, fields='nextPageToken,items(id(videoId))', max_result=50, order=options.order, next_page_token=next_page_token) # type: dict
            next_page_token = results.get('nextPageToken')
            items = results.get('items') # type: list
            for it in items: download(video_id=it['id']['videoId'])
            if not next_page_token: break

if __name__ == '__main__':
    main()
