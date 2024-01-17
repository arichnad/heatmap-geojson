#!/usr/bin/python3

# Copyright (c) 2021
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re
import glob
import argparse
import geopy.distance
import math

total_points = 0

def get_gpx_files(args):
	gpx_filters = args.gpx_filters if args.gpx_filters else ['*.gpx']
	gpx_files = []

	for filter in gpx_filters:
		gpx_files += glob.glob('{}/{}'.format(args.gpx_dir, filter))

	if not gpx_files:
		exit('error no gpx files found')

	return gpx_files

def distance(point1, point2):
	#using great_circle because its fast, and accuracy matters not here
	return geopy.distance.great_circle(point1, point2).m

def binning(number, bin_size):
	return round(number/bin_size)*bin_size

def add_points(output_file, points, count, bin_size):
	print('{"type":"Feature","properties":{"count":%d},"geometry":{"type":"MultiPoint","coordinates":[' % count, file=output_file)
	first=True
	round_value = max(math.ceil(-math.log10(bin_size)+1),0)
	for point in points:
		print(
			'{comma}[{longitude:.{round_value}f},{latitude:.{round_value}f}]'.format(
			comma='' if first else ',', end='',
			latitude=point[0],
			longitude=point[1],
			round_value=round_value),
		file=output_file, end='')
		first=False
	print('', file=output_file)
	print(']}}', file=output_file)

def read_gpx(filename):
	global total_points
	with open(filename, 'r') as file:
		for line in file:
			if '<trkpt' in line:
				point = re.findall('[-]?[0-9]*[.]?[0-9]+', line)
				total_points += 1
				yield point

def accept_points(heatmap_data, points):
	last_point = None
	for point in points:
		point = (binning(float(point[0]),args.bin_size), binning(float(point[1]),args.bin_size))
		if point == last_point or last_point is not None and distance(point, last_point) < args.skip_distance:
			continue
		last_point = point
		current_count = heatmap_data[point]+1 if point in heatmap_data else 1
		heatmap_data[point]=min(current_count, args.max_val)

def read_gpx_files(args, heatmap_data):
	for filename in get_gpx_files(args):
		if not args.quiet:
			print('reading {}'.format(filename))

		accept_points(heatmap_data, read_gpx(filename))

def write_geojson_file(args, heatmap_data):
	#for each count, create a feature
	heatmap_data_by_count = {}
	for point, count in heatmap_data.items():
		if count not in heatmap_data_by_count:
			heatmap_data_by_count[count]=[]
		heatmap_data_by_count[count].append(point)
	
	with open(args.output, "w") as output_file:
		print('{"type":"FeatureCollection","features":[', file=output_file)
		first = True
		for count, points in sorted(heatmap_data_by_count.items()):
			print('' if first else ',', end='', file=output_file)
			first=False
			add_points(output_file, points, count, args.bin_size)
		print(']}', file=output_file)

	if not args.quiet:
		print('saved {}'.format(args.output))

def main(args):
	heatmap_data = {}

	read_gpx_files(args, heatmap_data)
	
	print('loaded {} trackpoints:  compressed down to {} points at {} different locations'.format(total_points, sum(heatmap_data.values()), len(heatmap_data)))

	write_geojson_file(args, heatmap_data)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description = 'generate a local heatmap geojson from gpx files', epilog = 'report issues to github.com/arichnad/heatmap-geojson')

	parser.add_argument('--gpx-dir', metavar = 'DIR', default = 'gpx', help = 'directory containing the gpx files (default: gpx)')
	parser.add_argument('--gpx-filters', metavar = 'FILTERS', action = 'append', help = 'glob filter(s) for the gpx files (default: *.gpx)')
	parser.add_argument('--skip-distance', metavar = 'N', type = float, default = 10, help = 'compression: read points that change the position by this distance in meters (default: 10)')
	parser.add_argument('--max-val', metavar = 'N', type = float, default = 20, help = 'maximum value for a heatmap point (default: 20)')
	parser.add_argument('--bin-size', metavar = 'N', type = int, default = .00015, help = 'compression: put each point into a bin of this size in degrees (default: .00015 degrees)')
	parser.add_argument('--output', metavar = 'FILE', default = 'heatmap.geojson', help = 'output geojson file (default: heatmap.geojson)')
	parser.add_argument('--quiet', default = False, action = 'store_true', help = 'quiet output')

	args = parser.parse_args()

	main(args)

