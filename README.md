# WIFI-Mesh-Bandwith-Evaluation

This project contains the measurement-setup for a wifi-bandwith measurement through a stationary wifi-accesspoint and a mobile client.
The bandwith and the network-latency to the destination-server and the current gps-location of the mobile client are measured per second.

- Bandwith is measured via iperf3.
- Location is measured via gpspipe.
- Latency is measured via icmp.

## Setup

```
### info
## -- <WIRED-connection> --
## == <WIRELESS-connection> ==

HW-Setup:
Client == WLAN-Access-Point -- Local-Router -- Server
```

### Server-Setup

```bash
# install packages
sudo apt install iperf3

# run server to wait for client-connections
iperf3 -s
```

### Client-Setup

1. Install dependencies for bandwith-test and gps-logging

```bash
# install packages
sudo apt update
sudo apt install iperf3 gpsd gpsd-clients

# stop gpsd-default-service
sudo systemctl stop gpsd.socket
sudo systemctl stop gpsd
```

2. Connect GPS-USB-Antenna

3. Set gps-deamon to usb-interface
Open screen and run gps-deamon to read from serial-gps-antenna
```bash
# screen -S serialgps
sudo gpsd -D 5 -nN /dev/ttyACM0
# deattach screen via CTRL+A+D
```

### Run Measurement

Copy the measurement-script `./client_scripts/measurement.sh` to the client via scp and make it executable

```bash
scp ./client_scripts/measurement.sh <client-username>@<client-ip>:/tmp/
ssh <client-username>@<client-ip>

# make executable
chmod +x /tmp/measurement.sh

# run
/tmp/measurement.sh
```

After Measurement is finished you'll find three files in the same directory you where you installed the script:

- `bandwith_<time>.log`
- `gpsdata_<time>.log`
- `icmp_latency_<time>.log`


## Process logs, sync measurements and calculate data for distance 

First you have to parse the log-data and store the calculations into an csv via:

```bash
# for first info
poetry run python processing/__main__.py --help

# to process all data from one access-point 
poetry run python processing/__main__.py -b -g -i -s .\data\<measurement-folder>\

# to process all data from two accesspoints use "-m"
poetry run python processing/__main__.py -b -g -i -m -s .\data\<measurement-folder>\
```

This will provide results as `*.csv` in `./results/<measurement-folder>`.

## Evaluation

The evaluation-results can be viewed and executed within a jupyter-notebook in `evaluation/evaluate*.ipynb`.