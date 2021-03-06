#!/usr/bin/env python3

import requests, json, argparse, sys, re, urllib, enum, io, tqdm, math, shutil, os, time
from typing import Tuple,List,Dict

YOUTUBE_API_KEY = 'AIzaSyCyLSmcEDJt3HaLFK0_LdJYPkq0RFAVzKA'
CHANNEL_SETTING = [
    'UCQT2Ai7hQMnnvVTGd6GdrOQ',
    'UCO3pO3ykAUybrjv3RBbXEHw',
    'UCkWfzJTG5j-V8gTJQgEOexA',
    'UCdRKafyb--geO9ySg6CbhYA',
    'UCtAIPjABiQD3qjlEl1T5VpA'
]

safari_browser_headers = {
    'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Safari/605.1.15',
    'Accept-Language':'en-us',
    'Connection':'keep-alive'
}

class commands(object):
    download = 'download'
    check = 'check'
    download_channel = 'download-channel'
    check_channel = 'check-channel'
    download_list = 'download-list'
    check_list = 'check-list'

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
        self.max_result = data.max_result # type: int
        self.channel_index = data.channel_index # type: int
        self.output_path = data.output_path # type: str
        self.verbose = data.verbose # type: bool
        self.playlist = data.playlist # type: str

class CurrencyFormatter(object):
    def __init__(self, length:int = 10, align_right:bool = True):
        self.formatter = '{{:{}{}s}}'.format('>' if align_right else '<',length)

    def format(self, value:int):
        return self.formatter.format('{:,}'.format(value))

class BitrateFormatter(object):
    def __init__(self, length:int = 10, align_right:bool = True):
        self.formatter = '{{:{}{}}}Kb/s'.format('>' if align_right else '<',length)

    def format(self, value:int):
        return self.formatter.format(value//1024)

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
        field_name_list = [('itag', '{:>3d}'), ('file_type', '{:10s}'), ('quality', '{:>7s}'), ('resolution', '{:9s}'), ('fps', '{:2d}'),
                           ('bitrate', BitrateFormatter(8, True)),('codecs', '{:11s}'), ('length', CurrencyFormatter(12))]  # type: List[Tuple[str, str]]
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
    return response.json()

def query_api_channel_search(channel:str, part:str = 'snippet', fields:str = None, max_result:int = 50, order:str = 'date', next_page_token:str = None):
    params = {
        'channelId': channel,
        'part': part,
        'maxResults':max_result,
        'order': order,
        'safeSearch':'none',
        'type':'video',
        'key': YOUTUBE_API_KEY
    }
    if next_page_token: params['pageToken'] = next_page_token
    if fields: params['fields'] = fields
    response = requests.get('https://www.googleapis.com/youtube/v3/search', params=params)
    assert response.status_code == 200, tojson(response.json())
    return response.json()
    # print(tojson(response.json()))

def query_api_playlist(channel:str, part:str = 'snippet,contentDetails,status', max_result:int = 50):
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

def query_api_playlist_items(id, part = 'snippet,contentDetails', fields:str = None, max_result = 10):
    params = {
        'playlistId': id,
        'part': part,
        'maxResults':max_result,
        'key': YOUTUBE_API_KEY
    }
    if fields: params['fields'] = fields
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

def decode_player_api(content:bytes)->Dict:
    keyword = b'ytplayer.config'
    keyword_length = len(keyword)
    content_length = len(content)
    for n in range(content_length):
        char = content[n]
        if char == keyword[0]:
            match = content[n:n+keyword_length]
            if keyword[-1] == match[-1] and keyword == match:
                n += keyword_length
                api_data_available = False
                for m in range(n, content_length):
                    char = content[m]
                    if char == 123: # '{'
                        api_data_available = content[n:m].strip() == b'='
                        break
                if api_data_available: break
    if 0 < n < content_length:
        offset = n
        balance, position = -1, 0
        for i in range(n, content_length):
            char = content[i]
            if char == 123: # '{'
                if balance == -1: offset, balance = i, 0
                balance += 1
            if char == 125: # '}'
                balance -= 1
            if balance == 0:
                position = i + 1
                break
        data = json.loads(content[offset:position]) # type: dict
        return data.get('args')
    return {}

def decode_media_assets(movie_id:str, movie_info:Dict = None)->Dict[int, MediaAsset]:
    dont_retry = False
    if not movie_info:
        params = decode_parameters('el=embedded&ps=default&gl=US&hl=en')
        params['video_id'] = movie_id
        watch_headers = safari_browser_headers.copy()
        watch_headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        watch_headers['Accept-Encoding'] = 'br, gzip, deflate'
        response = requests.get('https://www.youtube.com/get_video_info', params=params, headers=watch_headers)
        movie_info = decode_parameters(response.text)
    else:
        dont_retry = True
    title = movie_info.get('title')
    asset_map = {} # type: Dict[int, MediaAsset]
    adaptive_fmts = movie_info.get('adaptive_fmts')
    if adaptive_fmts:
        for item in adaptive_fmts.split(','):
            download_info = decode_parameters(item)
            if not download_info: continue
            media = decode_media_1(download_info)
            media.title = title
            asset_map[media.itag] = media
            if options.verbose: print(media)
    url_encoded_fmts = movie_info.get('url_encoded_fmt_stream_map')
    if url_encoded_fmts:
        for item in url_encoded_fmts.split(','):
            download_info = decode_parameters(item)
            if not download_info: continue
            media = decode_media_2(download_info)
            asset_map[media.itag] = media
            media.title = title
            if options.verbose: print(media)
    else:
        if dont_retry: return {}
        response = requests.get(url='https://www.youtube.com/watch?v={}'.format(movie_id), headers=safari_browser_headers)
        if response.status_code != 200:
            print(response.text)
            return
        timestamp = time.clock()
        api_data = decode_player_api(response.content)
        if options.verbose: print('decode_player_api {:.3f}s'.format(time.clock() - timestamp))
        return decode_media_assets(movie_id, movie_info=api_data)
    return asset_map

def check_movie(movie_id:str):
    for tag, media in decode_media_assets(movie_id).items():
        if not options.verbose: print(media)

def check_channel(channel:str):
    result = query_api_channel_search(channel=channel, max_result=options.max_result,
                                      fields='items(snippet(title,publishedAt),id(videoId))',
                                      part='snippet,id')
    for item in result.get('items'):
        snippet = item['snippet']
        title = snippet['title']
        print('[%s]' % re.sub(r'\.\d+Z$', '', snippet['publishedAt']),
              'https://www.youtube.com/watch?v=%s' % item['id']['videoId'], title)

def check_list(list_id:str):
    result = query_api_playlist_items(id=list_id,
                                      max_result=options.max_result,
                                      fields='items(snippet(title,publishedAt),contentDetails(videoId))',
                                      part='snippet,contentDetails')
    for item in result.get('items'):
        snippet = item['snippet']
        title = snippet['title']
        print('[%s]' % re.sub(r'\.\d+Z$', '', snippet['publishedAt']),
              'https://www.youtube.com/watch?v=%s' % item['contentDetails']['videoId'], title)

def download_list(list_id:str):
    playlist_info = query_api_playlist_items(id=list_id,
                                             max_result=options.max_result,
                                             part='contentDetails',
                                             fields='items(contentDetails(videoId))')
    for item in playlist_info.get('items'):  # type: dict
        download_movie(movie_id=item['contentDetails']['videoId'])

def download_movie(movie_id:str):
    asset_map = decode_media_assets(movie_id)
    if options.tag not in asset_map:
        print('tag={} not found in {!r}'.format(options.tag, list(asset_map.keys())))
        return
    media = asset_map.get(options.tag)
    download(url=media.url, file_name=media.file_name)

def download(url:str, file_name:str):
    print(file_name, url)
    file_name = re.sub(r'[()]', '', re.sub(r'[/|]', '-', file_name))
    response = requests.get(url, stream=True, headers=safari_browser_headers)
    total = parse_int(response.headers.get('content-length'))
    block, wrote = 1024, 0
    if options.output_path:
        if not os.path.exists(options.output_path):
            os.makedirs(options.output_path)
        download_file_path = os.path.join(options.output_path, file_name)
    else:
        download_file_path = file_name
    if os.path.exists(download_file_path): return
    temp_file_path = '{}.dl'.format(download_file_path)
    with open(temp_file_path, 'wb') as fp:
        progress = tqdm.tqdm(total=math.ceil(total), unit='B', unit_scale=True)
        for data in response.iter_content(block):
            if not data: continue
            progress.update(len(data))
            wrote = wrote + len(data)
            fp.write(data)
        if fp.tell() == 0:
            fp.close()
            os.remove(fp.name)
        progress.close()
    if total != 0:
        if wrote != total:
            print("download failed")
        else:
            shutil.move(temp_file_path, download_file_path)

def download_channel(channel):
    description_printed = False
    result = query_api_channel_search(channel=channel, max_result=options.max_result)
    for item in result.get('items'):
        snippet = item['snippet']
        title = snippet['title']
        if not description_printed:
            description_printed = True
            print('%s[%s]'%(snippet['channelId'], snippet['channelTitle']))
        print('[%s]'%re.sub(r'\.\d+Z$', '', snippet['publishedAt']), 'https://www.youtube.com/watch?v=%s'%item['id']['videoId'], title)
        download_movie(movie_id=item['id']['videoId'])

def get_movie_id(url:str)->str:
    return decode_parameters(url.split('?')[-1]).get('v')

if __name__ == '__main__':
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--command', '-c', choices=commands.option_choices(), help='command')
    arguments.add_argument('--tag', '-t', type=int, help='Youtube media tag, you can get tag list $ ./utube.py -c check --url xxx')
    arguments.add_argument('--channel', '-l', default='UCQT2Ai7hQMnnvVTGd6GdrOQ', help='Youtube channel id')
    arguments.add_argument('--max-result', '-m', default=20, type=int, help='max search result')
    arguments.add_argument('--channel-index', '-i', type=int, choices=range(len(CHANNEL_SETTING)))
    arguments.add_argument('--url', '-u', help='Youtube video page url')
    arguments.add_argument('--output-path', '-o', help='used for downloaded videos')
    arguments.add_argument('--verbose', '-v', action='store_true', help='verbose print')
    arguments.add_argument('--playlist', '-p', help='Youtube playlist id')
    global options
    options = ArgumentOptions(data=arguments.parse_args(sys.argv[1:]))
    target_channel = options.channel
    if options.channel_index is not None:
        target_channel = CHANNEL_SETTING[options.channel_index]
    if options.command == commands.download_channel:
        assert target_channel
        assert options.tag
        download_channel(channel=target_channel)
    elif options.command == commands.download:
        assert options.url
        assert options.tag
        download_movie(get_movie_id(options.url))
    elif options.command == commands.check:
        assert options.url
        check_movie(get_movie_id(options.url))
    elif options.command == commands.check_channel:
        assert target_channel
        check_channel(target_channel)
    elif options.command == commands.check_list:
        assert options.playlist
        check_list(list_id=options.playlist)
    elif options.command == commands.download_list:
        assert options.playlist
        download_list(list_id=options.playlist)
