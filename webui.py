from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import os
import configparser
import threading
import time
import requests
import logging

app = Flask(__name__)
app.secret_key = 'arxdeari'
USER_DIR = os.path.join(os.path.dirname(__file__), 'users')

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

user_alarm_threads = {}

def load_user_config(username):
    """Loads saved alarms for the user from their config.txt file."""
    alarms = {}
    user_config_file = os.path.join(USER_DIR, username, 'config.txt')
    config = configparser.ConfigParser()
    if os.path.exists(user_config_file):
        config.read(user_config_file)
        for section in config.sections():
            alarm_time = datetime.strptime(config[section]['time'], '%Y-%m-%d %H:%M:%S')
            intensity = int(config[section]['intensity'])
            duration = int(config[section]['duration'])
            alarms[section] = (alarm_time, intensity, duration)
    logging.debug(f"Loaded alarms for user {username}: {alarms}")
    return alarms

def save_alarm_to_user_config(username, alarm_name, alarm_time, intensity, duration):
    """Saves an alarm to the user's config.txt file."""
    user_config_file = os.path.join(USER_DIR, username, 'config.txt')
    config = configparser.ConfigParser()
    if os.path.exists(user_config_file):
        config.read(user_config_file)

    config[alarm_name] = {
        'time': alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
        'intensity': str(intensity),
        'duration': str(duration)
    }

    with open(user_config_file, 'w') as configfile:
        config.write(configfile)
    logging.debug(f"Saved alarm for user {username}: {alarm_name} at {alarm_time}")

def load_user_env(username):
    """Loads the API key and Shock ID from the user's .env file."""
    user_env_file = os.path.join(USER_DIR, username, '.env')
    if os.path.exists(user_env_file):
        config = configparser.ConfigParser()
        config.read(user_env_file)
        api_key = config['DEFAULT'].get('SHOCK_API_KEY')
        shock_id = config['DEFAULT'].get('SHOCK_ID')
        logging.debug(f"Loaded env for user {username}: API Key: {'*' * len(api_key)}, Shock ID: {shock_id}")
        return api_key, shock_id
    logging.warning(f"No .env file found for user {username}")
    return None, None

def save_user_env(username, api_key, shock_id):
    """Saves the API key and Shock ID to the user's .env file."""
    user_env_file = os.path.join(USER_DIR, username, '.env')
    config = configparser.ConfigParser()
    config['DEFAULT'] = {
        'SHOCK_API_KEY': api_key,
        'SHOCK_ID': shock_id
    }
    with open(user_env_file, 'w') as configfile:
        config.write(configfile)
    logging.debug(f"Saved env for user {username}: API Key: {'*' * len(api_key)}, Shock ID: {shock_id}")

def trigger_shock(api_key, shock_id, intensity, duration):
    """Sends a shock command to the OpenShock API."""
    url = 'https://api.shocklink.net/2/shockers/control'
    headers = {
        'accept': 'application/json',
        'OpenShockToken': api_key,
        'Content-Type': 'application/json'
    }

    payload = {
        'shocks': [{
            'id': shock_id,
            'type': 'Shock',
            'intensity': intensity,
            'duration': duration,
            'exclusive': True
        }],
        'customName': 'OpenShockClock'
    }

    try:
        response = requests.post(url=url, headers=headers, json=payload)
        response.raise_for_status()
        logging.info(f"Shock triggered successfully: Intensity {intensity}, Duration {duration}")
    except requests.RequestException as e:
        logging.error(f"Failed to send shock. Error: {str(e)}")

def update_alarms(username):
    """Updates the alarms for the next day and checks if they need to be triggered."""
    logging.info(f"Starting alarm update thread for user {username}")
    while True:
        alarms = load_user_config(username)
        api_key, shock_id = load_user_env(username)

        if not api_key or not shock_id:
            logging.warning(f"Missing API key or Shock ID for user {username}")
            time.sleep(60)
            continue

        now = datetime.now()
        for name, (alarm_time, intensity, duration) in list(alarms.items()):
            if now >= alarm_time:
                logging.info(f"Triggering alarm {name} for user {username}")
                trigger_shock(api_key, shock_id, intensity, duration)

                next_alarm_time = alarm_time + timedelta(days=1)
                alarms[name] = (next_alarm_time, intensity, duration)
                save_alarm_to_user_config(username, name, next_alarm_time, intensity, duration)
                logging.info(f"Updated alarm {name} for user {username} to next day: {next_alarm_time}")

        time.sleep(60)

def start_user_alarm_thread(username):
    """Starts a thread to handle alarms for a specific user."""
    if username in user_alarm_threads and user_alarm_threads[username].is_alive():
        logging.info(f"Alarm thread for user {username} is already running")
        return

    thread = threading.Thread(target=update_alarms, args=(username,))
    thread.daemon = True
    thread.start()
    user_alarm_threads[username] = thread
    logging.info(f"Started alarm thread for user {username}")

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    api_key, shock_id = load_user_env(username)
    alarms = load_user_config(username)
    return render_template('index.html', alarms=alarms)

@app.route('/add', methods=['GET', 'POST'])
def add_alarm():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if request.method == 'POST':
        name = request.form['name']
        intensity = int(request.form['intensity'])
        duration = int(float(request.form['duration']) * 1000)
        time_str = request.form['time']
        alarm_time = datetime.strptime(time_str, "%H:%M").replace(
            year=datetime.now().year,
            month=datetime.now().month,
            day=datetime.now().day
        )
        if alarm_time < datetime.now():
            alarm_time += timedelta(days=1)
        save_alarm_to_user_config(username, name, alarm_time, intensity, duration)

        start_user_alarm_thread(username)

        return redirect(url_for('index'))
    return render_template('add_alarm.html')

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if request.method == 'POST':
        api_key = request.form['api_key']
        shock_id = request.form['shock_id']
        save_user_env(username, api_key, shock_id)

        start_user_alarm_thread(username)

        return redirect(url_for('index'))
    else:
        api_key, shock_id = load_user_env(username)
        return render_template('setup.html', api_key=api_key, shock_id=shock_id)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user_folder = os.path.join(USER_DIR, username)
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)

        user_config_file = os.path.join(user_folder, 'config.txt')
        with open(user_config_file, 'w') as configfile:
            configfile.write('')

        with open(os.path.join(USER_DIR, 'users.txt'), 'a') as f:
            f.write(f"{username}:{password}\n")

        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with open(os.path.join(USER_DIR, 'users.txt'), 'r') as f:
            users = dict(line.strip().split(':') for line in f)

        if username in users and users[username] == password:
            session['username'] = username
            start_user_alarm_thread(username)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.pop('username', None)
    if username in user_alarm_threads:
        del user_alarm_threads[username]
        logging.info(f"Removed alarm thread for user {username}")
    return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists(USER_DIR):
        os.makedirs(USER_DIR)

    app.run(debug=True)
