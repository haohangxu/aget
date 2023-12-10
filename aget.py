#!/usr/bin/python3
###########################################
###               IMPORTS               ###
###########################################
import argparse
import sys
import os
import re
import urllib3
import shutil
from urllib.parse import urljoin
from bs4 import BeautifulSoup

###########################################
###          FUNCTION DEFS              ###
###########################################

def request_page(url, timeout):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '
        'AppleWebKit/537.11 (KHTML, like Gecko) '
        'Chrome/23.0.1271.64 Safari/537.11',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
        'Accept-Encoding': 'none',
        'Accept-Language': 'en-US,en;q=0.8',
        'Connection': 'keep-alive'}
    http = urllib3.PoolManager()
    return http.request('GET', url, timeout=timeout, headers=headers)

def is_extension_int(url, extension):
    return re.match(".+\." + extension, url)

def is_extension(url, extension):
    result = is_extension_int(url, extension)
    print("HXU -- (%s, %s) => %s" % (url, extension, str(result)))
    return result

def get_abs_url_int(current_url, link):
    """ A function to get the absolute URL of a link """
    if re.match("#", link):
        return current_url
    
    # If our link isn't an absolute link already, make it absolute
    if not re.match("http://", link) and not re.match("https://", link):
        return urljoin(current_url, link)
        
    # Otherwise just return our link
    return link

def get_abs_url(current_url, link):
    result = get_abs_url_int(current_url, link)
    # print("HXU -- (%s, %s) => %s" % (current_url, link, result))
    return result

def download(target_directory, filename, r):
    with open(os.path.join(target_directory, filename), 'wb') as out:
        shutil.copyfileobj(r, out)

    # TODO: check for failure
    return True
                                                
def is_external(base_url, url):
    rel_path = os.path.relpath(url, base_url)

    print("HXU -- (%s, %s) => %s" % (base_url, url, rel_path))
    return re.match("\.\./", rel_path)
                    
def process_page(max_depth, depth, base_url, url, target, timeout, target_extension):
    global file_record

    # print("HXU -- processing page %s" % url);

    # If we've already seen this file, don't bother processing it
    if url in file_record:
        print_result(depth, base_url, url, file_record, True)

    else:
        if is_external(base_url, url):
            file_record[url] = "external"
            print_result(depth, base_url, url, file_record, False)
        else:
            if depth >= max_depth:
                file_record[url] = "stopping"
                print_result(depth, base_url, url, file_record, False)
            else:
                file_record[url] = "descending"
                print_result(depth, base_url, url, file_record, False)
                
                r = request_page(url, timeout)
                data = r.data.decode(encoding='iso-8859-1')
                r.close()
                
                try:
                    parsed = BeautifulSoup(data, features = "html.parser")
                    # Loop through all the links in the anchor tags
                    for link in parsed.find_all('a'):
                        # Make sure url is valid
                        if link.get("href") == None or link.get("href") == "":
                            continue
                        
                        # Calculate the absolute link of each new page
                        abs_url = get_abs_url(url, link.get("href"))

                        if is_extension(abs_url, target_extension):
                            r = request_page(abs_url, timeout)
                            status = "success" if download(target, link.contents[0], r) else "FAILURE"
                            file_record[url] = status
                            print_result(depth, base_url, url, file_record, False)
                            r.close()
                        else:
                            process_page(max_depth, depth+1, base_url, abs_url, target, timeout, target_extension)
                        
                except Exception as e:
                    print("Error: %s\n" % str(e))

def print_result(depth, base_url, url, file_record, seen):
    status = file_record[url]
    toprint = ""
    if status == "external":
        toprint = url
    else:
        toprint = os.path.relpath(url, base_url)

    if seen:
        print("  " * depth + ("%s [done: %s]" % (toprint, status)))
    else:
        print("  " * depth + ("%s [%s]" % (toprint, status)))


###########################################
###         MAIN SCRIPT                 ###
###########################################

current_folder = os.path.dirname(os.path.abspath(__file__))

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--depth", type=int, help="maximum depth to search", default=0)
parser.add_argument("-l", "--location", type=str, help="where to store downloaded files", default=current_folder)
parser.add_argument("-t", "--timeout", type=int, help="request timeout (in seconds)", default=2)
parser.add_argument("url", type=str, help="base URL to crawl")
parser.add_argument("-e", "--extension",  type=str, help="what type of assets to download")
args = parser.parse_args()

download_url = args.url
depth = args.depth
target_folder = args.location
timeout = args.timeout
target_extension = args.extension

# Check to make sure we don't have access issues
try:
    _ = request_page(download_url, timeout)
except urllib3.exceptions.HTTPError as e:
    sys.stderr.write("Error: This URL cannot be accessed.\n")
    sys.exit()

# Print "header" info
print("URL: " + download_url)
print("extension: " + target_extension)
print("download location: " + target_folder + "\n")

# Make a new hash map
global file_record
file_record = {}

print(os.path.dirname(download_url))

# Set the processing to start on the root url
process_page(depth, 0, os.path.dirname(download_url), download_url, target_folder, timeout, target_extension)

# Count up all the files
total = 0
succeeded = 0
values = file_record.values()

for val in values:
    if val == "success":
        succeeded += 1
    if val != "external":
        total += 1
