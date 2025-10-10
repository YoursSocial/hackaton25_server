# Sensor Management System



## Initial Setup

#### Required software:
- screen (preinstalled on Ubuntu)
- openssl (preinstalled on Ubuntu)
- python 3.11
- sudo apt install python3.11-venv
- sudo apt install certbot python3-certbot-nginx

#### Install the Virtual environment:

1. Clone the repository

2. In the root directory, create a virtual environment to install the dependencies:

   $ `python3.11 -m venv env`

3.  Activate the virtual environment:

    $ `source env/bin/activate`

6. Install the requirements:

   (env)$ `pip install -r requirements.txt`

7. Create the jwt-secrets file:

   (env)$ `echo 'AUTHJWT_SECRET_KEY="placeMySecretKeyHere"' > env/.env`

8. Deactivate the virtual environment by entering `deactivate`

Note: if a system upgrade messes with the virtual environment and upgrades python version by accident, the simplest fix is to uninstall the virtual environment (`rm -r env`), install python3.11 if it's not on the system anymore and create a new virtual environment (step 2 to 6).

#### Install MongoDB on Ubuntu 20.04:

0. Info: currently used for the main application, mights be moved in the next updates to postgres

1. Import the public key used by the package management system:

   $ `wget -qO - https://www.mongodb.org/static/pgp/server-5.0.asc | sudo apt-key add -`

2. Create a list file for MongoDB:

   $ `echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/5.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-5.0.list`

3. Reload the package database:

   $ `sudo apt-get update`

4. Install MongoDB packages:

   $ `sudo apt-get install -y mongodb-org`

#### Setup PostgreSQL:

0. Info: currently only used for the dashboard data, in future maybe for the whole application

1. Install PostgreSQL

    $ `apt install postgresql`
2. Login as superuser or create own user account with sufficient privileges, then create new database with name postgres

    $ `sudo -u postgres createdb postgres`
3. Enter database

    $ `sudo -u postgres psql postgres`
4. Change the password of the superuser to something secure ( ! important step, default password "postgres" not secure ! )

    $ `\password postgres`

5. Create tables

```
    CREATE SCHEMA public AUTHORIZATION pg_database_owner;

    CREATE SEQUENCE sensor_job_id_seq
        INCREMENT BY 1
        MINVALUE 1
        MAXVALUE 2147483647
        START 1
        CACHE 1
        NO CYCLE;

    CREATE TABLE jobs (
        "name" text NOT NULL,
        command text NULL,
        start_time int4 NULL,
        end_time int4 NULL,
        CONSTRAINT jobs_pkey PRIMARY KEY (name)
    );

    CREATE TABLE sensor_job (
        id serial4 NOT NULL,
        job_name text NULL,
        sensor_name text NULL,
        lat float8 NULL,
        lon float8 NULL,
        sample_rate int4 NULL,
        center_freq int4 NULL,
        bandwidth int4 NULL,
        gain int4 NULL,
        if_gain int4 NULL,
        bb_gain int4 NULL,
        decimation int4 NULL,
        CONSTRAINT sensor_job_job_name_sensor_name_key UNIQUE (job_name, sensor_name),
        CONSTRAINT sensor_job_pkey PRIMARY KEY (id),
        CONSTRAINT sensor_job_job_name_fkey FOREIGN KEY (job_name) REFERENCES jobs("name")
    );

    CREATE TABLE signal (
        id int4 NOT NULL,
        "timestamp" float8 NOT NULL,
        signal_level float4 NULL,
        background_noise float4 NULL,
        snr float4 NULL,
        count int4 NULL,
        CONSTRAINT signal_pkey PRIMARY KEY (id, "timestamp"),
        CONSTRAINT signal_id_fkey FOREIGN KEY (id) REFERENCES sensor_job(id)
    );

    CREATE TABLE stderr (
        id int4 NOT NULL,
        "timestamp" float8 NOT NULL,
        i int4 NULL,
        o int4 NULL,
        ok_s int4 NULL,
        ok int4 NULL,
        CONSTRAINT stderr_pkey PRIMARY KEY (id, "timestamp"),
        CONSTRAINT stderr_id_fkey FOREIGN KEY (id) REFERENCES sensor_job(id)
    );

    CREATE TABLE packets (
        id int4 NOT NULL,
        "type" text NOT NULL,
        count int4 NULL,
        CONSTRAINT packets_pkey PRIMARY KEY (id, type),
        CONSTRAINT packets_id_fkey FOREIGN KEY (id) REFERENCES sensor_job(id)
    );
```

#### Install and Setup Nginx:

1. Install Nginx:

   $ `sudo apt update && sudo apt install nginx`

2. Move `http.conf` to `/etc/nginx/conf.d/` and edit its root and index to point to the correct locations

3. In `nginx.conf` comment out or delete the line `include /etc/nginx/sites-enabled/*;`

4. Reload Nginx:

   $ `sudo nginx -s reload`

#### LetsEncrypt Certbot setup:

1. $ `sudo apt install certbot python3-certbot-nginx`

2. Modify the `http.conf` in `/etc/nginx/conf.d/`: 
   1. Remove all parts that are handeled by Certbot (the lines with comments).
   2. Change the `listen 443 ssl http2;` to `listen 80;`

3. Reload NginX: $ `sudo systemctl reload nginx`

4. Run Certbot to create the certificates: $ `sudo certbot --nginx -d myLeoCommonDummyUrl.com`

5. Start the Certbot Timer: $ `sudo systemctl start certbot.timer`

#### Setup iridium-toolkit:
1. In the root directory of the server, create tools folder

    $ `mkdir tools`
2. Enter folder

    $ `cd tools`

2. Clone the repository

    $ `git clone https://github.com/muccc/iridium-toolkit.git`

## Setup the accounts

Do not run the development environment on the live-server!

The development environment offers: 

- FastAPI development-page (127.0.0.1:8000/docs)

#### Activate the development-environment:
   
1. Delete the http.conf: $ `rm http.conf`

2. Copy http_dev.conf to http.conf: $ `cp http_dev.conf http.conf` 

3. http.conf: change `root /home/user/server/app/static;` to your own path to the /app/static-folder

4. Modify `startup.sh`: comment out the block about the certbot-timer

5. Run `startup.sh`

6. Open website via `http://127.0.0.1` or FastAPI via `127.0.0.1:8000/docs`

7. Modify the mongoDB as shown below to create a inital dummy-account.

Differences between dev-env and live-env:

1. http.conf: removed `|docs/` from line `location ~ ^/(data/|fixedjobs/|docs/|sensors/|login/)`

2. http.conf: modified line `proxy_pass http://0.0.0.0:8000;` to `proxy_pass http://127.0.0.1:8000;`

3. Added https and a http-reroute to the http.conf.


#### Setup the database:
IMPORTANT: make sure to only use the insecureAdminLogin (dummy account) in development environment. Create a real admin account by using this dummy account, than delete this dummy.

1. Start the dev-env as descried above.

2. Open the virtual envoronment: 

   $ `source env/bin/activate`

3. Open mondodb-shell: 

   $ `mongo` (or depending on the system: $ `mongosh`)

4. Check that the database "sensors" is available: 

   $ `show dbs`

5. Change to the sensors database or create it if non-existent yet (is the same command): 

   $ `use sensors`

6. Insert dummy user "insecureAdminLogin" and implicitly create the collection "users":

   $ `db.users.insert({ "_id" : ObjectId("6431594b33bd9273ce33f0b2"), "email" : "test@mail.com", "username" : "insecureAdminLogin", "hashed_password" : BinData(0,"JDJiJDEyJGdmWllwN0NoYmNjdlJyTmhkakJPcXU2VEVNMVpYamtWVUptRnVpYkNnZGc0UUZNVjBwdVVX"), "role" : "admin", "creation_date" : 954587471, "owned_sensors" : [ ], "scheduled_jobs" : [ ], "online_status" : [ [ 0, 0 ] ], "public_rsa_key" : "" })`

6. Verify that the collection "users" is available: 

   $ `show collections`

7. Show all registered users: 

   $ `db.users.find()`

#### Dummy admin account
On live systems NEVER use the insecureAdminLogin!

User: insecureAdminLogin
Password: insecurePasswordRemoveAfterAdminCreated123onZhs2LipBPZVg2itHJsoS7U5tkywsxP

#### Create your own Admin Account

1. Login a first time with the insecureAdminLogin.

2. Create your own admin account with a secure password, to use it later.

3. Logout from the insecureAdminLogin and login with your own admin account.

4. Delete the insecureAdminLogin.

#### Setup Dashboard:

1. Create a dedicated dashboard account with user privileges on the server

2. Locate the `.env` file in the `/env` directory, add the following lines and fill the empty quotation marks with own values

    `DASH_DB_USER=""` the name of the postgres user ("postgres" or own user account)

    `DASH_DB_PASSWORD=""` the password of the postgres user

    `DASH_USER=""` the name of the dashboard user from step 1

    `DASH_PASSWORD=""` the password of the dashboard user from step 1

#### Deactivate the development-environment:
   
1. Copy http_live.conf to http.conf: $ `cp http_live.conf http.conf` 

2. http.conf: change `root /home/user/server/app/static;` to your own path to the /app/static-folder

3. Modify `startup.sh`: comment in the block about the certbot-timer

4. Run `startup.sh`

5. Open website via the external address.

## Run the Application

Use the `startup.sh`-script or follow the next steps to manually start it:

1. Start nginx:

   $ `sudo service nginx start/stop/status` or do $ `sudo nginx -s reload` for reloading

2. Start the Certbot Timer: $ `sudo systemctl start certbot.timer`

3. Start mongoDB:

   $ `sudo service mongod start/stop/status`

4. The application has to be run in the virtual environment where the requirements are installed.

   $ `cd server`

​   $ `source env/bin/activate`

​   Note: The virtual environment can be deactivated by entering `deactivate`

Furthermore, set PYTHONPATH as the current directory:

​   (env)$ `export PYTHONPATH=$PWD`

Finally, run the application:

​   (env)$ `python3 app/main.py`


## Run the Application using screen
1. Open a screen session: $ `screen`

2. Run the application with the startup script: $ `./startup.sh`

3. Detatch the current session: $ `ctrl+a`, `d`

4. Close the terminal.

Access the detatched screen session and terminate the server:

1. List all detatched sessions: $ `screen -ls`

2. Connect to a specific session: $ `screen -r <sessionName>`

3. Terminate the server: $ `ctrl-x`

4. End the screen session: $ `exit`





## TODOs

- [X] Webinterface.UserDetails: Implement missing buttons for user account management.
- [ ] Webinterface.FixedJobs: show local-time and convert to timestamp when creating a new job. Add some buttons [+1 min, +10 min, +1h] for simple interaction.
- [ ] Webinterface.FixedJobs: method 'get_fixed_jobs_by_sensorname' rename the router-path from "/fixedjobs/{name}" to "/fixedjobs/sensor_name/{name}" for clarification. But this also needs to be adjusted in the sensors!
- [X] Webinterface.SensorDetails: add "are you sure" window, before the new JWT for a new sensor is created (otherwise you can remove sensors from the server with this accedentally). (TODO: in progress (to test)
- [ ] Webinterface.FixedJobs: when creating new fixed job, ensure not required arguments are not enforced (ensure every command has default parameters)
- [ ] Webinterface.FixedJobs: when creating new fixed job, make it possible to select sensor directly
- [X] Public website: make the connection to osm secure, so that it does not rise a tls-warning
- [ ] Webinterface.Data: add possiblity to filter/sort data collection
- [ ] Webinterface.Data: add upload-time to data-table

## Troubleshooting

This section lists errors that can occur by wrongly operating the application and how to fix them.

- Getting `localhost:27017: [Errno 111] Connection refused` when trying to call the API (for example by loading the webpage):

  The MongoDB service `mongod` wasn't shut down properly with $ `sudo service mongod stop` and the lock file still exists, not allowing the service to launch. Remove the lock file and start the service:

  ​	$ `sudo rm /var/lib/mongodb/mongod.lock`
  ​	$ `sudo service mongod start`

- MongoDB-shell: 

   $ `mongo` (Ctrl+c for exit)

- Create Certficates: $ `openssl req -x509 -newkey rsa:4096 -sha256 -days 365 -nodes -keyout myDummyLeoCommonUrl.key -out myDummyLeoCommonUrl.crt -subj "/C=DE/ST=Rhineland-Palatinate/L=Kaiserslautern/O=University Kauserslautern/OU=DistributedComputerSystemsLab/CN=www.myDummyLeoCommonUrl.com" -addext "subjectAltName=DNS:myDummyLeoCommonUrl.com"`

- "I set up ngnix correctly but get a 404." -> check if the http user can access the server directory. This is can be a problem in development settings. 
  Test access: `sudo -u http stat <path>/server`

#### Delete a user and his tokens directly in the DB

1. Open the virtual envoronment: $ `source env/bin/activate`

2. Open mondodb-shell: $ `mongo`

3. Check that the target user is available: $ `db.users.find({"username":"insecureAdminLogin"})` or `db.users.find({"email":"testmail@test.com"})`

4. Delete the user: $ `db.users.deleteOne({"username":"insecureAdminLogin"})` or delete all with one mail adress `db.users.deleteMany({"email":"testmail@test.com"})`

5. Find the refresh-token: $ `db.refresh_token_whitelist.find({"sub":"insecureAdminLogin"})`

6. Remember the "sibling_jti", this is the JSON Web Token ID of the corresponding access-token. 

7. Delete the refresh-token: $ `db.refresh_token_whitelist.deleteOne({"sub":"insecureAdminLogin"})` or using the jti `db.refresh_token_whitelist.deleteOne({"jti":"INSERT-YOUR-JTI-HERE"})`

8. Add the access-token to the black list: `db.access_token_blacklist.insertOne({"jti" : "INSERT-SIBLING-JTI-HERE", "sub" : "INSERT-SUBJECT-NAME-HERE", "expire" : "INSERT-EXPIRATION-DATE-HERE", "time_added" : "INSERT-CURRENT-DATE-HERE"})`. Use an expiration date of today+3 days (make sure it is blocked long enough). The dates must be in format "YYYY-mm-dd HH:MM:SS", example "2020-12-31 23:59:59". 

## Bugs

- Webinterface.FixedJobs: deleting a fixed job does not remove the job from the sensors joblist

- When a job-file is uploaded, the DB entry is created before the file is stored on the disk. If a soring-error occures, there is no file on the disk, but an entry in the DB.

- ...







