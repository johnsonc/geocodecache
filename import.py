import sqlalchemy
# The Postgres and SQLite driver has different syntax for parameterized SQL. SQLAlchemy handles that with the text()
# wrapper and gives us a driver neutral way of creating a new connection.
from sqlalchemy.sql.expression import text
import argparse

parser = argparse.ArgumentParser(description='Copy the geocode cache data from one database to another.')
parser.add_argument('fromdb')
parser.add_argument('todb')

args = parser.parse_args()

import_into = sqlalchemy.create_engine(args.todb).connect()
import_from = sqlalchemy.create_engine(args.fromdb).connect()
print 'existing records:', import_into.execute('select count(*) from Geocode').fetchone()
print 'importing records:', import_from.execute('select count(*) from Geocode').fetchone()
updated = 0
count = 0
inserted = 0
trans = import_into.begin()
for row in import_from.execute('select query, lat, lng from Geocode'):
  count += 1
  query, lat, lng = row
  if len(query) > 255:
    query = query[-255:]
  try:
    existing = import_into.execute(text('select lat, lng from Geocode where query=:query'), query=query).fetchone()
    if existing:
      # Only overwrite None values
      if existing[0] is None and not lat is None:
        updated += 1
        import_into.execute(text('update Geocode set lat=:lat, lng=:lng where query=:query'),
                            lat=lat, lng=lng, query=query)
    else:
      import_into.execute(
        text('insert into Geocode (query, lat, lng, source, json) values (:query, :lat, :lng, :source, :json)'),
        query=query, lat=lat, lng=lng, source=None, json=None)
      inserted += 1
  except sqlalchemy.exc.DataError:
    print "Bad Unicode: ", query
    trans.commit()
    trans = import_into.begin()
  if count % 1000 == 0:
    print count, updated, inserted
    trans.commit()
    trans = import_into.begin()
trans.commit()
print 'final records:', import_into.execute('select count(*) from Geocode').fetchone()
