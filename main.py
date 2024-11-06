# This file has been deprecated in favor of app.py
# All functionality has been moved to Flask routes
from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
