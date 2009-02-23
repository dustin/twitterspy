import ConfigParser

import config

db_type = config.CONF.get("db", "type")

if db_type == 'couch':
    from db_couch import *
elif db_type == 'sql':
    from db_sql import *
else:
    raise ConfigParser.Error("Unknown database type:  " + db_type)
