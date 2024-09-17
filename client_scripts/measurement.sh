#!/bin/bash

echo "Start Position-tracking"
gpspipe -w > "gpsdata_$(date +%H-%M-%S.log)" &

echo "Start Network-dump"
sudo tcpdump -i wlx0c7274746783 -w "interfacedump_$(date +%H-%M-%S.pcap)" &

echo "Start ping"
ping 10.16.32.61 > "icmp_$(date +%H-%M-%S.log)" &

echo "Start bandwith-measurement via iperf3"
iperf3 -c 10.16.32.61 -i 1 -t 60 --logfile "bandwith_$(date +%H-%M-%S).log"


echo "kill all measurements after iperf3 is finished"
killall gpspipe
killall tcpdump
killall ping