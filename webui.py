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

alarms = {}
alarms_lock = threading.Lock()

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
    with alarms_lock:
        alarms.clear()
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            for section in config.sections():
                alarm_time = datetime.strptime(config[section]['time'], '%Y-%m-%d %H:%M:%S')
                intensity = int(config[section]['intensity'])
                duration = int(config[section]['duration'])
                days = config[section].get('days', '').split(',')
                days = [day for day in days if day]  # Remove empty strings
                repeat = config[section].getboolean('repeat', False)
                alarms[section] = (alarm_time, intensity, duration, days, repeat)

def save_alarm_to_config(alarm_name, alarm_time, intensity, duration, days, repeat):
    """Saves an alarm to the config.txt file."""
    with alarms_lock:
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)

        config[alarm_name] = {
            'time': alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
            'intensity': str(intensity),
            'duration': str(duration),
            'days': ','.join(days),
            'repeat': str(repeat)
        }

        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

        alarms[alarm_name] = (alarm_time, intensity, duration, days, repeat)

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

def update_alarms(api_key, shock_id):
    """Updates the alarms and triggers them on the specified days."""
    while True:
        now = datetime.now()
        with alarms_lock:
            for name in list(alarms.keys()):
                alarm_time, intensity, duration, days, repeat = alarms[name]
                
                # Check if today is one of the specified days
                if days and now.strftime('%A') not in days:
                    continue  # Skip this alarm if today is not in the specified days
                
                # Check if the current time is greater than or equal to the alarm time
                if now >= alarm_time:
                    trigger_shock(api_key, shock_id, intensity, duration)
                    
                    if repeat:
                        # Schedule for the next occurrence on the correct day
                        next_day = (alarm_time + timedelta(days=1)).strftime('%A')
                        while next_day not in days:
                            alarm_time += timedelta(days=1)
                            next_day = alarm_time.strftime('%A')
                        next_alarm_time = alarm_time + timedelta(days=1)
                        alarms[name] = (next_alarm_time, intensity, duration, days, repeat)
                        save_alarm_to_config(name, next_alarm_time, intensity, duration, days, repeat)
                    else:
                        del alarms[name]
        time.sleep(30)

@app.route('/')
def index():
    with alarms_lock:
        current_alarms = alarms.copy()
    return render_template('index.html', alarms=current_alarms)

@app.route('/setup')
def setup():
    return render_template('setup.html')

@app.route('/add', methods=['GET', 'POST'])
def add_alarm():
    if request.method == 'POST':
        name = request.form['name']
        intensity = int(request.form['intensity'])
        duration = int(float(request.form['duration']) * 1000)
        time_str = request.form['time']
        repeat = request.form.get('repeat') == 'true'
        days = request.form.getlist('days')

        now = datetime.now()
        alarm_time = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {time_str}", '%Y-%m-%d %H:%M')
        if alarm_time < now:
            alarm_time += timedelta(days=1)

        save_alarm_to_config(name, alarm_time, intensity, duration, days, repeat)

        return redirect(url_for('index'))

    return render_template('add_alarm.html')

@app.route('/delete/<alarm_name>')
def delete_alarm(alarm_name):
    with alarms_lock:
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            if config.has_section(alarm_name):
                config.remove_section(alarm_name)
                with open(CONFIG_FILE, 'w') as configfile:
                    config.write(configfile)
                alarms.pop(alarm_name, None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    api_key, shock_id = load_env()
    load_config()
    alarm_thread = threading.Thread(target=update_alarms, args=(api_key, shock_id), daemon=True)
    alarm_thread.start()
    app.run(debug=True)
