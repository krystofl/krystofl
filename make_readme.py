#!/usr/bin/env python3
'''
Build README.md, including the latest blog posts
'''

import argparse
import os
import sys
import traceback
import xml.etree.ElementTree as ET

from twython import Twython
import requests

from eglogging import *
logging_load_human_config()


BLOG_FEED_URL = 'https://krystof.litomisky.com/feed.xml'

# number of blog posts to include in the list
NUM_POSTS = 5



class Readme_builder:

  def __init__(self, args):
    # args are from argparse
    self.args = args

    # list of latest Klog posts
    self.klog_posts = []

    # the original README - before this script re-generated it
    self.README_ORIG = ''


  def get_blog_posts(self) -> str:
    '''
    Return the markdown of the blog posts
    '''
    self.klog_posts = []

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

      # add it to the list of posts
      self.klog_posts.append({ "title": title,
                               "url"  : url })

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


  def build_readme(self):
    '''
    Build README.md
    '''
    # store the original README - useful for detecting changes
    with open(self.args.output, 'r') as fp:
      self.README_ORIG = fp.read()

    # load the template
    with open(self.args.template, 'r') as fp:
      TEMPLATE = fp.read()

    # add the blog posts
    BLOG_POSTS_MD = self.get_blog_posts()
    result = TEMPLATE.replace("<!-- BLOG POSTS HERE -->", BLOG_POSTS_MD)

    # save the result
    with open(self.args.output, 'w') as fp:
      fp.write(result)
    return


  def tweet(self):
    '''
    Tweets if a new Klog post was found
    '''
    # check if we are supposed to tweet
    if not self.args.yes_tweet:
      INFO("Not tweeting because --yes_tweet is not set")
      return

    # make sure we found some Klog posts
    if len(self.klog_posts) == 0:
      INFO("No Klog posts found")
      return

    # check if a new tweet was found
    with open(self.args.output, 'r') as fp:
      NEW_README = fp.read()
    if NEW_README == self.README_ORIG:
      INFO("No new posts found - not tweeting")
      return

    # OK - tweet out the latest post
    latest = self.klog_posts[0]
    url = "{}?utm_source=krystofs_twitter_bot".format(latest['url'])
    tweet = "New #blogpost: {}: {}".format(latest['title'], url)

    INFO("Tweet: {}".format(tweet))

    # login to Twitter
    twitter = Twython(os.environ['TWITTER_API_KEY'],
                      os.environ['TWITTER_API_SECRET_KEY'],
                      os.environ['TWITTER_ACCESS_TOKEN'],
                      os.environ['TWITTER_ACCESS_TOKEN_SECRET'])

    # tweet
    twitter.update_status(status = tweet)



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

  parser.add_argument('-y', '--yes_tweet',
                      action = 'store_true',
                      help = 'When set, tweet when a new post is found')

  args = parser.parse_args()
  return args



if __name__ == '__main__':

    try:
      args   = parse_command_line_args()

      # build the README
      builder = Readme_builder(args)
      builder.build_readme()

      # tweet, but only if appropriate
      builder.tweet()

    except Exception as ex:
      CRITICAL("Exception: {}".format(ex))
      traceback.print_exc()
      sys.exit(1)
