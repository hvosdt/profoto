from peewee import *
import config
import datetime

#db = PostgresqlDatabase(config.DB_NAME, user=config.DB_USERNAME, password=config.DB_PASSWORD)
db = SqliteDatabase('vpn_bot.db')

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    user_id = TextField(unique=True)
    expire_in = DateTimeField(default=datetime.datetime.now())
    node = TextField(default='Node1')
    is_active = BooleanField(default=False)
    is_freemium = BooleanField(default=False)
    
    



    

     