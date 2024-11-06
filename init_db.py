from app import create_app
from db_init import clear_and_init_db

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        clear_and_init_db()
