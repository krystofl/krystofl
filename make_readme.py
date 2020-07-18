#!/usr/bin/env python3
'''
Build README.md, including the latest blog posts
'''

import argparse
import sys
import traceback
import xml.etree.ElementTree as ET

import requests

from eglogging import *
logging_load_human_config()


BLOG_FEED_URL = 'https://krystof.litomisky.com/feed.xml'

# number of blog posts to include in the list
NUM_POSTS = 5


def get_blog_posts() -> str:
  '''
  Return the markdown of the blog posts
  '''
  response = requests.get(BLOG_FEED_URL)
  content  = response.content

  root    = ET.fromstring(content)
  channel = root.find('channel')

  # markdown like [blog post title](url)
  posts = []

  # add the appropriate number of posts
  for post in channel.findall('item'):
    title = post.find('title').text
    url   = post.find('link' ).text

    url_with_utm = '{}?utm_source=krystofl_github'.format(url)

    md = '[{}]({})'.format(title, url_with_utm)
    posts.append(md)

    if len(posts) >= NUM_POSTS:
      break

  ret = "### Latest Blog Posts\n"
  for post in posts:
    ret += "- {}\n".format(post)

  ret += "\nMore at [krystof.litomisky.com]" \
         "(https://krystof.litomisky.com/?utm_source=krystofl_github)\n"

  return ret



def build_readme(args):
  '''
  Build README.md
  '''
  # get the latest blog posts

  # load the template
  with open(args.template, 'r') as fp:
    TEMPLATE = fp.read()

  # add the blog posts
  BLOG_POSTS_MD = get_blog_posts()
  result = TEMPLATE.replace("<!-- BLOG POSTS HERE -->", BLOG_POSTS_MD)

  # save the result
  with open(args.output, 'w') as fp:
    fp.write(result)

  return



def parse_command_line_args():

  parser = argparse.ArgumentParser(description = 'Build README.md')

  parser.add_argument('-o', '--output',
                      default = 'README.md',
                      help = 'File to which to write the results. ' \
                      'README.md by default.')

  parser.add_argument('-t', '--template',
                      default = 'README_TEMPLATE.md',
                      help = 'Template from which to build the output file. ' \
                      'README_TEMPLATE.md by default.')

  args = parser.parse_args()
  return args



if __name__ == '__main__':

    try:
      args   = parse_command_line_args()

      build_readme(args)

    except Exception as ex:
      CRITICAL("Exception: {}".format(ex))
      traceback.print_exc()
      sys.exit(1)
