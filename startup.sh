local_config="http.conf"
nginx_config="/etc/nginx/conf.d/http.conf"

# start the mongo-deamon
if [ "$(systemctl is-active mongod)" != "active" ]
then
	echo "starting service 'mongod'"
	sudo service mongod start
else
	echo "service 'mongod' is running"
fi

# check the nginX web-config-file
if [ "$(cmp $local_config $nginx_config)" != "" ]
then
	echo "nginx config file changed!"
	sudo cp "$local_config" "$nginx_config"
else
	echo "nginx config did not change"
fi

# start the nginX-deamon
if [ "$(systemctl is-active nginx)" != "active" ]
then
	echo "starting service 'nginx'"
	sudo service nginx start
else
	echo "service 'nginx' is running"
	sudo nginx -s reload
fi

# start the certbot-timer
if [ "$(systemctl is-active certbot.timer)" != "active" ]
then
	echo "starting service 'certbot.timer'"
	sudo service certbot.timer start
else
	echo "service 'certbot.timer' is running"
fi

# start the application itself (blocking)
source "env/bin/activate"
export PYTHONPATH=$PWD
# terminate all background processes if app/main.py is terminated
trap "kill 0" EXIT
# run app/dashboard/parser/data_daemon.py in background (check for new data every day at midnight)
python3 "app/dashboard/parser/data_daemon.py" &
python3 "app/main.py"
