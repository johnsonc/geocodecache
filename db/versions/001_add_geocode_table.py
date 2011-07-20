from sqlalchemy import *
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION

meta = MetaData()

geocode = Table('geocode', meta,
                Column('query', String(255), primary_key=True),
                Column('lat', DOUBLE_PRECISION()),
                Column('lng', DOUBLE_PRECISION()),
                Column('source', String(30)),
                Column('json', String(1024)),
                )

def upgrade(migrate_engine):
  meta.bind = migrate_engine
  geocode.create()


def downgrade(migrate_engine):
  meta.bind = migrate_engine
  geocode.drop()
