# Tuna Flask-Grafana Application

## Local Flask session
How start a Flask instance on your local machine (Example using headnode):
```
* Map a port(4000) on headnode, sample: `ssh <user>@<IP> -p <port_number> -L <port_mapping>:localhost:<port_mapping>`
* Install the Tuna venv and source it `source ~/myvenv/bin/activate`
* Set Flask app env variables as such:
  *export FLASK_APP=example_app
  *export FLASK_ENV=development
  *export FLASK_DEBUG=1
* Navigate to `example_app.py` and run the application on a designated port: **flask run --host=0.0.0.0 -p <port_mapping>**
This terminal session will now represent the flask backend.


In a different terminal session:
* Install the flaskapp module in /tuna/flaskapp by running:
  ```bash
  python3 setup.py 
  ```
```
Any changes in /tuna/flaskapp/example_grafana.py will now be visible in the flask backend. This represents 
the entrypoint for Grafana.

## Connect your dev box to a Grafana instance.
The following steps will show how to set up your own Flask application and connect it to Grafana.
```
1. Start a local Flask session on your deb box. Details on how to do this in the previous section.
Chose a port that is unused on your box. It is advised to run this in a permanent session like tmux.
2. Create an ssh tunnel from headnode (this is where Grafana runs) to your local dev box. Instructions
on how to do this can be found in the doc/NonQTSNodeSetup.md
3. Set up your dev box as a Data-Source in Grafana. Open Grafana (you need edit permissions) and
navigate to Configurations -> Data Source (on the left hand side vertical tab). Click `Add data source`
and select `SimpleJson` type. Give your dev box a unique identifiable name and set the URL address
similar to: `http://alex-MS-7B09:4000`. The port 4000 must match the port your Flask app is running
on on your dev box. Details on how to start a Flask app on your local dev box can be found in the
previous section. Leave Access to default (Server default). You can check alex-devbox data source
for an example. Click Save & Test and you should get a green light.
4. Add a new Dashboard. Open Grafana and click `Complete your first Dashboard`. Click `Add new panel`.
Under the Query tab below the panel, replace `CSV data source` with your dev box data-source added in
step 3. On the Flask backend you can now see a query trying to access the /query entrypoint.
5. Click Save in the upper right hand corner to save your dashboard. Remember to `star it` so you
can easily navigate to it from the main page.
6. To connect a panel to the mysql DB on headnode select the data-source for your panel:
`<db_name>_mysql_datasource`. You can now directly run a mysql query trough the panels Query tab
and bypass Flask.


# Useful extras 
## curl
You can directly send data to Flask using curl:
Sample curl POST wit JSON format
```bash
curl -i --header "Content-Type: application/json"   --request POST   --data '{"cmd":"/bin/MIOpenDriver conv -n 128 -c 1024 -H 14 -W 14 -k 21 -x 1 -p 0 -q 0 -u 2 -v 2 -l 1 -j 1 -m conv -g 1 -F 1 -t 1"}'   http://localhost:5001/fdb_key
curl -i --header "Content-Type: application/json"   --request POST   --data '{"cmd":"/bin/MIOpenDriver conv -n 128 -c 1024 -H 14 -W 14 -k 21 -x 1 -p 0 -q 0 -u 2 -v 2 -l 1 -j 1 -m conv -g 1 -F 1 -t 1"}'   http://localhost:5001/import_configs
```
This commands represents a POST request and can be parsed in the following entry point:
```
@grafana.route('/query', methods=['POST', 'GET'])
req = request.get_json()
```
Note: If -X is passed to curl, the data is encoded and we cannot decipher the Content-Type on
the server side.

## JSON API Documentation
 * Flask API (entrypoints that need to be supported for JSON Dashboard) ```https://grafana.com/grafana/plugins/simpod-json-datasource/```
 * JSON fields: ```https://grafana.com/docs/grafana/latest/dashboards/json-model/```

## Dashboard important utilities
 * Templates and Variables (filters): ```https://grafana.com/docs/grafana/latest/variables/```
 * Tutorials: ```https://grafana.com/tutorials/```
 * Sample Dashboards we can use as examples: ```https://grafana.com/grafana/dashboards/```
