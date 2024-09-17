import pretty_errors
import argparse
import argcomplete
import typing
import pandas as pd
import json
import geopy
import geopy.distance
import subprocess
import os
import csv
import re
import numpy
import importlib

from argparse import ArgumentParser
from rich_argparse import RichHelpFormatter
from datetime import datetime, timedelta


def parse_arguments():
    parser = ArgumentParser(
        prog="wifi-mesh-logdata-processing",
        description="Script evaluates given log-files for bandwith-tests via WiFi depending on the gps-location.",
        formatter_class=RichHelpFormatter
    )

    parser.add_argument(
        "-b", "--bandwithdata",
        action="store_true",
        help="process bandwith-data",
    )

    parser.add_argument(
        "-g", "--gpsdata",
        action="store_true",
        help="process gps-data",
    )

    parser.add_argument(
        "-n", "--networkdump",
        action="store_true",
        help="process networkdump",
    )

    parser.add_argument(
        "-i", "--icmpdata",
        action="store_true",
        help="process icmp-latency-data",
    )

    parser.add_argument(
        "-m", "--mesh",
        action="store_true",
        help="process distances to multiple accesspoints from config-file",
    )

    parser.add_argument(
        "-s", "--sourcefolder",
        type=str,
        help="sourcefolder with measurements"
    )

    argcomplete.autocomplete(parser)
    return parser.parse_args()


def merge_data_sources(df_bandwith: pd.DataFrame, df_gps: pd.DataFrame, df_icmp: pd.DataFrame):
    df = pd.merge(df_gps, df_bandwith, on='Time')
    if df_icmp is not None:
        df = pd.merge(df, df_icmp, on='Time')
    
    df.reset_index()
    return df


def parse_pcaps(pcapfile: str):

    def extract_time(file_name):
        # Define the regular expression pattern to match the time format
        pattern = r'(\d{2})-(\d{2})-(\d{2})\.pcap'

        # Use re.search to find the pattern in the file name
        match = re.search(pattern, file_name)

        # If match is found, extract and return the time
        if match:
            hour = match.group(1)
            minute = match.group(2)
            second = match.group(3)
            return f"{hour}:{minute}:{second}"
        else:
            return "Time not found in the given string."

    def __postprocess_csv(output_file):
        t_str = extract_time(output_file)
        starttime = datetime.strptime(t_str, "%H:%M:%S")
        pcapcsv = pd.read_csv(output_file, delimiter=";")
        pcapcsv['_ws.col.Time'] = pd.to_timedelta(pcapcsv['_ws.col.Time'], unit='s')
        pcapcsv['_ws.col.Time'] = pcapcsv['_ws.col.Time'] + starttime
        pcapcsv['_ws.col.Time'] = pcapcsv['_ws.col.Time'].dt.time
        
        return pcapcsv
    
    output_csv = pcapfile + '.csv'
    os.system(f"tshark -N n -r {pcapfile} -T fields -e frame.number -e _ws.col.Time -e _ws.col.Source -e _ws.col.Destination -e _ws.col.Protocol -e _ws.col.Length -e _ws.col.Info -E header=y -E separator=; > {output_csv}")
    df = __postprocess_csv(output_file=output_csv)
    with open(output_csv, "w", encoding="utf-8", newline='') as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerows(df.itertuples())

def parse_gps_logs(gps_logfile: str):
    # parse gps-logs and save to dataframe
    data = []
    with open(gps_logfile, 'r') as f:
        for line in f:
            parsed_line = json.loads(line.strip())
            
            if parsed_line.get('class') == 'TPV':
                lat = parsed_line.get('lat')
                lon = parsed_line.get('lon')

                time_str = parsed_line.get('time')
                time = pd.to_datetime(time_str)
                time = time.time()

                
                data.append((time, lat, lon))

    df_gps = pd.DataFrame(data, columns=['Time', 'Latitude', 'Longitude'])
    df_gps = df_gps.groupby('Time').agg({
        'Latitude': 'mean',  # Average latitude within each second
        'Longitude': 'mean'  # Average longitude within each second
    })
    df_gps = df_gps.reset_index()

    return df_gps


def parse_icmp_logs(icmp_logfile: str, init_time: datetime.time):
    data = []
    line_counter = 0
    with open(icmp_logfile, "r") as f:
        for line in f:
            if 'icmp_seq=' in line:
                line_counter += 1

                parts = line.split()
                if "Zielhost nicht erreichbar" in line:
                    time = float(parts[2].split('=')[1])
                    timeout_difference = time-line_counter
                    time = time - timeout_difference
                    latency = None
                else:
                    time = float(parts[4].split('=')[1])
                    latency = float(parts[6].split('=')[1])

                time = (datetime.combine(datetime.today(), init_time) + timedelta(seconds=time)).time()
                data.append([time, latency])
    
    df_icmp = pd.DataFrame(data, columns=['Time', 'Latency'])
    return df_icmp


def parse_bandwith_logs(bandwith_logfile: str, init_time: datetime.time):
    data = []
    with open(bandwith_logfile, "r") as f:
        for line in f:
            if '/sec' in line and ('sender'not in line and 'receiver' not in line):
                parts = line.split()

                time = float(parts[2].split('-')[0])
                time = (datetime.combine(datetime.today(), init_time) + timedelta(seconds=time)).time()
                bitrate = float(parts[6])
                data.append([time, bitrate])

    df_bandwith = pd.DataFrame(data, columns=['Time', 'Bitrate'])
    return df_bandwith



def calc_distances(df: pd.DataFrame, georeference: typing.Tuple, columnname: str):
    df[columnname] = df.apply(
        lambda row: geopy.distance.geodesic((row["Latitude"], row["Longitude"]), (georeference[0], georeference[1])).m,
        axis=1
    )
    return df


def load_measurements(sourcefolder: str) -> typing.Dict:
    def __extract_times_from_measurementname(measurementname: str):
        time_idx = measurement.find("_")
        time = measurementname[time_idx+1:time_idx+9]
        return time
    
    measurement_dict = dict()
    
    if not os.path.exists(sourcefolder):
        raise AssertionError(f"Sourcefolder {sourcefolder} does not exist.")
        exit(1)
    else:
        for measurement in os.listdir(sourcefolder):
            time = __extract_times_from_measurementname(measurement)        
            if time not in measurement_dict.keys():
                measurement_dict[time] = dict()
                measurement_dict[time] = {
                    "bandwith":None,
                    "gpsdata":None,
                    "icmp":None,
                    "interfacedump":None,
                    }
            
            p = os.path.join(sourcefolder, measurement)
            
            if "bandwith" in measurement:
                measurement_dict[time]["bandwith"] = p
            elif "gpsdata" in measurement:
                measurement_dict[time]["gpsdata"] = p
            elif "icmp" in measurement:
                measurement_dict[time]["icmp"] = p
            elif "interfacedump" in measurement:
                measurement_dict[time]["interfacedump"] = p
        return measurement_dict

def main():
    cli_args: argparse.Namespace = parse_arguments()
    
    if cli_args.networkdump is True:
        parse_pcaps(pcapfile=cli_args.networkdump)
    else:
            
        if cli_args.sourcefolder is None:
            raise ValueError("Missing Argument. Please add datasource.")
            exit(1)

        if cli_args.bandwithdata is False:
            raise ValueError("Missing Argument. Please add flag for bandwithdata.")
            exit(1)
        
        if cli_args.gpsdata is None:
            raise ValueError("Missing Argument. Please add flag for gpsdata.")
            exit(1)


        for time, measurement in load_measurements(cli_args.sourcefolder).items():
            df_gps = parse_gps_logs(measurement["gpsdata"])
            init_time = df_gps["Time"][0]

            df_bandwith = parse_bandwith_logs(measurement["bandwith"], init_time)

            df_icmp_latency = None
            if cli_args.icmpdata is True:
                df_icmp_latency = parse_icmp_logs(measurement["icmp"], init_time)

            df = merge_data_sources(df_bandwith, df_gps, df_icmp_latency)

            if cli_args.mesh == False:
                config = importlib.import_module('config', 'evaluation')
                df = calc_distances(df, config.REF_POINT, 'DISTANCE')
            else:
                config = importlib.import_module('config_mesh', 'evaluation')
                df = calc_distances(df, config.REF_POINT_CENTER, 'DISTANCE_CENTER')
                df = calc_distances(df, config.REF_POINT_AP_RUESTHALLE, 'DISTANCE_AP_RUESTHALLE')
                df = calc_distances(df, config.REF_POINT_AP_GARAGE, 'DISTANCE_AP_GARAGE')
            df.to_csv(f"{time}.csv")


if __name__ == "__main__":
    main()