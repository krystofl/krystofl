#!/usr/bin/env python3
'''
Build README.md, including the latest blog posts
'''

import argparse
import os
import sys
import traceback
import xml.etree.ElementTree as ET

from html.parser import HTMLParser

from twython import Twython
import requests

from eglogging import *
logging_load_human_config()


BLOG_BASE_URL = 'https://krystof.litomisky.com'
BLOG_FEED_URL = 'https://krystof.litomisky.com/feed.xml'
BLOG_TAGS_URL = 'https://krystof.litomisky.com/tags/'

# number of blog posts to include in the most-recent list
NUM_POSTS = 5
NUM_SW_POSTS = 5


class Blog_post():
  def __init__(self):
    self.title = ''
    self.tags  = []        # list of strings
    self.url   = ''
    self.publish_date = '' # string as it appears in the html


class Tags_html_parser(HTMLParser):

  def __init__(self):
    # initialize the base HTMLParser class
    super().__init__()

    self.posts_by_tag = {} # tag (string) --> list of Blog_posts

    # used for parsing
    self.current_tag = '' # tag that we're currently parsing
    self.read_tag    = False # when true, read the next tag name

    self.current_post = Blog_post() # the post we're parsing now
    self.read_post    = False # when true, we're reading a post now
    self.read_time    = False # when true, we're reading the publish time now
    self.read_post_title = False # when true, we're reading the post title


  def get_posts_by_tag(self):
    return self.posts_by_tag


  def print(self):
    '''
    print the posts we have to stdout
    '''
    for tag in self.posts_by_tag:
      print(f"{tag}:")
      for post in self.posts_by_tag[tag]:
        print(f"  {post.title}")


  def handle_starttag(self, tag, attrs):
    # handle h2s - get the name of the tag we're about to parse
    if tag == 'h2':
      self.read_tag = True

    # handle lis - each a post
    if tag == 'li':
      # INFO("Start tag:", tag)
      # for attr in attrs:
      #   print("     attr:", attr)
      self.current_post = Blog_post()
      self.read_post = True

    # if we're now reading a post line...
    if self.read_post:
      # handle as - links to blog post
      if tag == 'a':
        for attr in attrs:
          if attr[0] == 'href':
            self.current_post.url = BLOG_BASE_URL + attr[1]

        # note to read the title next
        self.read_post_title = True

      # read the publish time?
      if tag == 'time':
        self.read_time = True


  def handle_endtag(self, tag):
    # if we're now reading a post...
    if self.read_post:
      # ...and we got to the closing </li>
      if tag == 'li':
        # save the post
        self.posts_by_tag[self.current_tag].append(self.current_post)
        self.current_post = Blog_post()


  def handle_data(self, data):
    # are we trying to start reading a new tag?
    if self.read_tag:
      self.current_tag = data
      self.read_tag = False
      self.posts_by_tag[self.current_tag] = []
      # INFO(f"current tag: {self.current_tag}", color = LOG_COLORS['GREEN'])
      return

    # are we reading the publish time of a post?
    if self.read_time:
      self.current_post.publish_date = data
      self.read_time = False
      return

    # read the title of a post
    if self.read_post_title:
      self.current_post.title = data
      self.read_post_title = False



class Readme_builder:

  def __init__(self, args):
    # args are from argparse
    self.args = args

    # list of latest Klog posts
    self.klog_posts = []

    # the original README - before this script re-generated it
    self.README_ORIG = ''


  def get_blog_posts_by_tag(self) -> str:
    try:
      response  = requests.get(BLOG_TAGS_URL)
      tags_page = str(response.content)
      # simplify it - only keep the section I need using string search before starting html processing
      #   <!-- .entry-header -->
      #   <div class="entry-content">
      #     "<!-- Archive by tag -->"
      #     # what I want is here
      #   </div>
      #   ends with <!-- .entry-content -->
      # so chop off everything up to Archive by tag
      # and chop from (and including) everything past the last </div>
      archive_by_tag_start = tags_page.find("<!-- Archive by tag -->")
      entry_content_end    = tags_page.find("<!-- .entry-content -->")
      ending_div = tags_page.rfind('</div>', archive_by_tag_start, entry_content_end)
      archive_by_tag_html = tags_page[archive_by_tag_start : ending_div]

      # with open('archive_by_tag.html', 'w') as fp:
      #   fp.write(archive_by_tag_html)

      # now parse it!
      parser = Tags_html_parser()
      parser.feed(archive_by_tag_html)
      # parser.print()
      return parser.get_posts_by_tag()

    except Exception as e:
      ERROR(e)
      traceback.print_exc()


  def get_blog_posts(self) -> str:
    '''
    Return the markdown of the most recent blog posts
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

    # add the latest software posts
    SW_POSTS_MD = self.get_sw_posts_md()
    result = result.replace("<!-- SW BLOG POSTS HERE -->", SW_POSTS_MD)

    # save the result
    with open(self.args.output, 'w') as fp:
      fp.write(result)
    return


  def get_sw_posts_md(self) -> str:
    '''
    Get the markdown string for the latest software posts
    '''
    md = '### Latest Software Posts\n' # the return markdown string

    posts_by_tag = self.get_blog_posts_by_tag()

    sw_posts = posts_by_tag['Software']
    for i in range(NUM_SW_POSTS):
      p = sw_posts[i]
      s = f"[{p.title}]({p.url}?utm_source=krystofl_github)"
      md += f"- {s}\n"

    return md


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
    tweet = "New blog post: {}: {}".format(latest['title'], url)

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
