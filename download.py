#!/usr/bin/env python3

import crawl

if __name__ == '__main__':
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--video-id', '-i', nargs='+', required=True)
    options = arguments.parse_args(sys.argv[1:])
    for video_id in options.video_id:
        crawl.download(video_id)
