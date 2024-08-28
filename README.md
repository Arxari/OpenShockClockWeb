### Open Shock Clock on the web!
A python flask implementation of [OpenShockClock](https://github.com/Arxari/OpenShockClock)

This is dev branch for Users.

#### For developers

All user and alarm related data is stored in the `users` folder.

User usernames and passwords are stored in the `users.txt` file.

The `config.txt` file contains the user's configuration.

The `env` file contains the user's api key and shock id.

When a user creates an account, the webui.py script will create a folder in the `users` folder with the username as the folder name.

**The goal of this branch**
Make OpenShockClock viable to be hosted on the web. This means users can create their own accounts, create their own alarms, and all of those accouns can be access concurrently and all alarms are active, this means that if user A and user B have an alarm set for 8AM, it will go off for 8AM for both with their specified selections.
Users should also be able to create new alarms while an alarm is running without the host server having to be re-ran.

Later down the road, more features will be added, but this is priority.
