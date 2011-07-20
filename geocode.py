import socket
import urllib
import urllib2
import time
import psycopg2
import flags
# TODO(tirsen): Change this to be named as just 'json' (have to change name of lots of variables)
import json as simplejson

YAHOO_KEY = 'b7XKURzV34FLNYpkaClbpqMN0jT9sda5wbPr9Y1c6IjMrHuSkrGVhieVZLAwTdY-'
BING_KEY = 'Ah5goplkyJDUquiOWOTI6flwj_lv14iWgXFKpSbodlrpgQhNZN_ay6TWp9INfcOl'
MIN_YAHOO_QUALITY = 86

connection = None

class OverQueryLimit(Exception):
  pass


def encode(s):
  if type(s) == unicode:
    s = s.encode('utf-8')
  return s


def FloatAfter(xml, tag):
  p = xml.find(tag)
  if p == -1:
    return None
  p += len(tag)
  q = xml.find('<', p)
  return float(xml[p:q])


def BetterValues(source1, has_value1, source2, has_value2):
  """Return whether (source1, has_value1) is better than (source2, has_value2).

  - Having no source is the worst, because it means we have old, possibly contaminated
    data by Yahoo.

  - Having a value is better than not having a value.

  - Otherwise pick Google over Yahoo.
  """
  if (source1 is None) != (source2 is None):
    return source2 is None
  if (has_value1 != has_value2):
    return has_value1
  SOURCES = {'Google': 3, 'Yahoo': 2, 'Bing': 1}
  s1 = SOURCES.get(source1, 0)
  s2 = SOURCES.get(source2, 0)
  return s1 > s2


def GoogleGeocode(address):
  address = encode(address)
  url = 'http://maps.google.com/maps/api/geocode/json?address=%s&sensor=false' % urllib.quote_plus(address)
  final_url, search_results = GetUrl(url)
  if final_url is None:
    raise IOError('Google failure')
  json = simplejson.loads(search_results)
  status = json.get('status')
  if status == 'OVER_QUERY_LIMIT':
    raise OverQueryLimit
    #print json['results'][0].keys()
  if not json['results']:
    print 'JSON=', json
    print 'no result for', address
    return 'Google', json, None, None
  location = json['results'][0]['geometry']['location']
  return 'Google', json, location['lat'], location['lng']


def BingGeocode(key, address):
  address = encode(address)
  url = 'http://dev.virtualearth.net/REST/v1/Locations?q=%s&key=%s' % (urllib.quote_plus(address), key)
  final_url, search_results = GetUrl(url)
  if final_url is None:
    httperror = search_results
    if httperror.code == 400:
      return 'Bing', "{'error': 400}", None, None
    print final_url, search_results
    if httperror.code == 500:
      time.sleep(5)
      final_url, search_results = GetUrl(url)
      if final_url is None:
        raise IOError('Bing failure')
  json = simplejson.loads(search_results)
  sets = json['resourceSets']
  if not sets:
    print 'No results'
  for set in sets:
    resources = set['resources']
    for res in resources:
      confidence = res['confidence']
      point = res.get('point')
      print confidence, point
      if confidence.lower() == 'high' and point:
        lat, lng = point['coordinates']
        return 'Bing', json, lat, lng
  return 'Bing', json, None, None


def YahooGeocode(key, address):
  address = encode(address)
  url = 'http://where.yahooapis.com/geocode?q=%s&appid=%s&flags=J' % (urllib.quote_plus(address), key)
  final_url, search_results = GetUrl(url)
  if final_url is None:
    raise IOError('Yahoo failure')
  json = simplejson.loads(search_results)
  print 'YAHOO:', json
  results = json.get('ResultSet')
  if not results:
    return 'Yahoo', None, None, None
  quality = results.get('Quality', 0)
  if quality < MIN_YAHOO_QUALITY or results.get('Found') == 0:
    'print base quality too low', quality, results.get('Found')
    return 'Yahoo', json, None, None
  for result in results['Results']:
    res_quality = result.get('quality', quality)
    if res_quality >= MIN_YAHOO_QUALITY:
      print '--', res_quality
      return 'Yahoo', json, float(result['latitude']), float(result['longitude'])
  return 'Yahoo', json, None, None


def Geocode(address, retry=False, skip_yahoo=None, skip_google=None, skip_bing=None):
  if skip_yahoo is None:
    skip_yahoo = flags.skip_yahoo
  if skip_google is None:
    skip_google = flags.skip_google
  if skip_bing is None:
    skip_bing = flags.skip_bing

  global connection
  if connection is None:
    connection = psycopg2.connect(database=flags.database, user=flags.user)

  cursor = connection.cursor()
  cursor.execute('SELECT source, lat, lng FROM geocode WHERE query=%s', (address,))
  res = cursor.fetchone()
  if res:
    res_source, res_lat, res_lng = res
    if not retry:
      return res_lat, res_lng

  if skip_yahoo:
    lat = None
    lng = None
  else:
    source, json, lat, lng = YahooGeocode(YAHOO_KEY, address)
  if lat is None and not skip_bing:
    source, json, lat, lng = BingGeocode(BING_KEY, address)
  if lat is None and not skip_google:
    source, json, lat, lng = GoogleGeocode(address)

  if res:
    # we had a result, so we must be retrying
    if BetterValues(source, not lat is None,
                    res_source, not res_lat is None):
      print 'Updating... %s (%s) -> %s value:%s' % (res_source, not res_lat is None, source, not lat is None)
      cursor.execute('UPDATE geocode SET lat=%s, lng=%s, source=%s, json=%s WHERE query=%s',
                     (lat, lng, source, simplejson.dumps(json), address))
      connection.commit()
  else:
    cursor.execute('INSERT INTO geocode VALUES(%s, %s, %s, %s, %s) ',
                   (address, lat, lng, source, simplejson.dumps(json)))
  connection.commit()
  cursor.close()

  return lat, lng


def GetUrl(url, tries=5, minsleep=0.0, IsError=None):
  sleep = 2.0
  socket.setdefaulttimeout(float(flags.url_fetch_timeout) / 1000)
  for tries in range(tries):
    try:
      time.sleep(minsleep)
      request = urllib2.Request(url)
      request.add_header('User-Agent', 'Marco Polo')
      opener = urllib2.build_opener()
      handle = opener.open(request)
      final_url = handle.geturl()
      html = handle.read()
      if IsError and IsError(html):
        print 'service in error'
      else:
        return final_url, html
      time.sleep(sleep)
      sleep *= 3
    except urllib2.HTTPError, httperror:
      return None, httperror.code
    except urllib2.URLError, urlerror:
      print 'urllib:', urlerror.reason
      if 'no host' in urlerror.reason:
        return url, ''
    except IOError, io:
      print 'ioerror', io, type(io)
      pass
    except socket.error:
      print 'socket error'
      pass
  return None, None
