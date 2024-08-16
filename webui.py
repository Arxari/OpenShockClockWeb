from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import configparser
import threading
import time
import requests

app = Flask(__name__)

ENV_FILE = os.path.join(os.path.dirname(__file__), '.env')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.txt')

def load_env():
    """Loads the API key and Shock ID from the .env file."""
    if os.path.exists(ENV_FILE):
        load_dotenv(ENV_FILE)
        api_key = os.getenv('SHOCK_API_KEY')
        shock_id = os.getenv('SHOCK_ID')
        return api_key, shock_id
    return None, None 

def load_config():
    """Loads saved alarms from the config.txt file."""
    alarms = {}
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        for section in config.sections():
            alarm_time = datetime.strptime(config[section]['time'], '%Y-%m-%d %H:%M:%S')
            intensity = int(config[section]['intensity'])
            duration = int(config[section]['duration'])
            alarms[section] = (alarm_time, intensity, duration)
    return alarms

def save_alarm_to_config(alarm_name, alarm_time, intensity, duration):
    """Saves an alarm to the config.txt file."""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)

    config[alarm_name] = {
        'time': alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
        'intensity': str(intensity),
        'duration': str(duration)
    }

    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)

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
    
    response = requests.post(url=url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Failed to send shock. Response: {response.content}")

def update_alarms(alarms, api_key, shock_id):
    """Updates the alarms for the next day and checks if they need to be triggered."""
    while True:
        now = datetime.now()
        for name, (alarm_time, intensity, duration) in list(alarms.items()):
            if now >= alarm_time:
                trigger_shock(api_key, shock_id, intensity, duration)
                alarms[name] = (alarm_time + timedelta(days=1), intensity, duration)
                save_alarm_to_config(name, alarms[name][0], intensity, duration)
        time.sleep(60)

@app.route('/')
def index():
    api_key, shock_id = load_env()
    alarms = load_config()
    return render_template('index.html', alarms=alarms)

@app.route('/add', methods=['GET', 'POST'])
def add_alarm():
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
        save_alarm_to_config(name, alarm_time, intensity, duration)
        return redirect(url_for('index'))
    return render_template('add_alarm.html')

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        api_key = request.form['api_key']
        shock_id = request.form['shock_id']
        with open(ENV_FILE, 'w') as f:
            f.write(f"SHOCK_API_KEY={api_key}\n")
            f.write(f"SHOCK_ID={shock_id}\n")
        return redirect(url_for('index'))
    else:
        api_key, shock_id = load_env()
        return render_template('setup.html', api_key=api_key, shock_id=shock_id)

if __name__ == '__main__':
    api_key, shock_id = load_env()
    alarms = load_config()
    alarm_thread = threading.Thread(target=update_alarms, args=(alarms, api_key, shock_id), daemon=True)
    alarm_thread.start()
    app.run(debug=True)
