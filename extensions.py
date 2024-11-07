from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from time import sleep

db = SQLAlchemy()
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

def get_db():
    retries = 3
    while retries > 0:
        try:
            return db.session()
        except OperationalError as e:
            if retries == 1:
                raise e
            retries -= 1
            sleep(1)
