#!/usr/bin/env python3

import requests, json, argparse, sys, time, re, urllib, enum, io, tqdm, math, shutil, os
from typing import Tuple,List,Dict

YOUTUBE_API_KEY = 'AIzaSyCyLSmcEDJt3HaLFK0_LdJYPkq0RFAVzKA'
CHANNEL_SETTING = [
    'UCQT2Ai7hQMnnvVTGd6GdrOQ',
    'UCO3pO3ykAUybrjv3RBbXEHw',
    'UCkWfzJTG5j-V8gTJQgEOexA',
    'UCdRKafyb--geO9ySg6CbhYA',
    'UCtAIPjABiQD3qjlEl1T5VpA'
]

class commands(object):
    check_movie = 'check-movie'
    check_channel = 'check-channel'
    download_movie = 'download-movie'
    download_channel = 'download-channel'

    @classmethod
    def option_choices(cls):
        choice_list = []
        for name, value in vars(cls).items():
            if name.replace('_', '-') == value: choice_list.append(value)
        return choice_list

class MediaType(enum.Enum):
    UNKNOWN, VIDEO, AUDIO, MOVIE = range(4)

class ArgumentOptions(object):
    def __init__(self, data):
        self.command = data.command # type: str
        self.tag = data.tag # type: int
        self.url = data.url  # type: str
        self.channel = data.channel # type: str
        self.time_span = data.time_span # type: int
        self.time_unit = data.time_unit # type: str
        self.max_result = data.max_result # type: int
        self.channel_index = data.channel_index # type: int
        self.download_path = data.download_path # type: str

class CurrencyFormatter(object):
    def __init__(self, length:int = 10, align_right:bool = True):
        self.formatter = '{{:{}{}s}}'.format('>' if align_right else '<',length)

    def format(self, value:int):
        return self.formatter.format('{:,}'.format(value))

class MediaAsset(object):
    def __init__(self):
        self.itag = None # type: int
        self.type = MediaType.UNKNOWN # type: MediaType
        self.file_type = None # type: str
        self.length = 0 # type: int
        self.bitrate = 0 # type: int
        self.codecs = None # type: List[str]
        self.url = None # type: str
        self.extension = None # type: str
        self.resolution = None # type: str
        self.fps = None # type: str
        self.quality = None # type: str
        self.title = None # type: str

    @property
    def file_name(self):
        return '{}.{}'.format(self.title, self.extension)

    def __repr__(self):
        field_name_list = [('itag', '{:>3d}'), ('file_type', '{:10s}'), ('quality', '{:>6s}'), ('resolution', '{:9s}'), ('fps', '{:2d}'),
                           ('codecs', '{:11s}'), ('length', CurrencyFormatter(12))]  # type: List[Tuple[str, str]]
        data = io.StringIO()
        for field_name, formatter in field_name_list:
            value = self.__getattribute__(field_name)
            if not value: continue
            if isinstance(value, list):
                column_data = '|'.join([formatter.format(x) for x in value])
            else:
                column_data = formatter.format(value)
            if not column_data.strip(): continue
            data.write(column_data)
            data.write('  ')
        data.seek(0)
        return data.read()

def tojson(data):
    return json.dumps(data, ensure_ascii=False, indent=4)

def parse_multiple_param(value):
    if isinstance(value, tuple) or isinstance(value, list):
        return ','.join([str(x) for x in value])
    return value

def query_api_channel(id, part = 'snippet,contentDetails,statistics'):
    params = {
        'id':id,
        'part':part,
        'key':YOUTUBE_API_KEY
    }
    response = requests.get('https://www.googleapis.com/youtube/v3/channels', params=params)
    assert response.status_code == 200, tojson(response.json())
    print(tojson(response.json()))

def query_api_video(id, part = 'snippet,contentDetails,statistics'):
    params = {
        'id': id,
        'part': part,
        'key': YOUTUBE_API_KEY
    }
    response = requests.get('https://www.googleapis.com/youtube/v3/videos', params=params)
    assert response.status_code == 200, tojson(response.json())
    print(tojson(response.json()))

def query_api_search(channel, part = 'snippet', max_result = 50):
    params = {
        'channelId': channel,
        'part': part,
        'maxResults':max_result,
        'order':'date',
        'safeSearch':'none',
        'type':'video',
        'key': YOUTUBE_API_KEY
    }
    response = requests.get('https://www.googleapis.com/youtube/v3/search', params=params)
    assert response.status_code == 200, tojson(response.json())
    return response.json()
    # print(tojson(response.json()))

def query_api_playlist(channel, part = 'snippet,contentDetails,status', max_result = 50):
    params = {
        'channelId': channel,
        'part': part,
        'maxResults':max_result,
        'key': YOUTUBE_API_KEY
    }
    response = requests.get('https://www.googleapis.com/youtube/v3/playlists', params=params)
    assert response.status_code == 200, tojson(response.json())
    return response.json()
    # print(tojson(response.json()))

def query_api_playlist_items(id, part = 'snippet,contentDetails', max_result = 10):
    params = {
        'playlistId': id,
        'part': part,
        'maxResults':max_result,
        'key': YOUTUBE_API_KEY
    }
    response = requests.get('https://www.googleapis.com/youtube/v3/playlistItems', params=params)
    assert response.status_code == 200, tojson(response.json())
    return response.json()
    # print(tojson(response.json()))

def query_api_category(region_code, part = 'snippet'):
    params = {
        'regionCode': region_code,
        'part': part,
        'key': YOUTUBE_API_KEY
    }
    response = requests.get('https://www.googleapis.com/youtube/v3/videoCategories', params=params)
    assert response.status_code == 200, tojson(response.json())
    print(tojson(response.json()))

def decode_parameters(query_string:str):
    result = {}
    for param in query_string.split('&'):
        kvpair = param.split('=')
        if len(kvpair) == 2:
            result[kvpair[0]] = urllib.request.unquote(kvpair[1])
    return result

def parse_codecs(value:str)->Tuple[str, List[str]]:
    file_type, codecs_data = tuple(value.split(';')) # type: str, str
    codecs_list = [re.sub(r'^\+', '', x) for x in codecs_data.split('=')[-1][1:-1].split(',')]
    return  file_type, codecs_list

def parse_int(value:str):
    return int(value) if value else 0

def decode_media_1(data:Dict)->MediaAsset:
    media = MediaAsset()
    media.url = data.get('url')
    media.length = parse_int(data.get('clen'))
    media.bitrate = parse_int(data.get('bitrate'))
    media.itag = parse_int(data.get('itag'))
    media.file_type, media.codecs = parse_codecs(data.get('type'))
    media.fps = parse_int(data.get('fps'))
    media.resolution = data.get('size')
    media.quality = data.get('quality_label')
    if media.file_type.startswith('video'):
        media.type = MediaType.VIDEO if len(media.codecs) <= 1 else MediaType.MOVIE
    else:
        media.type = MediaType.AUDIO
    media.extension = media.file_type.split('/')[-1]
    return media

def decode_media_2(data:Dict):
    media = MediaAsset()
    media.url = data.get('url')
    media.itag = parse_int(data.get('itag'))
    media.quality = data.get('quality')
    media.file_type, media.codecs = parse_codecs(data.get('type'))
    if media.file_type.startswith('video'):
        media.type = MediaType.VIDEO if len(media.codecs) <= 1 else MediaType.MOVIE
    else:
        media.type = MediaType.AUDIO
    media.extension = media.file_type.split('/')[-1]
    return media

def decode_media_assets(movie_id:str)->Dict[int, MediaAsset]:
    params = decode_parameters('el=embedded&ps=default&eurl=&gl=US&hl=en')
    params['video_id'] = movie_id
    response = requests.get('https://www.youtube.com/get_video_info', params=params)
    movie_info = decode_parameters(response.text)
    title = movie_info.get('title')
    asset_map = {} # type: Dict[int, MediaAsset]
    for item in movie_info.get('adaptive_fmts').split(','):
        download_info = decode_parameters(item)
        media = decode_media_1(download_info)
        media.title = title
        asset_map[media.itag] = media
        print(media)
    for item in movie_info.get('url_encoded_fmt_stream_map').split(','):
        download_info = decode_parameters(item)
        media = decode_media_2(download_info)
        asset_map[media.itag] = media
        media.title = title
        print(media)
    return asset_map

def check_movie(movie_id:str):
    decode_media_assets(movie_id)

def check_channel(channel:str):
    description_printed = False
    result = query_api_search(channel=channel, max_result=options.max_result)
    for item in result.get('items'):
        snippet = item['snippet']
        title = snippet['title']
        if not description_printed:
            description_printed = True
            print('%s[%s]' % (snippet['channelId'], snippet['channelTitle']))
        print('[%s]' % re.sub(r'\.\d+Z$', '', snippet['publishedAt']),
              'https://www.youtube.com/watch?v=%s' % item['id']['videoId'], title)

def download_movie(movie_id:str):
    asset_map = decode_media_assets(movie_id)
    if options.tag not in asset_map:
        print('tag={} not found in {!r}'.format(options.tag, list(asset_map.keys())))
        return
    media = asset_map.get(options.tag)
    download(url=media.url, file_name=media.file_name)

def download(url:str, file_name:str):
    print(file_name, url)
    response = requests.get(url, stream=True)
    total = parse_int(response.headers.get('content-length'))
    block, wrote = 1024, 0
    if options.download_path:
        if not os.path.exists(options.download_path):
            os.makedirs(options.download_path)
        download_file_path = os.path.join(options.download_path, file_name)
    else:
        download_file_path = file_name
    if os.path.exists(download_file_path): return
    temp_file_path = '{}.dl'.format(download_file_path)
    with open(temp_file_path, 'wb') as fp:
        for data in tqdm.tqdm(response.iter_content(block),
                              total=math.ceil(total // block), unit='KB', unit_scale=True):
            wrote = wrote + len(data)
            fp.write(data)
    if total != 0 and wrote != total:
        print("download failed")
    else:
        shutil.move(temp_file_path, download_file_path)

def download_channel(channel):
    description_printed = False
    result = query_api_search(channel=channel, max_result=options.max_result)
    for item in result.get('items'):
        snippet = item['snippet']
        title = snippet['title']
        if not description_printed:
            description_printed = True
            print('%s[%s]'%(snippet['channelId'], snippet['channelTitle']))
        print('[%s]'%re.sub(r'\.\d+Z$', '', snippet['publishedAt']), 'https://www.youtube.com/watch?v=%s'%item['id']['videoId'], title)
        download_movie(movie_id=item['id']['videoId'])

def query_recent_videos(channel, time_span, max_result):
    start_time = time.localtime(time.mktime(time.localtime()) - time_span)
    video_list = []
    for playlist in query_api_playlist(channel=channel).get('items'):
        playlist_id = playlist.get('id')
        print('[PLAY]', playlist_id, playlist['snippet']['title'])
        playlist_list = query_api_playlist_items(id=playlist_id, max_result=max_result).get('items')
        playlist_list.sort(cmp=lambda a, b: -1 if a['contentDetails'].get('videoPublishedAt') > b['contentDetails'].get('videoPublishedAt') else 1)
        for item in playlist_list:
            detail = item.get('contentDetails')
            if 'videoPublishedAt' not in detail: continue
            title = item['snippet']['title']
            print('    [VIDEO]', detail['videoPublishedAt'], detail['videoId'], title)
            time_string = re.sub(r'\.\d+Z$','', detail.get('videoPublishedAt'))
            publish_time = time.strptime(time_string, '%Y-%m-%dT%H:%M:%S')
            if publish_time >= start_time:
                video_item = (detail.get('videoId'), publish_time, title)
                video_list.append(video_item)
    from operator import itemgetter
    video_list.sort(key=itemgetter(1), reverse=True)
    for n in range(len(video_list)):
        video_item = video_list[n]
        print(time.strftime('[%Y-%m-%d %H:%M:%S]', video_item[1]), 'https://www.youtube.com/watch?v=%s'%video_item[0], '\'%s\''%(video_item[-1]))

def parse_time_span(value, unit):
    if unit == 's':return int(value)
    if unit == 'm':return int(value) * 60
    if unit == 'h':return int(value) * 3600
    if unit == 'd':return int(value) * 3600 * 24
    return int(value)

def get_movie_id(url:str)->str:
    return decode_parameters(url.split('?')[-1]).get('v')

if __name__ == '__main__':
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--command', '-c', choices=commands.option_choices(), help='command')
    arguments.add_argument('--tag', '-t', type=int, help='Youtube media tag, you can get tag list $ ./utube.py -c check-movie --url xxx')
    arguments.add_argument('--channel', '-l', default='UCQT2Ai7hQMnnvVTGd6GdrOQ', help='Youtube channel id')
    arguments.add_argument('--time-span', '-s', default=7, type=int, help='time span')
    arguments.add_argument('--time-unit', '-n', default='d', choices=['s', 'm', 'h', 'd'], help='s:second m:minute h:hour d:day')
    arguments.add_argument('--max-result', '-m', default=20, type=int, help='max search result')
    arguments.add_argument('--channel-index', '-i', type=int, choices=range(len(CHANNEL_SETTING)))
    arguments.add_argument('--url', '-u', help='Youtube video page url')
    arguments.add_argument('--download-path', '-d', help='used for downloaded videos')
    global options
    options = ArgumentOptions(data=arguments.parse_args(sys.argv[1:]))
    target_channel = options.channel
    if options.channel_index is not None:
        target_channel = CHANNEL_SETTING[options.channel_index]
    if options.command == commands.download_channel:
        assert target_channel
        assert options.tag
        download_channel(channel=target_channel)
    elif options.command == commands.download_movie:
        assert options.url
        assert options.tag
        download_movie(get_movie_id(options.url))
    elif options.command == commands.check_movie:
        assert options.url
        check_movie(get_movie_id(options.url))
    elif options.command == commands.check_channel:
        assert target_channel
        check_channel(target_channel)